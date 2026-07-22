#!/usr/bin/env python3
"""Produce independent human/machine Stage-A completion and support reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
CANDIDATES = CYCLE / "candidates"
STAGE = CYCLE / "stage_a"
ORACLE = STAGE / "oracle"
CALLS = CYCLE / "ORACLE_CALL_MANIFEST.csv"
LABELS = CYCLE / "ORACLE_LABEL_MANIFEST.csv"
SCORES = CANDIDATES / "UNIT_SCORES.csv"
SAMPLE = STAGE / "STAGE_A_FROZEN_SAMPLE.csv"
OPPORTUNITIES = STAGE / "STAGE_A_QUERY_OPPORTUNITIES.csv"
EVENT_GROUPS = STAGE / "STAGE_A_K3_EVENT_GROUPS.csv"
SUPPORT_JSON = STAGE / "STAGE_A_SUPPORT_GATE_REPORT.json"
PHYSICAL_COST = STAGE / "STAGE_A_PHYSICAL_COST.json"
ORACLE_COMPLETE = ORACLE / "STAGE_A_ORACLE_COMPLETE.json"
ATTEMPT_LOG = ORACLE / "ATTEMPT_EVENT_LOG.jsonl"
SUPPORT_MD = STAGE / "STAGE_A_SUPPORT_REPORT.md"
LABEL_DISTRIBUTION = STAGE / "STAGE_A_LABEL_DISTRIBUTION.csv"
HARD_NEGATIVES = STAGE / "STAGE_A_HARD_NEGATIVES.csv"
HARD_POSITIVES = STAGE / "STAGE_A_HARD_POSITIVES.csv"
COMPLETION_AUDIT = STAGE / "STAGE_A_COMPLETION_AUDIT.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode())


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    atomic_bytes(path, frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))


def build() -> tuple[dict[str, Any], str, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required = [
        CALLS, LABELS, SCORES, SAMPLE, OPPORTUNITIES, EVENT_GROUPS, SUPPORT_JSON,
        PHYSICAL_COST, ORACLE_COMPLETE, ATTEMPT_LOG,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Stage-A final artifact set is incomplete: {missing}")
    calls = pd.read_csv(CALLS, keep_default_na=False)
    labels = pd.read_csv(LABELS, keep_default_na=False)
    scores = pd.read_csv(SCORES, keep_default_na=False)
    sample = pd.read_csv(SAMPLE, keep_default_na=False)
    opportunities = pd.read_csv(OPPORTUNITIES, keep_default_na=False)
    groups = pd.read_csv(EVENT_GROUPS, keep_default_na=False)
    support = load_json(SUPPORT_JSON)
    cost = load_json(PHYSICAL_COST)
    complete = load_json(ORACLE_COMPLETE)
    events = read_jsonl(ATTEMPT_LOG)
    if len(calls) != 96 or calls["physical_call_id"].nunique() != 96:
        raise RuntimeError("Final call manifest is not exactly 96 unique physical calls")
    if len(labels) != 192 or labels["verification_key"].nunique() != 192:
        raise RuntimeError("Final label manifest is not exactly 192 unique query keys")
    if set(labels["verification_key"]) != set(opportunities["verification_key"]):
        raise RuntimeError("Final label identities differ from frozen opportunities")
    if set(calls["physical_call_id"]) != set(sample["physical_call_id"]):
        raise RuntimeError("Final physical-call identities differ from frozen sample")
    if complete.get("status") != "COMPLETE_COMMIT":
        raise RuntimeError("Oracle completion commit is invalid or absent")
    payload = {key: value for key, value in complete.items() if key != "complete_hash"}
    if complete.get("complete_hash") != canonical_hash(payload):
        raise RuntimeError("Oracle completion self-hash does not recompute")
    for relative, digest in complete["artifacts"].items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise RuntimeError(f"Committed oracle artifact changed: {relative}")

    started = [event for event in events if event.get("event") == "STARTED"]
    accepted = [event for event in events if event.get("event") in {"ACCEPTED", "RECOVERED_ACCEPTED"}]
    uncertain = [event for event in events if event.get("event") == "RECOVERED_UNCERTAIN"]
    attempt_ids = [event["attempt_id"] for event in started]
    if len(started) != 96 or len(accepted) != 96 or uncertain or len(set(attempt_ids)) != 96:
        raise RuntimeError("One-way attempt ledger does not reconcile to 96 exact accepted calls")
    raw_files = sorted((ORACLE / "raw").glob("*.json"))
    parsed_files = sorted((ORACLE / "parsed").glob("*.json"))
    if len(raw_files) != 96 or len(parsed_files) != 96:
        raise RuntimeError("Raw/parsed artifact universe is not exactly 96 each")

    distribution = (
        labels.groupby(["query_id", "model_split_role", "sampling_stratum", "projected_label"], dropna=False)
        .agg(
            semantic_samples=("verification_key", "size"),
            distinct_provider_videos=("session_id", "nunique"),
            distinct_physical_calls=("physical_call_id", "nunique"),
        )
        .reset_index()
        .sort_values(["query_id", "model_split_role", "sampling_stratum", "projected_label"])
        .reset_index(drop=True)
    )
    distribution["projected_label"] = distribution["projected_label"].replace("", "invalid_parse")

    score_subset = scores[["verification_key", "unit_score", "candidate_count", "top_track_id", "top_class_id"]]
    joined = labels.merge(score_subset, on="verification_key", how="left", validate="one_to_one")
    if joined["unit_score"].isna().any():
        raise RuntimeError("Final labels cannot be joined to frozen unit scores")
    quartiles = scores.groupby("query_id")["unit_score"].quantile([0.25, 0.75]).unstack()
    joined["score_q25"] = joined["query_id"].map(quartiles[0.25])
    joined["score_q75"] = joined["query_id"].map(quartiles[0.75])
    hard_positive = joined[
        (joined["projected_label"] == "positive") & (joined["unit_score"] <= joined["score_q25"])
    ].copy()
    hard_negative = joined[
        (joined["projected_label"] == "negative") & (joined["unit_score"] >= joined["score_q75"])
    ].copy()
    hard_fields = [
        "label_row_id", "physical_call_id", "source_dataset", "session_id", "query_id",
        "unit_id", "anchor_id", "model_split_role", "sampling_stratum", "verification_key",
        "witness_track_id", "projected_label", "unit_score", "score_q25", "score_q75",
        "candidate_count", "top_track_id", "top_class_id", "oracle_generic_label",
        "oracle_generic_involved_object", "confidence", "raw_response_sha256",
    ]
    hard_positive = hard_positive[hard_fields].sort_values(["query_id", "unit_score", "verification_key"])
    hard_negative = hard_negative[hard_fields].sort_values(
        ["query_id", "unit_score", "verification_key"], ascending=[True, False, True]
    )

    query_summary: dict[str, dict[str, Any]] = {}
    for query_id in ("Q1", "Q2"):
        part = labels[labels["query_id"] == query_id]
        query_groups = groups[groups["query_id"] == query_id]
        query_summary[query_id] = {
            "positive_units": int((part["projected_label"] == "positive").sum()),
            "negative_units": int((part["projected_label"] == "negative").sum()),
            "abstain_units": int((part["projected_label"] == "abstain").sum()),
            "invalid_parse_units": int((part["projected_label"] == "").sum()),
            "positive_provider_videos": int(part.loc[part["projected_label"] == "positive", "session_id"].nunique()),
            "event_groups": len(query_groups),
            "multi_unit_event_groups": int((pd.to_numeric(query_groups["unit_count"], errors="coerce") >= 2).sum()),
            "hard_positives": int((hard_positive["query_id"] == query_id).sum()),
            "hard_negatives": int((hard_negative["query_id"] == query_id).sum()),
            "support_existence_pass": bool(support["per_query"][query_id]["support_existence_pass"]),
        }

    audit = {
        "audit_id": "MF_PSVR_CYCLE1_STAGE_A_COMPLETION_AUDIT_V1",
        "created_at_utc": utc_now(),
        "status": "PASS",
        "physical_attempts_started": len(started),
        "accepted_durable_calls": len(accepted),
        "uncertain_nonretriable_calls": len(uncertain),
        "raw_artifacts": len(raw_files),
        "parsed_artifacts": len(parsed_files),
        "call_manifest_rows": len(calls),
        "label_manifest_rows": len(labels),
        "parse_failures": int((calls["parse_status"] != "ok").sum()),
        "event_group_rows": len(groups),
        "support_decision": support["decision"],
        "per_query": query_summary,
        "total_physical_cost_seconds": float(cost.get("total_physical_cost_seconds", cost.get("total_wall_seconds", 0.0))),
        "call_manifest_sha256": sha256_file(CALLS),
        "label_manifest_sha256": sha256_file(LABELS),
        "event_groups_sha256": sha256_file(EVENT_GROUPS),
        "physical_cost_sha256": sha256_file(PHYSICAL_COST),
        "support_gate_report_sha256": sha256_file(SUPPORT_JSON),
        "oracle_complete_hash": complete["complete_hash"],
        "heldout_opened": False,
    }
    audit["audit_hash"] = canonical_hash(audit)

    support_lines = []
    for query_id in ("Q1", "Q2"):
        value = query_summary[query_id]
        support_lines.append(
            f"- {query_id}: {value['positive_units']} positives across {value['positive_provider_videos']} providers, "
            f"{value['negative_units']} negatives, {value['abstain_units']} abstentions, "
            f"{value['event_groups']} K3 groups, support gate `{value['support_existence_pass']}`."
        )
    report = f"""# MF-PSVR Stage-A support report

