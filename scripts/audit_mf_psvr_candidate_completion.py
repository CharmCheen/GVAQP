#!/usr/bin/env python3
"""Independently verify and summarize the frozen MF-PSVR Y8 extraction.

This auditor is deliberately separate from the frozen extraction runner.  It
recomputes the provider/query-unit universe, durable per-provider hashes,
global merges, numeric validity, frozen implementation hashes, and source
media hashes before declaring completion.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
OUT = CYCLE / "candidates"
POOL_MANIFEST = CYCLE / "TRAINING_POOL_MANIFEST.csv"
POOL_AUDIT_MANIFEST = CYCLE / "AUDIT_MANIFEST.json"
PROTOCOL = CYCLE / "ORACLE_ACQUISITION_PROTOCOL.json"
SHORT_PROFILE = CYCLE / "SHORT_CLIP_OVERHEAD_PROFILE.json"
PREINFERENCE_AUDIT = CYCLE / "stage_a/oracle/PREINFERENCE_AUDIT_MANIFEST.json"
CALL_MANIFEST = CYCLE / "ORACLE_CALL_MANIFEST.csv"
LABEL_MANIFEST = CYCLE / "ORACLE_LABEL_MANIFEST.csv"
UNIT_MANIFEST = OUT / "UNIT_MANIFEST.csv"
UNIT_SCORES = OUT / "UNIT_SCORES.csv"
TRACK_CANDIDATES = OUT / "TRACK_CANDIDATES.csv"
PLAN = OUT / "CANDIDATE_EXTRACTION_PLAN.json"
STATE = OUT / "CANDIDATE_EXTRACTION_STATE.json"
RUN_REPORT = OUT / "EXTRACT_RUN_REPORT.json"
RUN_RECEIPT = OUT / "CANDIDATE_EXTRACTION_RUN_RECEIPT.json"
PROXY_CONFIG = CYCLE / "TRAINING_POOL_PROXY_CONFIG.json"
PROXY_SOURCE = ROOT / "scripts/run_psvr_two_video_proxy.py"
RUNNER_SOURCE = ROOT / "scripts/run_mf_psvr_training_pool_candidates.py"
COMPLETION_AUDIT = OUT / "CANDIDATE_EXTRACTION_COMPLETION_AUDIT.json"
COST_AUDIT = OUT / "CANDIDATE_EXTRACTION_COST.json"
FAILURES = OUT / "CANDIDATE_EXTRACTION_FAILURES.csv"
SCORE_DISTRIBUTION = OUT / "CANDIDATE_SCORE_DISTRIBUTION.csv"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_bytes(payload.encode("utf-8"))


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


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    temporary_rows = []
    for row in rows:
        temporary_rows.append({field: row.get(field, "") for field in fields})
    frame = pd.DataFrame(temporary_rows, columns=fields)
    atomic_bytes(path, frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))


def candidate_dir(session_id: str, source_sha256: str) -> Path:
    safe = session_id.replace(":", "_").replace("/", "_")
    return OUT / "per_video" / f"{safe}__{source_sha256[:12]}"


def add_failure(
    failures: list[dict[str, str]],
    code: str,
    detail: str,
    row: dict[str, Any] | None = None,
) -> None:
    row = row or {}
    failures.append({
        "failure_code": code,
        "source_dataset": str(row.get("source_dataset", "")),
        "session_id": str(row.get("session_id", "")),
        "local_locator": str(row.get("local_locator", "")),
        "detail": detail,
    })


def exact_marker(
    directory: Path,
    pool_row: dict[str, Any],
    expected_units: int,
    config_hash: str,
) -> tuple[dict[str, Any] | None, str | None]:
    marker_path = directory / "EXTRACTION_COMPLETE.json"
    if not marker_path.exists():
        return None, "missing EXTRACTION_COMPLETE.json"
    try:
        marker = load_json(marker_path)
        checks = {
            "status": marker.get("status") == "COMPLETE",
            "unit_scope": marker.get("unit_scope") == "FULL_PROVIDER_VIDEO",
            "unit_scope_complete": marker.get("unit_scope_complete") is True,
            "source_dataset": marker.get("source_dataset") == pool_row["source_dataset"],
            "session_id": marker.get("session_id") == pool_row["session_id"],
            "source_sha256": marker.get("source_sha256") == pool_row["content_sha256"],
            "proxy_config_hash": marker.get("proxy_config_hash") == config_hash,
            "expected_units": int(marker.get("expected_units", -1)) == expected_units,
            "units": int(marker.get("units", -1)) == expected_units,
            "unit_score_rows": int(marker.get("unit_score_rows", -1)) == 2 * expected_units,
            "heldout_opened": marker.get("heldout_opened") is False,
        }
        file_bindings = {
            "TRACK_CANDIDATES.csv": "track_candidates_sha256",
            "UNIT_SCORES.csv": "unit_scores_sha256",
            "UNIT_PROCESSING.json": "unit_processing_sha256",
        }
        for filename, field in file_bindings.items():
            path = directory / filename
            checks[f"exists:{filename}"] = path.is_file()
            if path.is_file():
                checks[f"hash:{filename}"] = sha256_file(path) == marker.get(field)
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            return marker, "marker checks failed: " + ", ".join(failed)
        return marker, None
    except Exception as exc:  # fail closed and retain the exact provider identity
        return None, f"marker validation raised {type(exc).__name__}: {exc}"


def hash_source(row: dict[str, Any]) -> tuple[str, str | None, str | None]:
    session_id = str(row["session_id"])
    path = ROOT / str(row["local_locator"])
    try:
        if not path.is_file():
            return session_id, None, "source media missing"
        observed = sha256_file(path)
        if observed != row["content_sha256"]:
            return session_id, observed, "source SHA-256 mismatch"
        return session_id, observed, None
    except Exception as exc:
        return session_id, None, f"source hashing raised {type(exc).__name__}: {exc}"


def distribution_rows(scores: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query_id, group in scores.groupby("query_id", sort=True):
        values = pd.to_numeric(group["unit_score"], errors="coerce")
        candidate_counts = pd.to_numeric(group["candidate_count"], errors="coerce")
        rows.append({
            "query_id": query_id,
            "rows": len(group),
            "zero_score_rows": int((values == 0).sum()),
            "nonzero_score_rows": int((values > 0).sum()),
            "mean": float(values.mean()),
            "std": float(values.std(ddof=0)),
            "min": float(values.min()),
            "p01": float(values.quantile(0.01, interpolation="linear")),
            "p05": float(values.quantile(0.05, interpolation="linear")),
            "p25": float(values.quantile(0.25, interpolation="linear")),
            "p50": float(values.quantile(0.50, interpolation="linear")),
            "p75": float(values.quantile(0.75, interpolation="linear")),
            "p95": float(values.quantile(0.95, interpolation="linear")),
            "p99": float(values.quantile(0.99, interpolation="linear")),
            "max": float(values.max()),
            "candidate_count_mean": float(candidate_counts.mean()),
            "candidate_count_max": int(candidate_counts.max()),
        })
    return rows


def main(mode: str) -> None:
    if mode == "write" and COMPLETION_AUDIT.is_file():
        existing = load_json(COMPLETION_AUDIT)
        if existing.get("status") == "PASS":
            raise RuntimeError("Refusing to overwrite the finalized candidate PASS receipt; use `verify`")
    persisted_audit = load_json(COMPLETION_AUDIT) if mode == "verify" else None
    failures: list[dict[str, str]] = []
    required = [
        POOL_MANIFEST, POOL_AUDIT_MANIFEST, PROTOCOL, SHORT_PROFILE, PREINFERENCE_AUDIT,
        CALL_MANIFEST, LABEL_MANIFEST,
        UNIT_MANIFEST, UNIT_SCORES, TRACK_CANDIDATES, PLAN,
        STATE, RUN_REPORT, RUN_RECEIPT, PROXY_CONFIG, PROXY_SOURCE, RUNNER_SOURCE,
    ]
    missing_required = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing_required:
        for path in missing_required:
            add_failure(failures, "MISSING_REQUIRED_ARTIFACT", path)
        atomic_csv(
            FAILURES,
            failures,
            ["failure_code", "source_dataset", "session_id", "local_locator", "detail"],
        )
        raise SystemExit("Candidate completion audit cannot run: required artifacts are missing")

    pool_all = pd.read_csv(POOL_MANIFEST, keep_default_na=False)
    pool = pool_all[
        (pool_all["source_dataset"] == "nexar_collision_prediction")
        & (pool_all["pool_status"] == "ELIGIBLE_PENDING_CANDIDATE_EXTRACTION")
    ].copy().sort_values("session_id").reset_index(drop=True)
    units = pd.read_csv(UNIT_MANIFEST, keep_default_na=False)
    scores = pd.read_csv(UNIT_SCORES, keep_default_na=False)
    tracks = pd.read_csv(TRACK_CANDIDATES, keep_default_na=False)
    plan = load_json(PLAN)
    state = load_json(STATE)
    run_report = load_json(RUN_REPORT)
    receipt = load_json(RUN_RECEIPT)
    config = load_json(PROXY_CONFIG)
    protocol = load_json(PROTOCOL)
    short_profile = load_json(SHORT_PROFILE)
    preinference = load_json(PREINFERENCE_AUDIT)

    if len(pool) != 603:
        add_failure(failures, "PROVIDER_UNIVERSE_COUNT", f"expected 603, observed {len(pool)}")
    if pool["session_id"].duplicated().any() or pool["content_sha256"].duplicated().any():
        add_failure(failures, "PROVIDER_UNIVERSE_DUPLICATE", "session or content identity duplicated")
    if len(units) != 2654:
        add_failure(failures, "UNIT_UNIVERSE_COUNT", f"expected 2654, observed {len(units)}")
    if sha256_file(UNIT_MANIFEST) != short_profile.get("unit_manifest_sha256"):
        add_failure(
            failures,
            "UNIT_MANIFEST_FROZEN_HASH",
            "byte identity differs from the pre-extraction short-clip profile binding",
        )
    unit_keys = ["source_dataset", "session_id", "unit_id"]
    if units.duplicated(unit_keys).any():
        add_failure(failures, "UNIT_UNIVERSE_DUPLICATE", "unit identity duplicated")

    expected_unit_counts = units.groupby("session_id").size().to_dict()
    pool_sessions = set(pool["session_id"].astype(str))
    unit_sessions = set(units["session_id"].astype(str))
    if pool_sessions != unit_sessions:
        add_failure(
            failures,
            "UNIT_PROVIDER_COVERAGE",
            f"missing={sorted(pool_sessions - unit_sessions)[:10]}, extra={sorted(unit_sessions - pool_sessions)[:10]}",
        )

    plan_without_hash = dict(plan)
    observed_plan_hash = plan_without_hash.pop("plan_hash", None)
    if canonical_hash(plan_without_hash) != observed_plan_hash:
        add_failure(failures, "PLAN_SELF_HASH", "candidate plan canonical hash does not recompute")
    expected_plan_values = {
        "status": "PREFLIGHT_PASS_GPU_NOT_RUN",
        "provider_videos": 603,
        "units": 2654,
        "query_unit_rows_expected": 5308,
        "heldout_opened": False,
        "semantic_labels_accessed": False,
    }
    for key, expected in expected_plan_values.items():
        if plan.get(key) != expected:
            add_failure(failures, "PLAN_FROZEN_VALUE", f"{key}: expected {expected!r}, observed {plan.get(key)!r}")
    plan_artifact_bindings = {
        "pool_manifest_sha256": POOL_MANIFEST,
        "pool_audit_manifest_sha256": POOL_AUDIT_MANIFEST,
        "acquisition_protocol_sha256": PROTOCOL,
    }
    for field, path in plan_artifact_bindings.items():
        if plan.get(field) != sha256_file(path):
            add_failure(failures, "PLAN_ARTIFACT_BINDING", f"{field} does not match {path.relative_to(ROOT)}")
    if plan.get("proxy_config_hash") != config.get("training_pool_proxy_config_hash"):
        add_failure(failures, "PLAN_PROXY_CONFIG_BINDING", "plan and proxy config internal identities differ")

    protocol_payload = {key: value for key, value in protocol.items() if key != "protocol_hash"}
    if canonical_hash(protocol_payload) != protocol.get("protocol_hash"):
        add_failure(failures, "PROTOCOL_SELF_HASH", "acquisition protocol canonical hash does not recompute")
    config_payload = {
        key: value for key, value in config.items() if key != "training_pool_proxy_config_hash"
    }
    if canonical_hash(config_payload) != config.get("training_pool_proxy_config_hash"):
        add_failure(failures, "PROXY_CONFIG_SELF_HASH", "training-pool proxy config canonical hash does not recompute")
    if protocol.get("heldout_opened") is not False or config.get("heldout_opened") is not False:
        add_failure(failures, "FROZEN_BOUNDARY_FLAG", "protocol or proxy config held-out flag is not false")

    bound_artifact_failures = 0
    if mode == "write":
        for relative, binding in preinference.get("artifacts", {}).items():
            path = CYCLE / relative
            if not path.is_file() or sha256_file(path) != binding.get("sha256") or path.stat().st_size != int(binding.get("bytes", -1)):
                bound_artifact_failures += 1
                add_failure(failures, "PREINFERENCE_ARTIFACT_BINDING", relative)
        for relative, expected_hash in preinference.get("code_and_test_bindings", {}).items():
            path = ROOT / relative
            if not path.is_file() or sha256_file(path) != expected_hash:
                bound_artifact_failures += 1
                add_failure(failures, "PREINFERENCE_CODE_BINDING", relative)

    expected_state_values = {
        "status": "COMPLETE",
        "completed_provider_videos": 603,
        "total_provider_videos": 603,
        "unit_score_rows": 5308,
        "heldout_opened": False,
        "semantic_labels_accessed": False,
    }
    for key, expected in expected_state_values.items():
        if state.get(key) != expected:
            add_failure(failures, "STATE_COMPLETION_VALUE", f"{key}: expected {expected!r}, observed {state.get(key)!r}")
    current_call_rows = len(pd.read_csv(CALL_MANIFEST, keep_default_na=False))
    current_label_rows = len(pd.read_csv(LABEL_MANIFEST, keep_default_na=False))
    authoritative_call_rows = (
        current_call_rows if mode == "write" else int(persisted_audit["oracle_call_rows_at_candidate_audit"])
    )
    authoritative_label_rows = (
        current_label_rows if mode == "write" else int(persisted_audit["oracle_label_rows_at_candidate_audit"])
    )
    if mode == "write" and (authoritative_call_rows != 0 or authoritative_label_rows != 0):
        add_failure(
            failures,
            "ORACLE_OUTPUT_BEFORE_CANDIDATE_FREEZE",
            f"call rows={authoritative_call_rows}, label rows={authoritative_label_rows}",
        )
    if run_report.get("status") != "COMPLETE":
        add_failure(failures, "RUN_REPORT_STATUS", f"observed {run_report.get('status')!r}")
    if int(run_report.get("this_run_selected_provider_videos", -1)) != 603:
        add_failure(failures, "RUN_REPORT_SCOPE", "run report did not select exactly 603 provider videos")
    run_results = run_report.get("this_run_results", [])
    result_sessions = [row.get("session_id") for row in run_results]
    if len(run_results) != 603 or len(set(result_sessions)) != 603 or set(result_sessions) != pool_sessions:
        add_failure(failures, "RUN_REPORT_PROVIDER_IDENTITIES", "run result identities are not the exact 603-provider universe")
    if int(receipt.get("preexisting_valid_provider_markers", -1)) != 0:
        add_failure(failures, "RUN_RECEIPT_RESUME_SCOPE", "this completion run was not recorded as a zero-marker launch")
    if receipt.get("heldout_opened") is not False:
        add_failure(failures, "RUN_RECEIPT_HELDOUT", "held-out flag is not false")

    config_hash = str(config["training_pool_proxy_config_hash"])
    marker_rows: list[dict[str, Any]] = []
    expected_marker_paths: set[Path] = set()
    score_parts: list[pd.DataFrame] = []
    track_parts: list[pd.DataFrame] = []
    processing_rows_observed = 0
    processing_content_errors = 0
    per_video_score_content_errors = 0
    per_video_track_content_errors = 0
    for pool_row in pool.to_dict("records"):
        directory = candidate_dir(pool_row["session_id"], pool_row["content_sha256"])
        marker_path = directory / "EXTRACTION_COMPLETE.json"
        expected_marker_paths.add(marker_path.resolve())
        marker, error = exact_marker(
            directory,
            pool_row,
            int(expected_unit_counts.get(pool_row["session_id"], -1)),
            config_hash,
        )
        if error is not None:
            add_failure(failures, "PROVIDER_MARKER_INVALID", error, pool_row)
            continue
        assert marker is not None
        marker_rows.append(marker)
        provider_scores = pd.read_csv(directory / "UNIT_SCORES.csv", keep_default_na=False)
        provider_tracks = pd.read_csv(directory / "TRACK_CANDIDATES.csv", keep_default_na=False)
        processing = load_json(directory / "UNIT_PROCESSING.json")
        provider_units = units[units["session_id"] == pool_row["session_id"]].copy()
        expected_provider_score_keys = {
            (int(row.unit_id), query_id)
            for row in provider_units.itertuples()
            for query_id in ("Q1", "Q2")
        }
        try:
            observed_provider_score_keys = {
                (int(row.unit_id), str(row.query_id)) for row in provider_scores.itertuples()
            }
        except Exception:
            observed_provider_score_keys = set()
        if (
            len(provider_scores) != 2 * len(provider_units)
            or provider_scores.duplicated(["source_dataset", "session_id", "unit_id", "query_id"]).any()
            or observed_provider_score_keys != expected_provider_score_keys
            or set(provider_scores["source_dataset"].astype(str)) != {str(pool_row["source_dataset"])}
            or set(provider_scores["session_id"].astype(str)) != {str(pool_row["session_id"])}
        ):
            per_video_score_content_errors += 1
            add_failure(failures, "PROVIDER_SCORE_CONTENT", "identity/count mismatch", pool_row)

        expected_processing = provider_units.set_index("unit_id").to_dict("index")
        processing_rows_observed += len(processing) if isinstance(processing, list) else 0
        processing_error = not isinstance(processing, list) or len(processing) != len(provider_units)
        seen_processing_units: set[int] = set()
        sampled_sum = decoded_sum = 0
        gpu_sum = 0.0
        if isinstance(processing, list):
            for record in processing:
                try:
                    unit_id = int(record["unit_id"])
                    expected_unit = expected_processing[unit_id]
                    if unit_id in seen_processing_units:
                        raise ValueError("duplicate processing unit")
                    seen_processing_units.add(unit_id)
                    effective_end = min(int(expected_unit["end_frame"]), int(pool_row["frame_or_image_count"]) - 1)
                    expected_decoded = effective_end - int(expected_unit["start_frame"]) + 1
                    interval = max(1, int(round(float(pool_row["fps"]) / float(config["sample_fps"]))))
                    expected_sampled = ((effective_end - int(expected_unit["start_frame"])) // interval) + 1
                    numeric_cost_fields = [
                        "decode_seconds", "detector_gpu_seconds", "detector_path_seconds",
                        "evidence_serialization_seconds", "rule_scoring_cpu_seconds",
                        "seek_seconds", "tracking_cpu_seconds",
                    ]
                    if (
                        int(record["decoded_frames"]) != expected_decoded
                        or int(record["sampled_frames"]) != expected_sampled
                        or int(record["start_frame"]) != int(expected_unit["start_frame"])
                        or int(record["requested_end_frame"]) != int(expected_unit["end_frame"])
                        or int(record["effective_end_frame"]) != effective_end
                        or int(record["container_frame_count"]) != int(pool_row["frame_or_image_count"])
                        or not isinstance(record.get("candidate_evidence_sha256"), str)
                        or len(record.get("candidate_evidence_sha256", "")) != 64
                        or any(not math.isfinite(float(record[field])) or float(record[field]) < 0 for field in numeric_cost_fields)
                    ):
                        raise ValueError("processing content invariant failed")
                    sampled_sum += int(record["sampled_frames"])
                    decoded_sum += int(record["decoded_frames"])
                    gpu_sum += float(record["detector_gpu_seconds"])
                except Exception:
                    processing_error = True
        if seen_processing_units != set(expected_processing):
            processing_error = True
        if (
            sampled_sum != int(marker["sampled_frames"])
            or decoded_sum != int(marker["decoded_frames"])
            or not math.isclose(gpu_sum, float(marker["detector_gpu_seconds"]), rel_tol=0, abs_tol=1e-9)
        ):
            processing_error = True
        if processing_error:
            processing_content_errors += 1
            add_failure(failures, "PROVIDER_PROCESSING_CONTENT", "unit/frame/cost invariant failed", pool_row)

        if not provider_tracks.empty:
            track_key_columns = ["source_dataset", "session_id", "query_id", "unit_id", "track_id"]
            track_numeric_columns = [
                "unit_id", "track_id", "class_id", "observations", "track_persistence",
                "path_directed_lateral_motion", "box_growth", "front_region_occupancy",
                "approximate_ttc_urgency", "lane_relative_motion", "boundary_crossing",
                "ego_corridor_overlap", "road_geometry_reliability",
                "track_persistence_normalized", "path_directed_lateral_motion_normalized",
                "box_growth_normalized", "front_region_occupancy_normalized",
                "approximate_ttc_urgency_normalized", "candidate_score", "witness_track_id",
            ]
            numeric = provider_tracks[track_numeric_columns].apply(pd.to_numeric, errors="coerce")
            expected_track_verification = provider_tracks.apply(
                lambda row: f"{row['source_dataset']}|{row['session_id']}|{row['query_id']}|{int(row['unit_id'])}",
                axis=1,
            )
            q1_allowed = {1, 2, 3, 5, 7}
            q2_allowed = {0, 1, 3}
            class_ids = pd.to_numeric(provider_tracks["class_id"], errors="coerce")
            query_class_valid = (
                ((provider_tracks["query_id"] == "Q1") & class_ids.isin(q1_allowed))
                | ((provider_tracks["query_id"] == "Q2") & class_ids.isin(q2_allowed))
            )
            if (
                provider_tracks.duplicated(track_key_columns).any()
                or not np.isfinite(numeric.to_numpy(dtype=float)).all()
                or (numeric["observations"] <= 0).any()
                or (numeric["candidate_score"] < 0).any()
                or (numeric["candidate_score"] > 1).any()
                or not query_class_valid.all()
                or not expected_track_verification.equals(provider_tracks["verification_key"])
                or set(provider_tracks["source_dataset"].astype(str)) != {str(pool_row["source_dataset"])}
                or set(provider_tracks["session_id"].astype(str)) != {str(pool_row["session_id"])}
            ):
                per_video_track_content_errors += 1
                add_failure(failures, "PROVIDER_TRACK_CONTENT", "identity/class/numeric invariant failed", pool_row)
        score_parts.append(pd.read_csv(directory / "UNIT_SCORES.csv"))
        track_parts.append(pd.read_csv(directory / "TRACK_CANDIDATES.csv"))

    observed_marker_paths = {
        path.resolve() for path in (OUT / "per_video").glob("*/EXTRACTION_COMPLETE.json")
    }
    for extra in sorted(observed_marker_paths - expected_marker_paths):
        add_failure(failures, "EXTRA_PROVIDER_MARKER", str(extra.relative_to(ROOT)))

    with ThreadPoolExecutor(max_workers=4) as executor:
        source_results = list(executor.map(hash_source, pool.to_dict("records")))
    source_hashes_validated = 0
    source_hash_errors = {session: error for session, _, error in source_results if error}
    for pool_row in pool.to_dict("records"):
        error = source_hash_errors.get(pool_row["session_id"])
        if error:
            add_failure(failures, "SOURCE_CONTENT_HASH", error, pool_row)
        else:
            source_hashes_validated += 1

    locator_tokens = pool["local_locator"].astype(str).str.lower()
    prohibited_locator_rows = int(locator_tokens.str.contains(r"held.?out|/v0(?:/|\.|_)|/v1(?:/|\.|_)", regex=True).sum())
    if prohibited_locator_rows:
        add_failure(failures, "HELDOUT_OR_DEV_LOCATOR", str(prohibited_locator_rows))

    expected_score_keys = {
        (str(row.source_dataset), str(row.session_id), int(row.unit_id), query_id)
        for row in units.itertuples()
        for query_id in ("Q1", "Q2")
    }
    observed_score_keys: set[tuple[str, str, int, str]] = set()
    numeric_unit_ids = pd.to_numeric(scores.get("unit_id"), errors="coerce")
    for index, row in scores.iterrows():
        if pd.isna(numeric_unit_ids.iloc[index]):
            continue
        observed_score_keys.add((
            str(row["source_dataset"]), str(row["session_id"]), int(numeric_unit_ids.iloc[index]), str(row["query_id"])
        ))
    duplicate_score_rows = int(scores.duplicated([*unit_keys, "query_id"]).sum())
    missing_score_rows = len(expected_score_keys - observed_score_keys)
    extra_score_rows = len(observed_score_keys - expected_score_keys)
    if len(scores) != 5308:
        add_failure(failures, "UNIT_SCORE_ROW_COUNT", f"expected 5308, observed {len(scores)}")
    if duplicate_score_rows:
        add_failure(failures, "UNIT_SCORE_DUPLICATES", str(duplicate_score_rows))
    if missing_score_rows:
        add_failure(failures, "UNIT_SCORE_MISSING", str(missing_score_rows))
    if extra_score_rows:
        add_failure(failures, "UNIT_SCORE_EXTRA", str(extra_score_rows))
    if set(scores["query_id"].astype(str)) != {"Q1", "Q2"}:
        add_failure(failures, "QUERY_UNIVERSE", repr(sorted(set(scores["query_id"].astype(str)))))

    expected_serialized_keys = scores.apply(
        lambda row: f"{row['source_dataset']}|{row['session_id']}|{row['query_id']}|{int(row['unit_id'])}",
        axis=1,
    )
    invalid_verification_keys = int((expected_serialized_keys != scores["verification_key"]).sum())
    if invalid_verification_keys:
        add_failure(failures, "VERIFICATION_KEY_SERIALIZATION", str(invalid_verification_keys))

    unit_score_numeric = pd.to_numeric(scores["unit_score"], errors="coerce")
    candidate_count_numeric = pd.to_numeric(scores["candidate_count"], errors="coerce")
    invalid_numeric_rows = int(
        (~np.isfinite(unit_score_numeric)).sum()
        + (~np.isfinite(candidate_count_numeric)).sum()
        + ((unit_score_numeric < 0) | (unit_score_numeric > 1)).sum()
        + ((candidate_count_numeric < 0) | (candidate_count_numeric % 1 != 0)).sum()
    )
    if invalid_numeric_rows:
        add_failure(failures, "INVALID_NUMERIC_ROWS", str(invalid_numeric_rows))
    inconsistent_empty_witness = int(
        (
            (candidate_count_numeric == 0)
            & ((scores["top_track_id"] != "") | (scores["top_class_id"] != "") | (unit_score_numeric != 0))
        ).sum()
    )
    if inconsistent_empty_witness:
        add_failure(failures, "EMPTY_WITNESS_INCONSISTENCY", str(inconsistent_empty_witness))

    if score_parts:
        reconstructed_scores = pd.concat(score_parts, ignore_index=True)
        reconstructed_score_sha = sha256_bytes(
            reconstructed_scores.to_csv(index=False, lineterminator="\n").encode("utf-8")
        )
        if reconstructed_score_sha != sha256_file(UNIT_SCORES):
            add_failure(failures, "GLOBAL_SCORE_MERGE", "global UNIT_SCORES.csv is not the exact per-provider concatenation")
    if track_parts:
        reconstructed_tracks = pd.concat(track_parts, ignore_index=True)
        reconstructed_track_sha = sha256_bytes(
            reconstructed_tracks.to_csv(index=False, lineterminator="\n").encode("utf-8")
        )
        if reconstructed_track_sha != sha256_file(TRACK_CANDIDATES):
            add_failure(failures, "GLOBAL_TRACK_MERGE", "global TRACK_CANDIDATES.csv is not the exact per-provider concatenation")

    state_score_sha = state.get("unit_scores_sha256")
    state_track_sha = state.get("track_candidates_sha256")
    if sha256_file(UNIT_SCORES) != state_score_sha:
        add_failure(failures, "STATE_SCORE_HASH", "state hash does not bind global UNIT_SCORES.csv")
    if sha256_file(TRACK_CANDIDATES) != state_track_sha:
        add_failure(failures, "STATE_TRACK_HASH", "state hash does not bind global TRACK_CANDIDATES.csv")

    frozen_hashes = {
        "runner_sha256": sha256_file(RUNNER_SOURCE),
        "proxy_source_sha256": sha256_file(PROXY_SOURCE),
        "weight_sha256": sha256_file(Path(config["weight_path"])),
        "tracker_sha256": sha256_file(Path(config["tracker"]["implementation_path"])),
    }
    expected_frozen_hashes = {
        "runner_sha256": receipt["runner_sha256"],
        "proxy_source_sha256": plan["proxy_source_sha256"],
        "weight_sha256": plan["weight_sha256"],
        "tracker_sha256": plan["tracker_sha256"],
    }
    for key, observed in frozen_hashes.items():
        if observed != expected_frozen_hashes[key]:
            add_failure(failures, "FROZEN_IMPLEMENTATION_HASH", f"{key}: expected {expected_frozen_hashes[key]}, observed {observed}")

    score_rows = distribution_rows(scores)
    distribution_fields = [
        "query_id", "rows", "zero_score_rows", "nonzero_score_rows", "mean", "std",
        "min", "p01", "p05", "p25", "p50", "p75", "p95", "p99", "max",
        "candidate_count_mean", "candidate_count_max",
    ]
    if mode == "write":
        atomic_csv(SCORE_DISTRIBUTION, score_rows, distribution_fields)
    else:
        expected_distribution = pd.DataFrame(score_rows, columns=distribution_fields)
        observed_distribution = pd.read_csv(SCORE_DISTRIBUTION)
        pd.testing.assert_frame_equal(
            observed_distribution, expected_distribution, check_dtype=False, atol=1e-12, rtol=1e-12
        )

    marker_gpu_seconds = float(sum(float(row["detector_gpu_seconds"]) for row in marker_rows))
    marker_processing_seconds = float(sum(float(row["processing_wall_seconds"]) for row in marker_rows))
    initialization_seconds = float(run_report.get("this_run_initialization_seconds", 0.0))
    start = datetime.fromisoformat(str(receipt["process_start_utc"]).replace("Z", "+00:00"))
    completion = datetime.fromtimestamp(RUN_REPORT.stat().st_mtime, tz=timezone.utc)
    wall_clock_seconds = (completion - start).total_seconds()
    per_video_processing = pd.Series([float(row["processing_wall_seconds"]) for row in marker_rows], dtype=float)
    per_video_gpu = pd.Series([float(row["detector_gpu_seconds"]) for row in marker_rows], dtype=float)
    cost = {
        "cost_id": "MF_PSVR_CYCLE1_Y8_EXTRACTION_COST_V1",
        "status": "COMPLETE" if not failures else "AUDIT_FAILURE",
        "run_start_utc": start.isoformat().replace("+00:00", "Z"),
        "run_completion_utc": completion.isoformat().replace("+00:00", "Z"),
        "wall_clock_seconds": float(wall_clock_seconds),
        "detector_gpu_seconds": marker_gpu_seconds,
        "detector_initialization_seconds": initialization_seconds,
        "summed_provider_processing_wall_seconds": marker_processing_seconds,
        "summed_processing_plus_initialization_seconds": marker_processing_seconds + initialization_seconds,
        "provider_videos": len(marker_rows),
        "units": int(sum(int(row["units"]) for row in marker_rows)),
        "sampled_frames": int(sum(int(row["sampled_frames"]) for row in marker_rows)),
        "decoded_frames": int(sum(int(row["decoded_frames"]) for row in marker_rows)),
        "per_video_processing_seconds_p50": float(per_video_processing.quantile(0.50)) if len(per_video_processing) else None,
        "per_video_processing_seconds_p95": float(per_video_processing.quantile(0.95)) if len(per_video_processing) else None,
        "per_video_gpu_seconds_p50": float(per_video_gpu.quantile(0.50)) if len(per_video_gpu) else None,
        "per_video_gpu_seconds_p95": float(per_video_gpu.quantile(0.95)) if len(per_video_gpu) else None,
        "wall_clock_source": "observed process start receipt to durable EXTRACT_RUN_REPORT mtime",
        "gpu_seconds_source": "sum of exact-hash-valid per-provider completion markers",
        "heldout_opened": False,
    }
    if mode == "write":
        atomic_json(COST_AUDIT, cost)
    elif load_json(COST_AUDIT) != cost:
        add_failure(failures, "COST_AUDIT_RECOMPUTE", "persisted extraction cost does not recompute")

    failed_sessions = sorted({row["session_id"] for row in failures if row["session_id"]})
    audit = {
        "audit_id": "MF_PSVR_CYCLE1_Y8_EXTRACTION_COMPLETION_AUDIT_V1",
        "created_at_utc": utc_now() if mode == "write" else persisted_audit["created_at_utc"],
        "status": "PASS" if not failures else "FAIL",
        "expected_provider_videos": 603,
        "completed_provider_videos": len(marker_rows),
        "failed_provider_videos": len(failed_sessions),
        "expected_units": 2654,
        "observed_units": len(units),
        "expected_unit_score_rows": 5308,
        "observed_unit_score_rows": len(scores),
        "duplicate_unit_score_rows": duplicate_score_rows,
        "missing_unit_score_rows": missing_score_rows,
        "extra_unit_score_rows": extra_score_rows,
        "invalid_numeric_rows": invalid_numeric_rows,
        "invalid_verification_keys": invalid_verification_keys,
        "track_candidate_rows": len(tracks),
        "source_hashes_expected": 603,
        "source_hashes_validated": source_hashes_validated,
        "source_hash_failures": len(source_hash_errors),
        "preinference_bound_artifact_or_code_failures": bound_artifact_failures,
        "processing_rows_observed": processing_rows_observed,
        "provider_processing_content_errors": processing_content_errors,
        "provider_score_content_errors": per_video_score_content_errors,
        "provider_track_content_errors": per_video_track_content_errors,
        "prohibited_heldout_or_dev_locator_rows": prohibited_locator_rows,
        "frozen_hashes": frozen_hashes,
        "expected_frozen_hashes": expected_frozen_hashes,
        "unit_manifest_sha256": sha256_file(UNIT_MANIFEST),
        "unit_scores_sha256": sha256_file(UNIT_SCORES),
        "track_candidates_sha256": sha256_file(TRACK_CANDIDATES),
        "candidate_state_sha256": sha256_file(STATE),
        "candidate_plan_sha256": sha256_file(PLAN),
        "run_report_sha256": sha256_file(RUN_REPORT),
        "score_distribution_sha256": sha256_file(SCORE_DISTRIBUTION),
        "cost_audit_sha256": sha256_file(COST_AUDIT),
        "failure_rows": len(failures),
        "semantic_labels_accessed": False,
        "oracle_call_rows_at_candidate_audit": authoritative_call_rows,
        "oracle_label_rows_at_candidate_audit": authoritative_label_rows,
        "heldout_opened": False,
        "completion_gate": (
            "All exact provider/unit/query identities, source and frozen implementation hashes, "
            "per-provider durable artifacts, global merges, numeric values, and no-leakage flags recompute."
        ),
    }
    if mode == "write":
        atomic_csv(
            FAILURES,
            failures,
            ["failure_code", "source_dataset", "session_id", "local_locator", "detail"],
        )
    audit["failures_sha256"] = sha256_file(FAILURES)
    audit["audit_hash"] = canonical_hash(audit)
    if mode == "write":
        atomic_json(COMPLETION_AUDIT, audit)
    elif audit != persisted_audit:
        raise RuntimeError("Finalized candidate completion receipt does not exactly recompute")
    print(json.dumps(audit, indent=2))
    if failures:
        raise SystemExit(f"Candidate completion audit failed with {len(failures)} finding(s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["write", "verify"])
    main(parser.parse_args().stage)
