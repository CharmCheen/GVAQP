#!/usr/bin/env python3
"""Build and verify the query-aligned MF-PSVR Stage-A value dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
CANDIDATES = CYCLE / "candidates"
STAGE = CYCLE / "stage_a"
MODEL_OUT = STAGE / "modeling"
LABELS = CYCLE / "ORACLE_LABEL_MANIFEST.csv"
CALLS = CYCLE / "ORACLE_CALL_MANIFEST.csv"
SAMPLE = STAGE / "STAGE_A_FROZEN_SAMPLE.csv"
OPPORTUNITIES = STAGE / "STAGE_A_QUERY_OPPORTUNITIES.csv"
GROUPS = STAGE / "STAGE_A_K3_EVENT_GROUPS.csv"
ORACLE_COMPLETE = STAGE / "oracle/STAGE_A_ORACLE_COMPLETE.json"
UNIT_SCORES = CANDIDATES / "UNIT_SCORES.csv"
TRACKS = CANDIDATES / "TRACK_CANDIDATES.csv"
TEMPORAL_NPZ = MODEL_OUT / "STAGE_A_TEMPORAL_SEQUENCES.npz"
TEMPORAL_INDEX = MODEL_OUT / "STAGE_A_TEMPORAL_INDEX.csv"
TEMPORAL_AUDIT = MODEL_OUT / "STAGE_A_TEMPORAL_MATERIALIZATION_AUDIT.json"
DATASET = MODEL_OUT / "STAGE_A_CANDIDATE_VALUE_DATASET.parquet"
DATASET_CARD = MODEL_OUT / "STAGE_A_DATASET_CARD.md"
FEATURE_SCHEMA = MODEL_OUT / "STAGE_A_FEATURE_SCHEMA.json"
LABEL_SCHEMA = MODEL_OUT / "STAGE_A_LABEL_SCHEMA.json"
DEDUP_AUDIT = MODEL_OUT / "STAGE_A_DEDUP_AUDIT.json"
DATASET_AUDIT = MODEL_OUT / "STAGE_A_DATASET_COMPLETION_AUDIT.json"

TRACK_FEATURES = [
    "observations",
    "track_persistence",
    "path_directed_lateral_motion",
    "box_growth",
    "front_region_occupancy",
    "approximate_ttc_urgency",
    "lane_relative_motion",
    "boundary_crossing",
    "ego_corridor_overlap",
    "road_geometry_reliability",
    "track_persistence_normalized",
    "path_directed_lateral_motion_normalized",
    "box_growth_normalized",
    "front_region_occupancy_normalized",
    "approximate_ttc_urgency_normalized",
    "candidate_score",
]
SEQUENCE_FEATURES = [
    "frame_valid", "witness_observed", "raw_yolo_confidence", "bbox_center_x",
    "bbox_center_y", "bbox_width", "bbox_height", "bbox_area", "bbox_bottom",
    "delta_center_x_per_second", "delta_center_y_per_second", "box_growth_per_second",
    "height_growth_per_second", "front_region_occupancy", "approximate_ttc_urgency",
    "elapsed_fraction", "active_query_track_count", "max_query_raw_yolo_confidence",
]


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


def atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".parquet", dir=path.parent)
    os.close(descriptor)
    try:
        frame.to_parquet(temporary, index=False, engine="pyarrow", compression="zstd")
        with open(temporary, "rb") as handle:
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


def parse_optional_int(value: Any) -> int | None:
    return None if value is None or str(value).strip() == "" else int(float(value))


def temporal_summaries(sequence: np.ndarray, valid_mask: np.ndarray) -> dict[str, float]:
    feature = {name: index for index, name in enumerate(SEQUENCE_FEATURES)}
    valid = valid_mask.astype(bool)
    observed = valid & (sequence[:, feature["witness_observed"]] > 0)
    result: dict[str, float] = {
        "temporal_valid_steps": float(valid.sum()),
        "witness_observed_steps": float(observed.sum()),
        "witness_observation_fraction": float(observed.sum() / max(1, valid.sum())),
    }
    for name in (
        "raw_yolo_confidence", "bbox_center_x", "bbox_center_y", "bbox_width",
        "bbox_height", "bbox_area", "bbox_bottom", "delta_center_x_per_second",
        "delta_center_y_per_second", "box_growth_per_second", "height_growth_per_second",
        "front_region_occupancy", "approximate_ttc_urgency",
    ):
        values = sequence[observed, feature[name]]
        result[f"temporal_{name}_mean"] = float(values.mean()) if len(values) else 0.0
        result[f"temporal_{name}_max"] = float(values.max()) if len(values) else 0.0
        result[f"temporal_{name}_last"] = float(values[-1]) if len(values) else 0.0
    for name in ("active_query_track_count", "max_query_raw_yolo_confidence"):
        values = sequence[valid, feature[name]]
        result[f"temporal_{name}_mean"] = float(values.mean()) if len(values) else 0.0
        result[f"temporal_{name}_max"] = float(values.max()) if len(values) else 0.0
    return result


def prune_affine_redundant_features(
    frame: pd.DataFrame,
    candidates: list[str],
) -> tuple[list[str], dict[str, Any]]:
    """Select a deterministic full-rank feature basis without consulting labels.

    Columns are centered and scaled before a greedy rank test.  Centering makes
    the test intercept-aware: constants and any exact affine combination of
    earlier, semantically preferred columns are excluded.  The ordering is part
    of the schema so that duplicate representations resolve predictably.
    """
    preferred = [
        "raw_yolo_score",
        "frozen_y8_proxy_score",
        "query_is_q1",
        "class_is_pedestrian",
        "class_is_cyclist",
        "class_is_vehicle",
        "candidate_count",
        "query_class_compatibility",
    ]
    ordered = [name for name in preferred if name in candidates]
    ordered.extend(name for name in candidates if name not in set(ordered))
    retained: list[str] = []
    retained_standardized: list[np.ndarray] = []
    dropped: list[dict[str, Any]] = []
    for name in ordered:
        values = frame[name].to_numpy(dtype=np.float64)
        centered = values - float(values.mean())
        scale = float(np.linalg.norm(centered))
        if scale <= 1e-12:
            dropped.append({"feature": name, "reason": "constant_after_centering"})
            continue
        standardized = centered / scale
        rank_before = (
            int(np.linalg.matrix_rank(np.column_stack(retained_standardized)))
            if retained_standardized else 0
        )
        proposed = retained_standardized + [standardized]
        rank_after = int(np.linalg.matrix_rank(np.column_stack(proposed)))
        if rank_after == rank_before:
            dropped.append({"feature": name, "reason": "exact_affine_dependency_on_earlier_features"})
            continue
        retained.append(name)
        retained_standardized.append(standardized)
    centered_rank = (
        int(np.linalg.matrix_rank(np.column_stack(retained_standardized)))
        if retained_standardized else 0
    )
    design_rank_with_intercept = int(np.linalg.matrix_rank(np.column_stack([
        np.ones(len(frame), dtype=np.float64),
        *retained_standardized,
    ])))
    if centered_rank != len(retained) or design_rank_with_intercept != len(retained) + 1:
        raise RuntimeError("Aggregate redundancy pruning failed to produce an intercept-aware full-rank basis")
    audit = {
        "method": "label_free_greedy_centered_scaled_matrix_rank",
        "labels_consulted": False,
        "ordering_policy": "semantic_preference_then_dataset_column_order",
        "semantic_preference": preferred,
        "candidate_feature_count": len(ordered),
        "retained_feature_count": len(retained),
        "dropped_feature_count": len(dropped),
        "retained_centered_rank": centered_rank,
        "design_rank_with_intercept": design_rank_with_intercept,
        "dropped_features": dropped,
    }
    return retained, audit


def event_group_map(groups: pd.DataFrame) -> dict[tuple[str, str, str, int], str]:
    result: dict[tuple[str, str, str, int], str] = {}
    for row in groups.to_dict("records"):
        for token in str(row["unit_ids"]).split("|"):
            key = (str(row["source_dataset"]), str(row["session_id"]), str(row["query_id"]), int(token))
            if key in result:
                raise RuntimeError("A semantic unit belongs to multiple K3 event groups")
            result[key] = str(row["event_group_id"])
    return result


def build_frame() -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any], dict[str, Any]]:
    temporal_audit = load_json(TEMPORAL_AUDIT)
    oracle_complete = load_json(ORACLE_COMPLETE)
    if temporal_audit.get("status") != "PASS":
        raise RuntimeError("Temporal materialization audit is not PASS")
    if oracle_complete.get("status") != "COMPLETE_COMMIT":
        raise RuntimeError("Stage-A oracle completion marker is absent or invalid")
    labels = pd.read_csv(LABELS, keep_default_na=False)
    calls = pd.read_csv(CALLS, keep_default_na=False)
    sample = pd.read_csv(SAMPLE, keep_default_na=False)
    opportunities = pd.read_csv(OPPORTUNITIES, keep_default_na=False)
    scores = pd.read_csv(UNIT_SCORES, keep_default_na=False)
    tracks = pd.read_csv(TRACKS, keep_default_na=False)
    groups = pd.read_csv(GROUPS, keep_default_na=False)
    temporal_index = pd.read_csv(TEMPORAL_INDEX, keep_default_na=False)
    if len(labels) != 192 or labels["verification_key"].nunique() != 192:
        raise RuntimeError("Oracle label semantic universe is not exactly 192 unique keys")
    if len(calls) != 96 or calls["physical_call_id"].nunique() != 96:
        raise RuntimeError("Oracle physical-call universe is not exactly 96")
    if len(temporal_index) != 192 or temporal_index["semantic_sample_id"].nunique() != 192:
        raise RuntimeError("Temporal semantic universe is not exactly 192")
    if set(labels["verification_key"]) != set(temporal_index["semantic_sample_id"]):
        raise RuntimeError("Temporal and oracle semantic identities differ")

    with np.load(TEMPORAL_NPZ, allow_pickle=False) as temporal:
        ids = temporal["semantic_sample_id"].astype(str)
        if list(ids) != temporal_index["semantic_sample_id"].astype(str).tolist():
            raise RuntimeError("Temporal array order is detached from its index")
        sequence_by_id = {
            semantic_id: (temporal["sequences"][index], temporal["valid_mask"][index])
            for index, semantic_id in enumerate(ids)
        }

    opportunity_by_key = opportunities.set_index("verification_key").to_dict("index")
    sample_by_call = sample.set_index("physical_call_id").to_dict("index")
    score_by_key = scores.set_index("verification_key").to_dict("index")
    temporal_by_key = temporal_index.set_index("semantic_sample_id").to_dict("index")
    group_by_key = event_group_map(groups)
    track_by_key: dict[tuple[str, str, str, int, int], dict[str, Any]] = {}
    for row in tracks.to_dict("records"):
        key = (
            str(row["source_dataset"]), str(row["session_id"]), str(row["query_id"]),
            int(row["unit_id"]), int(row["track_id"]),
        )
        if key in track_by_key:
            raise RuntimeError("Duplicate persisted track candidate identity")
        track_by_key[key] = row

    rows: list[dict[str, Any]] = []
    for temporal_row_index, label in enumerate(labels.to_dict("records")):
        key = str(label["verification_key"])
        opportunity = opportunity_by_key[key]
        selected = sample_by_call[label["physical_call_id"]]
        score = score_by_key[key]
        temporal_row = temporal_by_key[key]
        witness = parse_optional_int(label["witness_track_id"])
        track_key = (
            str(label["source_dataset"]), str(label["session_id"]), str(label["query_id"]),
            int(label["unit_id"]), -1 if witness is None else witness,
        )
        track = track_by_key.get(track_key)
        if witness is not None and track is None:
            raise RuntimeError(f"Frozen witness track is missing: {key}")
        if parse_optional_int(opportunity["witness_track_id"]) != witness:
            raise RuntimeError(f"Label and frozen opportunity witness differ: {key}")
        class_id = -1 if track is None else int(track["class_id"])
        label_value = str(label["projected_label"])
        binary = 1.0 if label_value == "positive" else 0.0 if label_value == "negative" else np.nan
        sequence, valid_mask = sequence_by_id[key]
        row: dict[str, Any] = {
            "semantic_sample_id": key,
            "physical_call_id": label["physical_call_id"],
            "source_dataset": label["source_dataset"],
            "session_id": label["session_id"],
            "source_sha256": label["source_sha256"],
            "query_id": label["query_id"],
            "unit_id": int(label["unit_id"]),
            "anchor_id": label["anchor_id"],
            "unit_start_seconds": float(label["unit_start_seconds"]),
            "unit_end_seconds": float(label["unit_end_seconds"]),
            "model_split_role": label["model_split_role"],
            "sampling_stratum": label["sampling_stratum"],
            "verification_key": key,
            "witness_track_id": -1 if witness is None else witness,
            "witness_class_id": class_id,
            "has_witness_track": float(track is not None),
            "event_group_id": group_by_key.get(
                (str(label["source_dataset"]), str(label["session_id"]), str(label["query_id"]), int(label["unit_id"])),
                "",
            ),
            "oracle_projected_label": label_value,
            "label_binary": binary,
            "label_status": label["label_status"],
            "parse_status": label["parse_status"],
            "oracle_confidence": label["confidence"],
            "oracle_generic_label": label["oracle_generic_label"],
            "oracle_generic_involved_object": label["oracle_generic_involved_object"],
            "raw_response_sha256": label["raw_response_sha256"],
            "temporal_row_index": temporal_row_index,
            "raw_yolo_score": float(temporal_row["raw_yolo_score"]),
            "frozen_y8_proxy_score": float(score["unit_score"]),
            "candidate_count": int(score["candidate_count"]),
            "fifo_creation_score": 0.0 if witness is None else 1.0 / (1.0 + witness),
            "query_is_q1": float(label["query_id"] == "Q1"),
            "query_is_q2": float(label["query_id"] == "Q2"),
            "class_is_pedestrian": float(class_id == 0),
            "class_is_cyclist": float(class_id in {1, 3}),
            "class_is_vehicle": float(class_id in {2, 5, 7}),
            "query_class_compatibility": float(
                (label["query_id"] == "Q1" and class_id in {1, 2, 3, 5, 7})
                or (label["query_id"] == "Q2" and class_id in {0, 1, 3})
            ),
        }
        for feature in TRACK_FEATURES:
            row[f"track_{feature}"] = 0.0 if track is None else float(track[feature])
        row.update(temporal_summaries(sequence, valid_mask))
        rows.append(row)
    frame = pd.DataFrame(rows)
    if frame["semantic_sample_id"].duplicated().any() or len(frame) != 192:
        raise RuntimeError("Built dataset contains duplicate or missing semantic samples")
    if frame["physical_call_id"].nunique() != 96:
        raise RuntimeError("Built dataset is detached from physical-call universe")
    if not set(frame["oracle_projected_label"]).issubset({"positive", "negative", "abstain", ""}):
        raise RuntimeError("Built dataset label domain changed")
    if frame.select_dtypes(include=[np.number]).drop(columns=["label_binary"]).isna().any().any():
        raise RuntimeError("Runtime-visible numeric feature contains NaN")

    baseline_features = ["raw_yolo_score", "fifo_creation_score"]
    excluded = [
        "source_dataset", "session_id", "source_sha256", "physical_call_id", "semantic_sample_id",
        "verification_key", "anchor_id", "event_group_id", "raw_response_sha256",
        "oracle_projected_label", "label_binary", "label_status", "parse_status", "oracle_confidence",
        "oracle_generic_label", "oracle_generic_involved_object", "model_split_role", "sampling_stratum",
        "temporal_row_index", "unit_id", "unit_start_seconds", "unit_end_seconds", "witness_track_id",
        "witness_class_id",
    ]
    aggregate_candidates = [
        column for column in frame.columns
        if column not in excluded and column not in baseline_features and pd.api.types.is_numeric_dtype(frame[column])
    ] + ["raw_yolo_score", "frozen_y8_proxy_score"]
    aggregate_candidates = list(dict.fromkeys(aggregate_candidates))
    aggregate_features, redundancy_pruning = prune_affine_redundant_features(frame, aggregate_candidates)
    feature_schema = {
        "schema_id": "MF_PSVR_STAGE_A_FEATURE_SCHEMA_V2",
        "baseline_features": {"B0_raw_yolo": "raw_yolo_score", "B1_fifo_creation": "fifo_creation_score"},
        "aggregate_candidate_features": aggregate_candidates,
        "aggregate_model_features": aggregate_features,
        "aggregate_redundancy_pruning": redundancy_pruning,
        "temporal_model_input": "STAGE_A_TEMPORAL_SEQUENCES.npz: sequences + query_code + witness_class_id",
        "runtime_visible_only": True,
        "identity_or_leakage_columns_excluded": excluded,
        "categorical_identity_policy": "source/session/physical-call/unit/anchor/event-group identifiers are metadata only",
        "object_class_encoding": "aggregate models use has_witness_track plus pedestrian/cyclist/vehicle indicators; raw numeric witness_class_id is metadata-only to avoid imposing ordinal COCO-class geometry; temporal models use a 9-way one-hot class code",
        "raw_yolo_score_semantics": "maximum post-NMS YOLOv8 confidence for a query-eligible class within the unit",
        "frozen_y8_proxy_score_semantics": "pre-label frozen percentile-normalized five-feature heuristic",
    }
    label_schema = {
        "schema_id": "MF_PSVR_STAGE_A_LABEL_SCHEMA_V1",
        "source": "frozen generic physical oracle projected by the preregistered Q1/Q2 actor sets",
        "domain": ["positive", "negative", "abstain", "invalid_parse_empty"],
        "binary_mapping": {"positive": 1, "negative": 0, "abstain": None, "invalid_parse_empty": None},
        "training_rows": "positive and negative only; abstain/invalid retained in dataset and excluded from loss/metrics",
        "track_label_warning": "unit outcome; witness track is pre-label scheduling provenance, not a track-level oracle label",
    }
    dedup = {
        "audit_id": "MF_PSVR_STAGE_A_DEDUP_AUDIT_V1",
        "status": "PASS",
        "semantic_rows": len(frame),
        "unique_verification_keys": frame["verification_key"].nunique(),
        "duplicate_verification_keys": int(frame["verification_key"].duplicated().sum()),
        "physical_calls": frame["physical_call_id"].nunique(),
        "query_rows_per_physical_call_exactly_two": bool((frame.groupby("physical_call_id").size() == 2).all()),
        "physical_repeats_as_extra_semantic_samples": 0,
        "distinct_source_datasets": frame["source_dataset"].nunique(),
        "distinct_source_sessions": frame[["source_dataset", "session_id"]].drop_duplicates().shape[0],
        "positive_event_groups": int((frame["event_group_id"] != "").sum()),
        "heldout_opened": False,
    }
    return frame, feature_schema, label_schema, dedup


def dataset_card(frame: pd.DataFrame, feature_schema: dict[str, Any], dedup: dict[str, Any]) -> str:
    counts = frame.groupby(["query_id", "oracle_projected_label"], dropna=False).size().to_dict()
    split_counts = frame.groupby(["model_split_role", "query_id"]).size().to_dict()
    count_lines = "\n".join(f"- {query}/{label or 'invalid_parse'}: {count}" for (query, label), count in sorted(counts.items()))
    split_lines = "\n".join(f"- {split}/{query}: {count}" for (split, query), count in sorted(split_counts.items()))
    return f"""# MF-PSVR Stage-A candidate-value dataset card

