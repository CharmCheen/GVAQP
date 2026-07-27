#!/usr/bin/env python3
"""Freeze and audit the existing Stage-A Q1 assets before P0/P1/P2 fitting."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from cutin_p012_common import (
    CONTRACT, CONTRACT_ID, EVENT_CONTRACT_ID, MODELING, ORACLE_CONTRACT_ID,
    OUT, P0_FEATURES, P1_INCREMENTAL, P2_INCREMENTAL, POOL,
    PROHIBITED_MODEL_FIELDS, QUERY_ID, ROOT, SEED, STAGE, canonical_hash,
    read_json, sha256_file, utc_now, write_csv, write_json,
)


ASSETS = [
    (CONTRACT, "experiment_contract"),
    (POOL / "ORACLE_LABEL_MANIFEST.csv", "durable_oracle_label_manifest"),
    (POOL / "ORACLE_CALL_MANIFEST.csv", "durable_oracle_call_ledger"),
    (POOL / "ORACLE_ACQUISITION_PROTOCOL.json", "oracle_and_query_contract"),
    (POOL / "TRAINING_POOL_PROXY_CONFIG.json", "yolov8_bytetrack_config"),
    (STAGE / "STAGE_A_FROZEN_SAMPLE.csv", "frozen_candidate_sample"),
    (STAGE / "STAGE_A_FREEZE_MANIFEST.json", "candidate_freeze_manifest"),
    (STAGE / "STAGE_A_K3_EVENT_GROUPS.csv", "disqualified_same_label_derived_event_groups"),
    (STAGE / "STAGE_A_ORACLE_EXECUTION_SPEC.json", "oracle_execution_spec"),
    (STAGE / "STAGE_A_PHYSICAL_COST.json", "oracle_physical_cost"),
    (MODELING / "STAGE_A_TEMPORAL_MATERIALIZATION_AUDIT.json", "detection_track_materialization_audit"),
    (MODELING / "STAGE_A_CANDIDATE_VALUE_DATASET.parquet", "stage_a_candidate_dataset"),
    (MODELING / "STAGE_A_TEMPORAL_SEQUENCES.npz", "stage_a_temporal_features"),
    (MODELING / "STAGE_A_TEMPORAL_FEATURE_SCHEMA.json", "stage_a_temporal_schema"),
    (ROOT / "scripts/run_psvr_two_video_proxy.py", "frozen_proxy_implementation"),
    (ROOT / "models/yolo/yolov8n.pt", "yolov8_weights"),
    (ROOT / "outputs/ours_vs_baselines_realcartest_v1/COMPARISON_REPORT.md", "arc_full_results_other_universe"),
    (ROOT / "outputs/ours_vs_baselines_realcartest_v1/PROTOCOL_CONFIRMATION.md", "arc_protocol_other_universe"),
    (ROOT / "outputs/ours_vs_baselines_realcartest_v1/main_comparison_table.csv", "arc_metrics_other_universe"),
]


def source_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() or "UNKNOWN"


def creation_time(path: Path) -> str:
    return __import__("datetime").datetime.fromtimestamp(
        path.stat().st_mtime, tz=__import__("datetime").timezone.utc
    ).isoformat()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_manifest() -> list[dict[str, Any]]:
    commit = source_commit()
    rows: list[dict[str, Any]] = []
    for path, kind in ASSETS:
        exists = path.is_file()
        rows.append({
            "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            "artifact_type": kind,
            "source_commit": commit,
            "file_hash": sha256_file(path) if exists else "",
            "creation_time": creation_time(path) if exists else "",
            "query_id": QUERY_ID if "other_universe" not in kind else "Q1_OTHER_UNIVERSE",
            "oracle_contract_id": ORACLE_CONTRACT_ID if "other_universe" not in kind else "PSVR_TWO_VIDEO_STRICT_ORACLE",
            "event_matching_contract_id": EVENT_CONTRACT_ID if "other_universe" not in kind else "consecutive_positive_units_v1_OTHER_UNIVERSE",
            "validity_status": "VALID" if exists else "MISSING",
        })
    return rows


def audit_labels() -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    labels = pd.read_csv(POOL / "ORACLE_LABEL_MANIFEST.csv", dtype=str).fillna("")
    calls = pd.read_csv(POOL / "ORACLE_CALL_MANIFEST.csv", dtype=str).fillna("")
    q = labels[labels.query_id.eq(QUERY_ID)].copy()
    contract_cols = ["model_hash", "prompt_hash", "parser_schema_hash", "parser_source_hash", "sampling_code_hash"]
    identities = q[contract_cols].drop_duplicates().to_dict("records")
    call_dupes = q.groupby("verification_key").size()
    conflicts: list[dict[str, Any]] = []
    for key, block in q.groupby("verification_key"):
        projected = sorted(set(block.projected_label))
        contracts = block[contract_cols].drop_duplicates()
        if len(projected) > 1 or len(contracts) > 1:
            conflicts.append({
                "verification_key": key,
                "conflict_type": "VERSION_CONFLICT",
                "labels": "|".join(projected),
                "contract_identity_count": len(contracts),
            })
    q["candidate_status"] = np.where(
        q.label_status.eq("VALID") & q.parse_status.eq("ok") & q.projected_label.isin(["positive", "negative"]),
        np.where(q.projected_label.eq("positive"), "VALID_POSITIVE", "VALID_NEGATIVE"),
        np.where(q.projected_label.eq("abstain"), "AMBIGUOUS", "EXECUTION_FAILURE"),
    )
    q["candidate_id"] = q.verification_key
    q["window_start"] = q.unit_start_seconds.astype(float)
    q["window_end"] = q.unit_end_seconds.astype(float)
    q["oracle_label"] = q.projected_label
    q["oracle_call_id"] = q.physical_call_id
    q["oracle_version"] = q.model_hash
    q["oracle_contract_id"] = ORACLE_CONTRACT_ID
    latency = calls.set_index("physical_call_id").generation_runtime_seconds.to_dict()
    q["oracle_latency_sec"] = q.physical_call_id.map(latency)
    q["oracle_output_status"] = q.candidate_status
    q["oracle_output_hash"] = q.raw_response_sha256
    audit = {
        "audit_id": "PSVR_CUTIN_P012_LABEL_AUDIT_V1",
        "query_id": QUERY_ID,
        "query_name": "OTHER_VEHICLE_ENTERS_EGO_PATH",
        "projection": ["cyclist", "vehicle"],
        "semantic_scope_warning": "NOT_A_VEHICLE_ONLY_OR_HUMAN_ADJUDICATED_CUTIN_LABEL",
        "rows": len(q),
        "status_counts": q.candidate_status.value_counts().sort_index().to_dict(),
        "duplicate_verification_keys": int((call_dupes > 1).sum()),
        "contract_identities": identities,
        "conflicts": len(conflicts),
        "new_oracle_calls": 0,
        "label_modifications": 0,
        "status": "PASS_WITH_QUERY_SCOPE_LIMITATION" if not conflicts and len(identities) == 1 else "FAIL",
    }
    return q, audit, conflicts


def audit_events(labels: pd.DataFrame) -> tuple[dict[str, Any], dict[str, str]]:
    events = pd.read_csv(STAGE / "STAGE_A_K3_EVENT_GROUPS.csv", dtype=str).fillna("")
    events = events[events.query_id.eq(QUERY_ID)].copy()
    audit = {
        "audit_id": "PSVR_CUTIN_P012_REFERENCE_EVENT_AUDIT_V1",
        "event_match_rule_version": "MISSING",
        "mapping_policy": "NONE",
        "reference_event_count": 0,
        "mapped_positive_candidates": 0,
        "disqualified_k3_group_count": len(events),
        "disqualification_reason": (
            "STAGE_A_K3_EVENT_GROUPS is built directly from the same projected positive "
            "candidate labels; it is not an independent EventRelation reference."
        ),
        "provenance_evidence": [
            "src/garc_eval/mf_psvr/stage_a_oracle.py:166-199",
            "scripts/run_mf_psvr_stage_a_oracle.py:1200-1207",
        ],
        "conflict_audits": "NOT_EVALUABLE_WITHOUT_INDEPENDENT_REFERENCE",
        "scope": "EVENT_LEVEL_CLAIM_BLOCKED",
        "status": "BLOCKED_MISSING_FROZEN_MATCH_RULE",
    }
    return audit, {}


def make_splits(labels: pd.DataFrame, event_map: dict[str, str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    q = labels.copy()
    q["reference_event_id"] = q.verification_key.map(event_map).fillna("")
    q["split_group_id"] = q.session_id
    q["valid_for_confirmatory"] = q.candidate_status.isin(["VALID_POSITIVE", "VALID_NEGATIVE"])
    q["label_binary"] = np.where(q.candidate_status.eq("VALID_POSITIVE"), 1,
                                 np.where(q.candidate_status.eq("VALID_NEGATIVE"), 0, np.nan))
    valid = q[q.valid_for_confirmatory].copy()
    q["outer_fold"] = -1
    # Deterministic group-level allocator. sklearn's heuristic produced a
    # zero-positive test fold on this sparse 10-positive set, so balance
    # positive-bearing components first, then total candidate rows.
    grouped = (
        valid.groupby("split_group_id")
        .agg(positive=("label_binary", "sum"), rows=("label_binary", "size"))
        .reset_index()
    )
    grouped["tie"] = grouped.split_group_id.map(lambda value: canonical_hash(f"{SEED}|{value}"))
    grouped = grouped.sort_values(["positive", "rows", "tie"], ascending=[False, False, True])
    fold_positive = [0.0] * 5
    fold_rows = [0] * 5
    group_fold: dict[str, int] = {}
    for row in grouped.itertuples(index=False):
        if row.positive > 0:
            fold = min(range(5), key=lambda f: (fold_positive[f], fold_rows[f], f))
        else:
            fold = min(range(5), key=lambda f: (fold_rows[f], fold_positive[f], f))
        group_fold[row.split_group_id] = fold
        fold_positive[fold] += float(row.positive)
        fold_rows[fold] += int(row.rows)
    for idx in valid.index:
        q.loc[idx, "outer_fold"] = group_fold[q.loc[idx, "split_group_id"]]
    # Invalid candidates remain assigned by their connected component, never by labels.
    for idx in q.index[q.outer_fold.lt(0)]:
        q.loc[idx, "outer_fold"] = group_fold.get(
            q.loc[idx, "split_group_id"],
            int(canonical_hash(q.loc[idx, "split_group_id"])[:8], 16) % 5,
        )
    columns = [
        "candidate_id", "source_dataset", "session_id", "query_id", "unit_id",
        "window_start", "window_end", "reference_event_id", "split_group_id",
        "outer_fold", "candidate_status", "valid_for_confirmatory",
    ]
    manifest = q[columns].copy().sort_values("candidate_id")
    # Freeze every inner development assignment as part of the pre-fit split
    # artifact. -1 denotes the corresponding outer test fold or an invalid row.
    for outer in range(5):
        column = f"inner_fold_outer_{outer}"
        manifest[column] = -1
        eligible = manifest.valid_for_confirmatory & manifest.outer_fold.ne(outer)
        eligible_rows = manifest.loc[eligible]
        y_lookup = q.set_index("candidate_id").candidate_status.map(
            {"VALID_NEGATIVE": 0, "VALID_POSITIVE": 1}
        )
        y = eligible_rows.candidate_id.map(y_lookup).astype(int).to_numpy()
        groups = eligible_rows.split_group_id.to_numpy()
        splitter = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED)
        for inner_fold, (_, dev) in enumerate(splitter.split(eligible_rows, y, groups)):
            manifest.loc[eligible_rows.index[dev], column] = inner_fold
    overlap_edges = 0
    for _, block in q.groupby("session_id"):
        vals = block[["window_start", "window_end"]].astype(float).to_numpy()
        for i in range(len(vals)):
            overlap_edges += sum(vals[i, 0] < vals[j, 1] and vals[j, 0] < vals[i, 1] for j in range(i + 1, len(vals)))
    leakage = []
    valid_manifest = manifest[manifest.valid_for_confirmatory]
    for group, block in valid_manifest.groupby("split_group_id"):
        if block.outer_fold.nunique() != 1:
            leakage.append(group)
    audit = {
        "audit_id": "PSVR_CUTIN_P012_SPLIT_LEAKAGE_AUDIT_V1",
        "candidate_count": len(q),
        "valid_candidate_count": int(q.valid_for_confirmatory.sum()),
        "connected_components": int(q.split_group_id.nunique()),
        "same_session_edges_present": True,
        "temporal_overlap_edges": int(overlap_edges),
        "groups_crossing_outer_folds": leakage,
        "fold_counts": {
            str(int(fold)): {str(status): int(count) for status, count in counts.items()}
            for fold, counts in
            valid_manifest.groupby(["outer_fold", "candidate_status"]).size().unstack(fill_value=0).to_dict("index").items()
        },
        "split_method": "deterministic group-level sparse-class balancing, seed=20260723",
        "status": "PASS" if (
            not leakage
            and valid_manifest.outer_fold.nunique() == 5
            and all(
                block.candidate_status.nunique() == 2
                for _, block in valid_manifest.groupby("outer_fold")
            )
        ) else "FAIL",
    }
    return manifest, audit


def schema(representation: str, features: list[str], additions: list[str]) -> dict[str, Any]:
    return {
        "schema_id": f"PSVR_CUTIN_{representation.upper()}_FEATURE_SCHEMA_V1",
        "contract_id": CONTRACT_ID,
        "representation": representation.upper(),
        "features": features,
        "incremental_features": additions,
        "feature_count": len(features),
        "coordinates": "normalized_by_frame_width_height",
        "rates": "per_second",
        "sampling_fps": 5.0,
        "test_outcomes_seen_before_freeze": False,
        "prohibited_model_fields": PROHIBITED_MODEL_FIELDS,
        "missingness": "P2 motion failure retained with indicators; fold-local imputer",
        "frozen_at_utc": utc_now(),
    }


def environment_lock() -> dict[str, Any]:
    packages = {}
    for name in ["numpy", "pandas", "sklearn", "lightgbm", "cv2", "ultralytics", "psutil"]:
        try:
            module = __import__(name)
            packages[name] = getattr(module, "__version__", "unknown")
        except Exception as exc:
            packages[name] = f"UNAVAILABLE:{exc}"
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        text=True, capture_output=True, check=False,
    )
    return {
        "created_at_utc": utc_now(),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": packages,
        "gpu": gpu.stdout.strip() or "UNAVAILABLE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-frozen", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.verify_frozen and (OUT / "contract_freeze.json").exists():
        freeze = read_json(OUT / "contract_freeze.json")
        current = sha256_file(CONTRACT)
        if current != freeze["contract_sha256"]:
            raise SystemExit("Contract changed after freeze")
        print("Frozen contract verified")
        return

    manifest = build_manifest()
    if any(row["validity_status"] != "VALID" for row in manifest):
        raise SystemExit("Required frozen assets are missing")
    write_json(OUT / "frozen_manifest.json", {"contract_id": CONTRACT_ID, "artifacts": manifest})
    write_csv(OUT / "frozen_manifest.csv", manifest)
    labels, label_audit, conflicts = audit_labels()
    write_json(OUT / "label_audit.json", label_audit)
    write_csv(OUT / "label_conflicts.csv", conflicts,
              ["verification_key", "conflict_type", "labels", "contract_identity_count"])
    event_audit, event_map = audit_events(labels)
    write_json(OUT / "reference_event_audit.json", event_audit)
    valid = labels.candidate_status.isin(["VALID_POSITIVE", "VALID_NEGATIVE"])
    support = {
        "total_candidate_count": len(labels),
        "valid_labeled_candidate_count": int(valid.sum()),
        "positive_count": int(labels.candidate_status.eq("VALID_POSITIVE").sum()),
        "negative_count": int(labels.candidate_status.eq("VALID_NEGATIVE").sum()),
        "invalid_count": int((~valid).sum()),
        "label_coverage": float(valid.mean()),
        "POLICY_SUPPORT_COMPLETE": bool(valid.all()),
        "ORACLE_SUPPORT_STATUS": "COMPLETE" if valid.all() else "LABELED_SUPPORT_REPLAY",
        "invalid_candidate_ids": sorted(labels.loc[~valid, "candidate_id"].tolist()),
    }
    write_json(OUT / "oracle_support_audit.json", support)
    splits, leakage = make_splits(labels, event_map)
    splits.to_csv(OUT / "split_manifest.csv", index=False)
    write_json(OUT / "split_leakage_audit.json", leakage)
    write_json(OUT / "feature_schema_p0.json", schema("P0", P0_FEATURES, P0_FEATURES))
    write_json(OUT / "feature_schema_p1.json", schema("P1", P0_FEATURES + P1_INCREMENTAL, P1_INCREMENTAL))
    write_json(OUT / "feature_schema_p2.json", schema("P2", P0_FEATURES + P1_INCREMENTAL + P2_INCREMENTAL, P2_INCREMENTAL))
    write_json(OUT / "environment_lock.json", environment_lock())
    write_json(OUT / "code_version.json", {
        "git_commit": source_commit(),
        "git_branch": subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, text=True,
                                     capture_output=True, check=False).stdout.strip(),
        "contract_id": CONTRACT_ID,
        "audit_script_sha256": sha256_file(Path(__file__)),
        "common_script_sha256": sha256_file(ROOT / "scripts/cutin_p012_common.py"),
    })
    arc_contract = {
        "strong_baseline": "ARC",
        "arc_full_evidence": "outputs/ours_vs_baselines_realcartest_v1/COMPARISON_REPORT.md",
        "arc_candidate_universe": "realcartest_2000_3200_120_units_20_events",
        "p012_candidate_universe": "MF_PSVR_STAGE_A_FROZEN_SAMPLE",
        "candidate_universe_match": False,
        "deadline_contract_match": False,
        "oracle_contract_match": False,
        "ARC_FULL_status": "EXISTING_STRONG_OFFLINE_RESULT_OTHER_UNIVERSE",
        "component_replacement_status": "BLOCKED_ASSET_MISMATCH",
        "permitted_replay": "LABELED_SUPPORT_REPLAY",
        "prohibition": "Do not present other-universe ARC results as a P0/P1/P2 component replacement.",
    }
    write_json(OUT / "arc_baseline_contract.json", arc_contract)
    manifest_hash = sha256_file(OUT / "frozen_manifest.json")
    freeze = {
        "contract_id": CONTRACT_ID,
        "frozen_at_utc": utc_now(),
        "contract_sha256": sha256_file(CONTRACT),
        "manifest_sha256": manifest_hash,
        "split_manifest_sha256": sha256_file(OUT / "split_manifest.csv"),
        "feature_schema_sha256": {
            p: sha256_file(OUT / p) for p in
            ["feature_schema_p0.json", "feature_schema_p1.json", "feature_schema_p2.json"]
        },
        "training_started": False,
    }
    write_json(OUT / "contract_freeze.json", freeze)
    print(json.dumps({
        "contract": freeze["contract_sha256"],
        "manifest": manifest_hash,
        "labels": support,
        "event_status": event_audit["status"],
        "split_status": leakage["status"],
    }, indent=2))


if __name__ == "__main__":
    main()
