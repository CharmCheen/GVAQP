#!/usr/bin/env python3
"""Freeze the label-blind 96-call Stage-A sample after complete Y8 extraction."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from garc_eval.mf_psvr.stage_a import select_stage_a_units, selection_spec  # noqa: E402


CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
CANDIDATES = CYCLE / "candidates"
OUT = CYCLE / "stage_a"
PROTOCOL = CYCLE / "ORACLE_ACQUISITION_PROTOCOL.json"
PROXY_CONFIG = CYCLE / "TRAINING_POOL_PROXY_CONFIG.json"
UNIT_MANIFEST = CANDIDATES / "UNIT_MANIFEST.csv"
UNIT_SCORES = CANDIDATES / "UNIT_SCORES.csv"
CANDIDATE_PLAN = CANDIDATES / "CANDIDATE_EXTRACTION_PLAN.json"
CANDIDATE_STATE = CANDIDATES / "CANDIDATE_EXTRACTION_STATE.json"
CALL_MANIFEST = CYCLE / "ORACLE_CALL_MANIFEST.csv"
LABEL_MANIFEST = CYCLE / "ORACLE_LABEL_MANIFEST.csv"
SAMPLE = OUT / "STAGE_A_FROZEN_SAMPLE.csv"
QUERY_OPPORTUNITIES = OUT / "STAGE_A_QUERY_OPPORTUNITIES.csv"
FREEZE_MANIFEST = OUT / "STAGE_A_FREEZE_MANIFEST.json"
STATE = OUT / "STAGE_A_STATE.json"
SELECTOR_SOURCE = ROOT / "src/garc_eval/mf_psvr/stage_a.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode(),
    )


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    atomic_bytes(path, frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_empty_oracle_manifests() -> None:
    for path in (CALL_MANIFEST, LABEL_MANIFEST):
        if len(pd.read_csv(path, keep_default_na=False)) != 0:
            raise RuntimeError(f"Cannot freeze Stage A after oracle output exists: {path}")


def build_selection_rows() -> list[dict[str, Any]]:
    units = pd.read_csv(UNIT_MANIFEST, keep_default_na=False)
    scores = pd.read_csv(UNIT_SCORES, keep_default_na=False)
    if len(units) != 2654 or len(scores) != 5308:
        raise RuntimeError(f"Incomplete candidate tables: units={len(units)}, scores={len(scores)}")
    score_keys = ["source_dataset", "session_id", "unit_id", "query_id"]
    if scores.duplicated(score_keys).any():
        raise RuntimeError("Candidate unit scores contain duplicate query verification keys")
    if set(scores["query_id"]) != {"Q1", "Q2"}:
        raise RuntimeError("Candidate unit scores do not contain exactly Q1 and Q2")
    expected_verification = scores.apply(
        lambda row: (
            f"{row['source_dataset']}|{row['session_id']}|"
            f"{row['query_id']}|{int(row['unit_id'])}"
        ),
        axis=1,
    )
    if not expected_verification.equals(scores["verification_key"]):
        raise RuntimeError("Candidate verification-key serialization changed")

    index = ["source_dataset", "session_id", "unit_id"]
    score_wide = scores.pivot(index=index, columns="query_id", values="unit_score").rename(
        columns={"Q1": "q1_score", "Q2": "q2_score"}
    )
    witness_wide = scores.pivot(index=index, columns="query_id", values="top_track_id").rename(
        columns={"Q1": "q1_witness_track_id", "Q2": "q2_witness_track_id"}
    )
    wide = score_wide.join(witness_wide).reset_index()
    merged = units.merge(wide, on=index, how="left", validate="one_to_one")
    if merged[["q1_score", "q2_score"]].isna().any().any():
        raise RuntimeError("Candidate scores are missing for at least one unit")
    rows = []
    for row in merged.to_dict("records"):
        for key in ("q1_witness_track_id", "q2_witness_track_id"):
            row[key] = None if pd.isna(row[key]) or row[key] == "" else int(float(row[key]))
        row["unit_id"] = int(row["unit_id"])
        row["q1_score"] = float(row["q1_score"])
        row["q2_score"] = float(row["q2_score"])
        rows.append(row)
    return rows


def existing_freeze_valid() -> bool:
    if not FREEZE_MANIFEST.exists():
        return False
    try:
        value = load_json(FREEZE_MANIFEST)
        return (
            value["status"] == "FROZEN_ORACLE_NOT_RUN"
            and value["selector_source_sha256"] == sha256_file(SELECTOR_SOURCE)
            and value["unit_scores_sha256"] == sha256_file(UNIT_SCORES)
            and value["sample_sha256"] == sha256_file(SAMPLE)
            and value["query_opportunities_sha256"] == sha256_file(QUERY_OPPORTUNITIES)
            and value["physical_oracle_calls_at_freeze"] == 0
        )
    except Exception:
        return False


def main() -> None:
    if existing_freeze_valid():
        print(json.dumps(load_json(FREEZE_MANIFEST), indent=2))
        return
    validate_empty_oracle_manifests()
    protocol = load_json(PROTOCOL)
    config = load_json(PROXY_CONFIG)
    plan = load_json(CANDIDATE_PLAN)
    state = load_json(CANDIDATE_STATE)
    frozen_spec = protocol["stage_a_support_pilot"]
    if frozen_spec["selection_spec_hash"] != selection_spec()["selection_spec_hash"]:
        raise RuntimeError("Stage-A selection spec diverges from the acquisition protocol")
    if frozen_spec["selection_implementation_sha256"] != sha256_file(SELECTOR_SOURCE):
        raise RuntimeError("Stage-A selector source changed after protocol freeze")
    if state["status"] != "COMPLETE" or int(state["completed_provider_videos"]) != 603:
        raise RuntimeError("Full-pool candidate extraction is not physically complete")
    if int(state["unit_score_rows"]) != 5308:
        raise RuntimeError("Full-pool candidate query-unit rows are incomplete")
    if plan["proxy_config_hash"] != config["training_pool_proxy_config_hash"]:
        raise RuntimeError("Candidate plan and label-independent proxy config diverge")

    selected = select_stage_a_units(build_selection_rows())
    sample_columns = [
        "physical_call_id", "source_dataset", "session_id", "source_sha256",
        "model_split_role", "unit_id", "anchor_id", "anchor_time", "start_time", "end_time",
        "start_frame", "end_frame", "local_locator", "sampling_tag_only",
        "sampling_anchor_seconds", "sampling_stratum", "stratum_priority",
        "within_stratum_split_rank", "selection_hash", "anchor_distance_seconds",
        "q1_score", "q2_score", "q1_witness_track_id", "q2_witness_track_id",
    ]
    sample = pd.DataFrame(selected)[sample_columns]
    atomic_csv(SAMPLE, sample)

    opportunities = []
    for row in selected:
        for query_id in ("Q1", "Q2"):
            opportunities.append({
                "request_row_id": f"{row['physical_call_id']}__{query_id}",
                "physical_call_id": row["physical_call_id"],
                "source_dataset": row["source_dataset"],
                "session_id": row["session_id"],
                "source_sha256": row["source_sha256"],
                "model_split_role": row["model_split_role"],
                "unit_id": row["unit_id"],
                "query_id": query_id,
                "verification_key": (
                    f"{row['source_dataset']}|{row['session_id']}|{query_id}|{row['unit_id']}"
                ),
                "witness_track_id": row[f"{query_id.lower()}_witness_track_id"],
                "sampling_stratum": row["sampling_stratum"],
                "label_status": "FROZEN_REQUEST_ORACLE_NOT_RUN",
            })
    opportunity_frame = pd.DataFrame(opportunities)
    if opportunity_frame["verification_key"].duplicated().any() or len(opportunity_frame) != 192:
        raise RuntimeError("Stage-A query opportunity identity invariant failed")
    atomic_csv(QUERY_OPPORTUNITIES, opportunity_frame)

    identity_payload = sample[
        ["physical_call_id", "source_dataset", "session_id", "unit_id", "sampling_stratum"]
    ].to_dict("records")
    manifest = {
        "freeze_id": "MF_PSVR_CYCLE1_STAGE_A_FREEZE_V1",
        "status": "FROZEN_ORACLE_NOT_RUN",
        "frozen_at_utc": utc_now(),
        "protocol_sha256": sha256_file(PROTOCOL),
        "proxy_config_sha256": sha256_file(PROXY_CONFIG),
        "candidate_plan_sha256": sha256_file(CANDIDATE_PLAN),
        "candidate_state_sha256": sha256_file(CANDIDATE_STATE),
        "unit_manifest_sha256": sha256_file(UNIT_MANIFEST),
        "unit_scores_sha256": sha256_file(UNIT_SCORES),
        "selector_source_sha256": sha256_file(SELECTOR_SOURCE),
        "selection_spec_hash": selection_spec()["selection_spec_hash"],
        "physical_call_identities": 96,
        "query_verification_keys": 192,
        "physical_oracle_calls_at_freeze": 0,
        "identity_payload_hash": canonical_hash(identity_payload),
        "sample_sha256": sha256_file(SAMPLE),
        "query_opportunities_sha256": sha256_file(QUERY_OPPORTUNITIES),
        "heldout_opened": False,
    }
    manifest["freeze_hash"] = canonical_hash(manifest)
    atomic_json(FREEZE_MANIFEST, manifest)
    atomic_json(STATE, {
        "status": "FROZEN_ORACLE_NOT_RUN",
        "physical_oracle_calls": 0,
        "projected_labels": 0,
        "next_action": "Run exactly the 96 frozen generic calls after explicit oracle authority.",
        "heldout_opened": False,
    })
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