## Scope

- Semantic samples: {len(frame)} query-aligned verification keys from {dedup['physical_calls']} physical generic calls.
- Source datasets: {dedup['distinct_source_datasets']}.
- Source/provider sessions: {dedup['distinct_source_sessions']}.
- One row is one `(source_dataset, session_id, query_id, unit_id)` outcome. Q1/Q2 projections of one physical call are distinct semantic tasks; physical repeats never create rows.

## Label distribution

{count_lines}

## Frozen split coverage

{split_lines}

## Feature provenance

The dataset joins the frozen unit score, pre-label witness-track aggregates, independently materialized raw YOLO confidence and fixed-length trajectories, and the frozen oracle projection. The aggregate model has {len(feature_schema['aggregate_model_features'])} runtime-visible numeric features after a label-free, intercept-aware rank pruning of {feature_schema['aggregate_redundancy_pruning']['candidate_feature_count']} candidates. Source/session/call/unit/anchor/event identifiers and all oracle fields are excluded from model inputs. Raw `witness_class_id` is metadata only; aggregate models use categorical class indicators, while temporal models use a 9-way one-hot code.

## Limitations

- Stage A is deliberately enriched by preregistered strata; its class fraction is not population prevalence.
- All current rows come from one dataset family, so leave-one-dataset-out is unidentifiable at this stage.
- Most provider sessions contribute one unit and no session contributes more than two; exact leave-one-session-out predictions can be pooled, but per-session AUPRC is undefined for a one-row test fold.
- Oracle abstentions and parse failures are retained but excluded from binary training and scoring.
- The witness track is label-blind scheduling provenance. The unit label must not be interpreted as a verified track label.
- Temporal trajectories required a bounded replay of the exact frozen 96 units because the full-pool extractor discarded per-frame observations; no new unit, anchor, label, or oracle call was added.