## Strongest supported conclusion

The frozen Stage-A decision is `{support['decision']}`. All 96 one-way physical attempts have exact durable raw and parsed artifacts, and all 192 preregistered Q1/Q2 projections reconcile to the frozen sample.

## Decisive evidence

{chr(10).join(support_lines)}

- Parse failures: {audit['parse_failures']}.
- Uncertain non-retriable calls: {audit['uncertain_nonretriable_calls']}.
- Hard positives: {len(hard_positive)}; hard negatives: {len(hard_negative)} under the frozen full-pool quartiles.
- Total physical cost seconds: {audit['total_physical_cost_seconds']:.6f}.

## Interpretation

Stage A is a support/trainability test over a label-independently enriched sample, not a prevalence estimate. A pass establishes that the frozen pool contains enough observed Q1/Q2 support under the preregistered gates; it does not establish that any learned representation generalizes across sources. A stop decision identifies insufficient support under this exact frozen design and must not be repaired by retrying, replacing, or duplicating identities.

## Main competing explanation

Apparent score failures may reflect ambiguity or noise in the generic unit-level oracle rather than model-correctable candidate ranking. The downstream grouped models and shuffled/ID-only controls are required to distinguish transferable feature signal from selection-stratum, query, or provider memorization.

## Next action and rejection trigger

