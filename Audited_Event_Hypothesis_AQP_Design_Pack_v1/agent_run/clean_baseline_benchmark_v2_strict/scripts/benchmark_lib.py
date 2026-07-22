#!/usr/bin/env python3
"""Shared, label-isolated materialization and evaluation for benchmark v1."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


EVENT_SEGMENT_COLUMNS = [
    "benchmark_id", "run_id", "method", "method_variant", "seed",
    "horizon_budget", "event_id", "start_time", "core_start_time",
    "core_end_time", "end_time", "anchor_unit_ids", "evidence_unit_ids",
    "num_positive_anchors", "num_negative_barriers", "verification_state",
    "confidence", "returned_seconds", "materializer", "materializer_config_hash",
]

EVENT_MATCH_COLUMNS = [
    "benchmark_id", "run_id", "method", "method_variant", "seed",
    "horizon_budget", "predicted_event_id", "reference_event_id", "matched",
    "match_type", "overlap_any", "temporal_iou", "anchor_covered",
    "boundary_start_error", "boundary_end_error", "overmerge_count",
    "oversplit_count", "match_score",
]

METRIC_COLUMNS = [
    "benchmark_id", "run_id", "method", "method_variant", "seed",
    "horizon_budget", "metric_name", "metric_value", "metric_scope",
    "reference_type", "evaluator_hash",
]


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_ids(value: object) -> list[int]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    for delimiter in ["|", ",", ";"]:
        text = text.replace(delimiter, " ")
    out = []
    for token in text.split():
        try:
            out.append(int(float(token)))
        except ValueError:
            continue
    return sorted(set(out))


def temporal_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0.0


def overlaps(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    return min(a_end, b_end) > max(a_start, b_start)


def materialize_from_trace(
    trace: pd.DataFrame,
    units: pd.DataFrame,
    run_meta: dict,
    materializer: str,
    config: dict,
) -> pd.DataFrame:
    """Build events using queried observations only.

    original_k3 permits one unqueried unit between positive anchors, unless a
    queried negative occupies the bridge. k3_bridge_safe only joins directly
    adjacent queried-positive units, eliminating unverified bridges.
    """
    if trace.empty:
        return pd.DataFrame(columns=EVENT_SEGMENT_COLUMNS)
    labels = trace.set_index("unit_id")["oracle_label_after_query"].astype(str).str.lower()
    positives = sorted(int(x) for x in labels[labels == "positive"].index.unique())
    negatives = set(int(x) for x in labels[labels == "negative"].index.unique())
    if not positives:
        return pd.DataFrame(columns=EVENT_SEGMENT_COLUMNS)
    unit_by_id = units.set_index("unit_id")
    g_max = int(config.get("g_max", 1))
    core_cap = float(config.get("d_core_max", 40.0))
    seg_cap = float(config.get("d_seg_max", 60.0))
    groups: list[list[int]] = []
    current = [positives[0]]
    for uid in positives[1:]:
        left = current[-1]
        bridge_ids = set(range(left + 1, uid))
        no_negative_barrier = not bool(bridge_ids & negatives)
        if materializer == "original_k3":
            bridge_ok = (uid - left - 1) <= g_max and no_negative_barrier
        elif materializer == "k3_bridge_safe":
            bridge_ok = uid == left + 1 and no_negative_barrier
        else:
            raise ValueError(f"Unknown materializer: {materializer}")
        proposed_start = float(unit_by_id.loc[current[0], "start_time"])
        proposed_end = float(unit_by_id.loc[uid, "end_time"])
        duration_ok = proposed_end - proposed_start <= min(core_cap, seg_cap) + 1e-9
        if bridge_ok and duration_ok:
            current.append(uid)
        else:
            groups.append(current)
            current = [uid]
    groups.append(current)

    materializer_hash = canonical_hash({"name": materializer, **config})
    rows = []
    for idx, anchors in enumerate(groups):
        start = float(unit_by_id.loc[min(anchors), "start_time"])
        end = float(unit_by_id.loc[max(anchors), "end_time"])
        inside_negatives = sorted(n for n in negatives if min(anchors) < n < max(anchors))
        rows.append({
            **run_meta,
            "event_id": f"{run_meta['run_id']}_event_{idx:04d}",
            "start_time": start,
            "core_start_time": start,
            "core_end_time": end,
            "end_time": end,
            "anchor_unit_ids": "|".join(map(str, anchors)),
            "evidence_unit_ids": "|".join(map(str, sorted(set(anchors) | set(inside_negatives)))),
            "num_positive_anchors": len(anchors),
            "num_negative_barriers": len(inside_negatives),
            "verification_state": "oracle_confirmed",
            "confidence": 1.0,
            "returned_seconds": end - start,
            "materializer": materializer,
            "materializer_config_hash": materializer_hash,
        })
    return pd.DataFrame(rows, columns=EVENT_SEGMENT_COLUMNS)


def canonicalize_native_segments(
    native: pd.DataFrame,
    trace: pd.DataFrame,
    units: pd.DataFrame,
    run_meta: dict,
    materializer_name: str,
    materializer_config: dict,
) -> pd.DataFrame:
    if native.empty:
        return pd.DataFrame(columns=EVENT_SEGMENT_COLUMNS)
    # Frozen UnitTable uses unit_id as the canonical frame/window index. Some
    # repository adapters call the same value frame_idx in source_frame_ids.
    frame_key = "frame_idx" if "frame_idx" in units.columns else "unit_id"
    unit_by_frame = dict(zip(units[frame_key].astype(int), units["unit_id"].astype(int)))
    positive = set(
        trace.loc[
            trace["oracle_label_after_query"].astype(str).str.lower() == "positive", "unit_id"
        ].astype(int)
    )
    negative = set(
        trace.loc[
            trace["oracle_label_after_query"].astype(str).str.lower() == "negative", "unit_id"
        ].astype(int)
    )
    cfg_hash = canonical_hash({"name": materializer_name, **materializer_config})
    rows = []
    for idx, row in native.reset_index(drop=True).iterrows():
        raw_ids = read_ids(row.get("source_frame_ids", ""))
        ids = sorted({unit_by_frame.get(x, x) for x in raw_ids})
        anchor_ids = sorted(set(ids) & positive)
        if not ids:
            mask = (units["end_time"] > float(row["start_time"])) & (units["start_time"] < float(row["end_time"]))
            ids = units.loc[mask, "unit_id"].astype(int).tolist()
            anchor_ids = sorted(set(ids) & positive)
        start = float(row["start_time"])
        end = float(row["end_time"])
        rows.append({
            **run_meta,
            "event_id": f"{run_meta['run_id']}_event_{idx:04d}",
            "start_time": start,
            "core_start_time": start,
            "core_end_time": end,
            "end_time": end,
            "anchor_unit_ids": "|".join(map(str, anchor_ids)),
            "evidence_unit_ids": "|".join(map(str, ids)),
            "num_positive_anchors": len(anchor_ids),
            "num_negative_barriers": len(set(ids) & negative),
            "verification_state": str(row.get("verification_state", "native")),
            "confidence": float(row.get("segment_score", 0.0)),
            "returned_seconds": end - start,
            "materializer": materializer_name,
            "materializer_config_hash": cfg_hash,
        })
    return pd.DataFrame(rows, columns=EVENT_SEGMENT_COLUMNS)


def match_events(
    predicted: pd.DataFrame,
    reference: pd.DataFrame,
    run_meta: dict,
) -> pd.DataFrame:
    preds = predicted.reset_index(drop=True)
    refs = reference.reset_index(drop=True)
    p_count, r_count = len(preds), len(refs)
    overlap_matrix = np.zeros((p_count, r_count), dtype=float)
    iou_matrix = np.zeros((p_count, r_count), dtype=float)
    for i, p in preds.iterrows():
        for j, r in refs.iterrows():
            if overlaps(float(p.start_time), float(p.end_time), float(r.start_time), float(r.end_time)):
                overlap_matrix[i, j] = 1.0
                iou_matrix[i, j] = temporal_iou(float(p.start_time), float(p.end_time), float(r.start_time), float(r.end_time))
    # Cardinality dominates IoU: overlap-any is the frozen primary rule.
    score = overlap_matrix * 1000.0 + iou_matrix
    assigned_p: set[int] = set()
    assigned_r: set[int] = set()
    matches: list[tuple[int, int]] = []
    if p_count and r_count:
        pi, rj = linear_sum_assignment(-score)
        for i, j in zip(pi, rj):
            if overlap_matrix[i, j] > 0:
                assigned_p.add(int(i)); assigned_r.add(int(j)); matches.append((int(i), int(j)))
    pred_overlap_counts = overlap_matrix.sum(axis=1) if p_count else np.array([])
    ref_overlap_counts = overlap_matrix.sum(axis=0) if r_count else np.array([])
    rows = []
    for i, j in matches:
        p, r = preds.iloc[i], refs.iloc[j]
        anchors = read_ids(p.get("anchor_unit_ids", ""))
        ref_units = set(read_ids(r.get("source_unit_ids", "")))
        rows.append({
            **run_meta,
            "predicted_event_id": p.event_id,
            "reference_event_id": r.reference_event_id,
            "matched": True,
            "match_type": "overlap_any_one_to_one",
            "overlap_any": True,
            "temporal_iou": float(iou_matrix[i, j]),
            "anchor_covered": bool(set(anchors) & ref_units),
            "boundary_start_error": abs(float(p.start_time) - float(r.start_time)),
            "boundary_end_error": abs(float(p.end_time) - float(r.end_time)),
            "overmerge_count": max(0, int(pred_overlap_counts[i]) - 1),
            "oversplit_count": max(0, int(ref_overlap_counts[j]) - 1),
            "match_score": float(1000.0 + iou_matrix[i, j]),
        })
    for i in sorted(set(range(p_count)) - assigned_p):
        p = preds.iloc[i]
        rows.append({
            **run_meta, "predicted_event_id": p.event_id, "reference_event_id": "",
            "matched": False, "match_type": "unmatched_prediction", "overlap_any": False,
            "temporal_iou": 0.0, "anchor_covered": False, "boundary_start_error": math.nan,
            "boundary_end_error": math.nan, "overmerge_count": max(0, int(pred_overlap_counts[i]) - 1),
            "oversplit_count": 0, "match_score": 0.0,
        })
    for j in sorted(set(range(r_count)) - assigned_r):
        r = refs.iloc[j]
        rows.append({
            **run_meta, "predicted_event_id": "", "reference_event_id": r.reference_event_id,
            "matched": False, "match_type": "unmatched_reference", "overlap_any": False,
            "temporal_iou": 0.0, "anchor_covered": False, "boundary_start_error": math.nan,
            "boundary_end_error": math.nan, "overmerge_count": 0,
            "oversplit_count": max(0, int(ref_overlap_counts[j]) - 1), "match_score": 0.0,
        })
    return pd.DataFrame(rows, columns=EVENT_MATCH_COLUMNS)


def compute_metrics(
    predicted: pd.DataFrame,
    reference: pd.DataFrame,
    matches: pd.DataFrame,
    run_meta: dict,
    evaluator_hash: str,
    reference_type: str = "VLM_DEFINED_PSEUDO_ORACLE",
) -> pd.DataFrame:
    matched = matches[matches["matched"].astype(bool)] if not matches.empty else matches
    tp = len(matched)
    n_pred = len(predicted)
    n_ref = len(reference)
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_ref if n_ref else math.nan
    f1 = 2 * precision * recall / (precision + recall) if n_ref and precision + recall > 0 else 0.0
    ious = matched["temporal_iou"].astype(float) if tp else pd.Series(dtype=float)
    returned = float(predicted["returned_seconds"].sum()) if n_pred else 0.0
    ref_duration = float((reference["end_time"] - reference["start_time"]).sum()) if n_ref else math.nan
    values = {
        "event_precision": precision,
        "event_recall": recall,
        "event_f1": f1,
        "event_count_error": abs(n_pred - n_ref),
        "predicted_event_count": n_pred,
        "reference_event_count": n_ref,
        "tiou_03": float((ious >= 0.3).sum() / n_ref) if n_ref else math.nan,
        "tiou_05": float((ious >= 0.5).sum() / n_ref) if n_ref else math.nan,
        "matched_mean_iou": float(ious.mean()) if tp else 0.0,
        "overmerge": float(matches["overmerge_count"].sum()) if not matches.empty else 0.0,
        "oversplit": float(matches["oversplit_count"].sum()) if not matches.empty else 0.0,
        "returned_seconds": returned,
        "overcoverage_ratio": returned / ref_duration if n_ref and ref_duration > 0 else math.nan,
        "event_recall_per_returned_minute": recall / (returned / 60.0) if returned > 0 and n_ref else 0.0,
    }
    rows = [{
        **run_meta,
        "metric_name": name,
        "metric_value": value,
        "metric_scope": "single_video",
        "reference_type": reference_type,
        "evaluator_hash": evaluator_hash,
    } for name, value in values.items()]
    return pd.DataFrame(rows, columns=METRIC_COLUMNS)


def evaluate_events(
    predicted: pd.DataFrame,
    reference: pd.DataFrame,
    run_meta: dict,
    evaluator_hash: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    matches = match_events(predicted, reference, run_meta)
    metrics = compute_metrics(predicted, reference, matches, run_meta, evaluator_hash)
    return matches, metrics