## Intended use

Train and compare query-conditioned candidate-value ranking models under grouped source/session evaluation before deciding whether to enter the MF-PSVR physical pilot. Do not use this enriched sample to estimate natural-road prevalence.
"""


def write() -> dict[str, Any]:
    frame, feature_schema, label_schema, dedup = build_frame()
    MODEL_OUT.mkdir(parents=True, exist_ok=True)
    atomic_parquet(DATASET, frame)
    atomic_json(FEATURE_SCHEMA, feature_schema)
    atomic_json(LABEL_SCHEMA, label_schema)
    atomic_json(DEDUP_AUDIT, dedup)
    atomic_bytes(DATASET_CARD, dataset_card(frame, feature_schema, dedup).encode("utf-8"))
    audit = {
        "audit_id": "MF_PSVR_STAGE_A_DATASET_COMPLETION_AUDIT_V1",
        "created_at_utc": utc_now(),
        "status": "PASS",
        "semantic_samples": len(frame),
        "binary_training_samples": int(frame["label_binary"].notna().sum()),
        "positive_samples": int((frame["oracle_projected_label"] == "positive").sum()),
        "negative_samples": int((frame["oracle_projected_label"] == "negative").sum()),
        "abstain_samples": int((frame["oracle_projected_label"] == "abstain").sum()),
        "invalid_parse_samples": int((frame["oracle_projected_label"] == "").sum()),
        "source_datasets": frame["source_dataset"].nunique(),
        "source_sessions": frame[["source_dataset", "session_id"]].drop_duplicates().shape[0],
        "aggregate_candidate_features": feature_schema["aggregate_redundancy_pruning"]["candidate_feature_count"],
        "aggregate_retained_features": feature_schema["aggregate_redundancy_pruning"]["retained_feature_count"],
        "aggregate_design_rank_with_intercept": feature_schema["aggregate_redundancy_pruning"]["design_rank_with_intercept"],
        "dataset_sha256": sha256_file(DATASET),
        "dataset_card_sha256": sha256_file(DATASET_CARD),
        "feature_schema_sha256": sha256_file(FEATURE_SCHEMA),
        "label_schema_sha256": sha256_file(LABEL_SCHEMA),
        "dedup_audit_sha256": sha256_file(DEDUP_AUDIT),
        "temporal_sequences_sha256": sha256_file(TEMPORAL_NPZ),
        "builder_source_sha256": sha256_file(Path(__file__)),
        "oracle_completion_hash": load_json(ORACLE_COMPLETE)["complete_hash"],
        "heldout_opened": False,
    }
    audit["audit_hash"] = canonical_hash(audit)
    atomic_json(DATASET_AUDIT, audit)
    return audit


def verify() -> dict[str, Any]:
    if not all(path.is_file() for path in (DATASET, DATASET_CARD, FEATURE_SCHEMA, LABEL_SCHEMA, DEDUP_AUDIT, DATASET_AUDIT)):
        raise RuntimeError("Dataset finalized artifact set is incomplete")
    expected_frame, expected_features, expected_labels, expected_dedup = build_frame()
    observed = pd.read_parquet(DATASET)
    pd.testing.assert_frame_equal(observed, expected_frame, check_dtype=False)
    if load_json(FEATURE_SCHEMA) != expected_features or load_json(LABEL_SCHEMA) != expected_labels:
        raise RuntimeError("Dataset schema does not recompute")
    if load_json(DEDUP_AUDIT) != expected_dedup:
        raise RuntimeError("Dataset dedup audit does not recompute")
    audit = load_json(DATASET_AUDIT)
    payload = {key: value for key, value in audit.items() if key != "audit_hash"}
    if audit.get("audit_hash") != canonical_hash(payload) or audit.get("status") != "PASS":
        raise RuntimeError("Dataset completion audit self-hash is invalid")
    bindings = {
        "dataset_sha256": sha256_file(DATASET),
        "dataset_card_sha256": sha256_file(DATASET_CARD),
        "feature_schema_sha256": sha256_file(FEATURE_SCHEMA),
        "label_schema_sha256": sha256_file(LABEL_SCHEMA),
        "dedup_audit_sha256": sha256_file(DEDUP_AUDIT),
        "temporal_sequences_sha256": sha256_file(TEMPORAL_NPZ),
        "builder_source_sha256": sha256_file(Path(__file__)),
    }
    if any(audit.get(key) != value for key, value in bindings.items()):
        raise RuntimeError("Dataset completion audit artifact binding changed")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["build", "verify"])
    args = parser.parse_args()
    result = write() if args.stage == "build" else verify()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