Build one semantic row per frozen verification key, then compare raw YOLO confidence, FIFO order, aggregate features, and genuine temporal sequences under grouped source/session evaluation. Reject readiness for a physical pilot if performance does not exceed shuffled/ID-only controls, calibration is poor, or gains collapse on the worst provider/query group.
"""
    return audit, report, distribution, hard_negative, hard_positive


def write() -> dict[str, Any]:
    audit, report, distribution, hard_negative, hard_positive = build()
    atomic_csv(LABEL_DISTRIBUTION, distribution)
    atomic_csv(HARD_NEGATIVES, hard_negative)
    atomic_csv(HARD_POSITIVES, hard_positive)
    atomic_bytes(SUPPORT_MD, report.encode("utf-8"))
    audit.update({
        "support_report_sha256": sha256_file(SUPPORT_MD),
        "label_distribution_sha256": sha256_file(LABEL_DISTRIBUTION),
        "hard_negatives_sha256": sha256_file(HARD_NEGATIVES),
        "hard_positives_sha256": sha256_file(HARD_POSITIVES),
    })
    audit["audit_hash"] = canonical_hash({key: value for key, value in audit.items() if key != "audit_hash"})
    atomic_json(COMPLETION_AUDIT, audit)
    return audit


def verify() -> dict[str, Any]:
    if not all(path.is_file() for path in (SUPPORT_MD, LABEL_DISTRIBUTION, HARD_NEGATIVES, HARD_POSITIVES, COMPLETION_AUDIT)):
        raise RuntimeError("Independent Stage-A report artifact set is incomplete")
    expected, report, distribution, hard_negative, hard_positive = build()
    if SUPPORT_MD.read_text(encoding="utf-8") != report:
        raise RuntimeError("Stage-A support markdown does not recompute")
    pd.testing.assert_frame_equal(
        pd.read_csv(LABEL_DISTRIBUTION, keep_default_na=False).reset_index(drop=True),
        distribution.reset_index(drop=True), check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        pd.read_csv(HARD_NEGATIVES, keep_default_na=False).reset_index(drop=True),
        hard_negative.reset_index(drop=True), check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        pd.read_csv(HARD_POSITIVES, keep_default_na=False).reset_index(drop=True),
        hard_positive.reset_index(drop=True), check_dtype=False,
    )
    audit = load_json(COMPLETION_AUDIT)
    payload = {key: value for key, value in audit.items() if key != "audit_hash"}
    if audit.get("audit_hash") != canonical_hash(payload) or audit.get("status") != "PASS":
        raise RuntimeError("Independent Stage-A completion audit self-hash is invalid")
    bindings = {
        "support_report_sha256": sha256_file(SUPPORT_MD),
        "label_distribution_sha256": sha256_file(LABEL_DISTRIBUTION),
        "hard_negatives_sha256": sha256_file(HARD_NEGATIVES),
        "hard_positives_sha256": sha256_file(HARD_POSITIVES),
    }
    if any(audit.get(key) != value for key, value in bindings.items()):
        raise RuntimeError("Independent Stage-A report artifact binding changed")
    for key, value in expected.items():
        if key not in {"created_at_utc", "audit_hash"} and audit.get(key) != value:
            raise RuntimeError(f"Independent Stage-A audit field does not recompute: {key}")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["write", "verify"])
    args = parser.parse_args()
    result = write() if args.stage == "write" else verify()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
