#!/usr/bin/env python3
"""mab_cpu_gate common engine: loaders, C1 materializer, matching, metrics.

CPU-only. Consumes ONLY frozen cached artifacts. No model inference.
Faithful mirror of:
  - scripts/analyze_p0_v3_materializer_mechanisms.py::generic_events (C1)
  - src/garc_eval/accelerated_event_query/matching.py (strict-overlap 1:1)
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"

VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
QUERY_VULN = "Q_VULNERABLE_ROAD_USER_CONFLICT_V1"
QUERY_DRIVER = "Q_DRIVER_RESPONSE_V1"
UNIT_SEC = 10.0
C1_GAP_SEC = 10.0
BUDGETS = (5, 10, 20, 50, 80, 100)

# ---------------------------------------------------------------- loaders

def load_unit_grid() -> dict[str, list[dict]]:
    """video -> list of {unit_id, candidate_id, start_time, end_time} (10s grid)."""
    grid = {}
    with open(OUT / "accelerated_event_query_v1/video_manifests/frozen_unit_grid_v1.csv", newline="") as f:
        for r in csv.DictReader(f):
            grid.setdefault(r["video_id"], []).append({
                "unit_id": int(r["unit_id"]),
                "candidate_id": r["candidate_id"],
                "start_time": float(r["start_time"]),
                "end_time": float(r["end_time"]),
            })
    for v in grid:
        grid[v].sort(key=lambda u: u["unit_id"])
    return grid


def load_qwen32_labels() -> dict[str, str]:
    """candidate_id -> label for Q_VULNERABLE full grid (1475).

    Raw records carry candidate_id like 'VIDEO::VIDEO_u0000'; normalize to
    the unit-grid form 'VIDEO_u0000'.
    """
    labels = {}
    raw = OUT / "gvaqp_long_horizon_p1_p3_v1/qwen32_oracle/raw"
    for p in sorted(raw.glob("*.json")):
        d = json.loads(p.read_text())
        cid = d["candidate_id"].split("::")[-1]
        labels[cid] = d["label"]
    return labels


def load_proxy_a_scores() -> dict[str, float]:
    """Reconstruct V3 proxy score from frozen raw unit detections.

    Frozen scoring function (scripts/finalize_v3_prospective_scan_proxy.py):
        score = 0.5*min(det_count,20)/20 + 0.5*max_conf
    Validated: per-video min/mean/max match PROXY_REGIME_MANIFEST R0 exactly.
    """
    scores = {}
    for vid in VIDEOS:
        p = OUT / f"v3_scan_proxy_preregistration_v1/frozen_raw/{vid}/raw_unit_detections.jsonl"
        with open(p) as f:
            for line in f:
                d = json.loads(line)
                score = 0.5 * min(int(d["det_count"]), 20) / 20.0 + 0.5 * float(d["max_conf"])
                scores[d["unit_id"]] = score
    return scores


def load_seal_labels() -> dict[str, str]:
    """V10 multi-seal authoritative labels (Q_DRIVER, 21 units only)."""
    labels = {}
    for p in (OUT / "v10_multiseal_reference_v1/seals").glob("*/raw/*.json"):
        d = json.loads(p.read_text())
        labels[d["unit_id"]] = d["authoritative_label"]
    return labels


def load_trace_labels() -> dict[str, str]:
    """Union of queried-unit labels from P2 TRACE_MANIFEST (both queries)."""
    labels = {}
    with open(OUT / "p2_query_policy_novelty_killer_v1/TRACE_MANIFEST.csv", newline="") as f:
        for r in csv.DictReader(f):
            units = json.loads(r["queried_unit_ids_json"])
            outs = json.loads(r["oracle_outcomes_json"])
            for u, o in zip(units, outs):
                labels.setdefault(u, o)
    return labels


def load_p2_manifest() -> list[dict]:
    with open(OUT / "p2_query_policy_novelty_killer_v1/TRACE_MANIFEST.csv", newline="") as f:
        return list(csv.DictReader(f))


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- materializer

@dataclass(frozen=True)
class EventRecord:
    event_id: str
    query_id: str
    video_id: str
    start_time: float
    end_time: float
    confidence: float
    kind: str
    source_unit_ids: tuple
    materializer: str


def c1_materialize(video: str, query: str, unit_intervals: Sequence[tuple[str, float, float]],
                   prefix: str = "c1") -> list[EventRecord]:
    """Gap-only C1: greedy chain merge when adjacent gap <= 10s (frozen semantics)."""
    pos = sorted([(u, s, e) for u, s, e in unit_intervals], key=lambda x: (x[1], x[2], x[0]))
    if not pos:
        return []
    groups = [[pos[0]]]
    for right in pos[1:]:
        left = groups[-1][-1]
        gap = max(0.0, right[1] - left[2])
        if gap <= C1_GAP_SEC:
            groups[-1].append(right)
        else:
            groups.append([right])
    out = []
    for i, g in enumerate(groups):
        token = sha256_text(json.dumps({"v": "C1_gap_limited", "video": video, "src": [x[0] for x in g]}, sort_keys=True))[:16]
        out.append(EventRecord(
            f"mech_C1_gap_limited_{token}", query, video,
            min(x[1] for x in g), max(x[2] for x in g), 1.0, "VERIFIED_EVENT",
            tuple(x[0] for x in g), "C1_gap_limited"))
    return out


# ---------------------------------------------------------------- matching

def temporal_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0.0


def match_events(predicted: Sequence[EventRecord], reference: Sequence[EventRecord],
                 minimum_tiou: float = 0.0, boundary_tolerance_sec: float = 0.0):
    """Strict positive overlap eligibility; 1:1 max-cardinality then max tIoU.

    Vectorized over (n_pred x n_ref) — identical semantics to the python-loop
    version (validated 252/252 against P2 TRACE_MANIFEST before vectorization).
    """
    if not predicted or not reference:
        return []
    sp = np.array([e.start_time for e in predicted], dtype=float)
    ep = np.array([e.end_time for e in predicted], dtype=float)
    sr = np.array([e.start_time for e in reference], dtype=float)
    er = np.array([e.end_time for e in reference], dtype=float)
    inter = np.maximum(0.0, np.minimum(ep[:, None], er[None, :]) - np.maximum(sp[:, None], sr[None, :]))
    union = np.maximum(ep[:, None], er[None, :]) - np.minimum(sp[:, None], sr[None, :])
    iou = np.where(union > 0, inter / np.where(union > 0, union, 1.0), 0.0)
    eligible = iou > minimum_tiou
    if boundary_tolerance_sec > 0:
        eligible |= ((np.abs(sp[:, None] - sr[None, :]) <= boundary_tolerance_sec)
                     & (np.abs(ep[:, None] - er[None, :]) <= boundary_tolerance_sec))
    score = eligible.astype(float) * 1_000_000.0 + iou
    rows = []
    for i, j in zip(*linear_sum_assignment(-score)):
        if eligible[i, j]:
            rows.append((int(i), int(j), float(iou[i, j])))
    return sorted(rows, key=lambda x: (x[0], x[1]))


def summarize_matches(n_pred: int, n_ref: int, n_matched: int) -> dict:
    precision = n_matched / n_pred if n_pred else 0.0
    recall = n_matched / n_ref if n_ref else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"EventPrecision": precision, "EventRecall": recall, "EventF1": f1,
            "TP": n_matched, "FP": n_pred - n_matched, "FN": n_ref - n_matched}


def event_f1(predicted: Sequence[EventRecord], reference: Sequence[EventRecord]) -> dict:
    matches = match_events(predicted, reference)
    return summarize_matches(len(predicted), len(reference), len(matches))


def any_time_auc(f1_by_budget: Sequence[tuple[int, float]]) -> float:
    """Trapezoidal AUC of EventF1 vs budget, normalized by budget range (0..Bmax)."""
    xs = [0.0] + [float(b) for b, _ in f1_by_budget]
    ys = [0.0] + [f for _, f in f1_by_budget]
    auc = sum((ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i]) / 2.0 for i in range(len(xs) - 1))
    return auc / xs[-1] if xs[-1] > 0 else 0.0
