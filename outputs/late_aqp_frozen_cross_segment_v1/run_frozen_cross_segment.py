#!/usr/bin/env python3
"""
Frozen Cross-Segment Validation + Repair Trace for LATE-AQP.

Freezes a single LATE-AQP configuration and runs B6 / B7 / Ours on the dev
segment plus 2-3 unseen segments.  Logs per-call repair trace for Ours and
writes all required cross-segment reports.

No new VLM/YOLO/GPU/API calls.  No modification of existing labels.
"""
from __future__ import annotations

import csv
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "outputs" / "late_aqp_frozen_cross_segment_v1"
OUT.mkdir(parents=True, exist_ok=True)

BIN_SIZE = 10.0
BUDGETS = [5, 10, 20, 40, 80, 120]
SEEDS = [0, 1, 2, 3, 4]
RANDOM_SEED_BASE = 20260705

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FULL_EVENTS_PATH = ROOT / "experiments" / "v13" / "v13_8_full_oracle" / "tables" / "center10_vlm_oracle_events.csv"
DEV_EVENTS_PATH = ROOT / "src" / "garc_eval" / "outputs" / "clean_interval_aqp_full_reference_v2_clean_no_leak" / "reference_events.csv"
DEV_GRID_PATH = ROOT / "outputs" / "exsample_aware_replay" / "atomic_grid_10s.csv"
PROXY_SCORES_PATH = ROOT / "experiments" / "roadclip_budget_v2" / "roadclip_budget_v2" / "proxy_scores.csv"

# ---------------------------------------------------------------------------
# Segment definitions (must match frozen_config.yaml)
# ---------------------------------------------------------------------------
SEGMENTS = [
    {"segment_id": "realcartest_2000_3200", "video_id": "realcartest", "time_start": 2000.0, "time_end": 3200.0, "is_dev": True, "density_regime": "dev"},
    {"segment_id": "realcartest_1630_2000", "video_id": "realcartest", "time_start": 1630.0, "time_end": 2000.0, "is_dev": False, "density_regime": "low"},
    {"segment_id": "realcartest_3200_3830", "video_id": "realcartest", "time_start": 3200.0, "time_end": 3830.0, "is_dev": False, "density_regime": "medium"},
    {"segment_id": "realcartest_0_1570", "video_id": "realcartest", "time_start": 0.0, "time_end": 1570.0, "is_dev": False, "density_regime": "high"},
]


def load_full_events() -> pd.DataFrame:
    df = pd.read_csv(FULL_EVENTS_PATH)
    df = df.rename(columns={"event_start": "t_start", "event_end": "t_end", "event_duration": "duration"})
    return df


def load_dev_events() -> pd.DataFrame:
    df = pd.read_csv(DEV_EVENTS_PATH)
    df["duration"] = df["t_end"] - df["t_start"]
    return df


def load_proxy_scores() -> pd.DataFrame:
    df = pd.read_csv(PROXY_SCORES_PATH)
    df = df.rename(columns={"start_time": "t_start", "end_time": "t_end", "score_count": "score"})
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)
    return df


def load_dev_grid() -> pd.DataFrame:
    df = pd.read_csv(DEV_GRID_PATH)
    df["is_positive"] = df["label"] == "positive"
    df["event_id"] = df["event_id"].fillna("").astype(str)
    return df


def build_segment_grid(seg: dict, full_events: pd.DataFrame, proxy_scores: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return (grid_df, ref_events_df) for a segment."""
    t0, t1 = seg["time_start"], seg["time_end"]
    duration = t1 - t0
    n_bins = int(math.ceil(duration / BIN_SIZE))

    if seg["is_dev"]:
        # Use existing dev grid directly (already relative to 2000 s).
        grid = load_dev_grid().copy()
        grid = grid[grid["t_start"] < duration].reset_index(drop=True)
        grid["bin_idx"] = np.arange(len(grid))
        grid["local_t_start"] = grid["t_start"]
        grid["local_t_end"] = grid["t_end"].clip(upper=duration)
        ref = load_dev_events().copy()
    else:
        bins = []
        for i in range(n_bins):
            bs = i * BIN_SIZE
            be = min(bs + BIN_SIZE, duration)
            bins.append({"bin_idx": i, "local_t_start": bs, "local_t_end": be})
        grid = pd.DataFrame(bins)

        # Events overlapping segment -> convert to local time.
        ev_overlap = full_events[
            (full_events["t_end"] > t0) & (full_events["t_start"] < t1)
        ].copy()
        ev_overlap["t_start"] = ev_overlap["t_start"].clip(lower=t0) - t0
        ev_overlap["t_end"] = ev_overlap["t_end"].clip(upper=t1) - t0
        ev_overlap["duration"] = ev_overlap["t_end"] - ev_overlap["t_start"]
        ref = ev_overlap.reset_index(drop=True)

        # Labels per bin.
        labels = []
        event_ids = []
        for _, b in grid.iterrows():
            bs, be = b["local_t_start"], b["local_t_end"]
            best_eid = ""
            best_ov = 0.0
            is_pos = False
            for _, ev in ref.iterrows():
                inter = max(0.0, min(be, ev["t_end"]) - max(bs, ev["t_start"]))
                if inter > 0:
                    is_pos = True
                    if inter > best_ov:
                        best_ov = inter
                        best_eid = ev["event_id"]
            labels.append("positive" if is_pos else "negative")
            event_ids.append(best_eid)
        grid["label"] = labels
        grid["is_positive"] = grid["label"] == "positive"
        grid["event_id"] = event_ids

        # Prior scores from proxy_scores.
        scores_max = []
        scores_mean = []
        for _, b in grid.iterrows():
            bs_abs = t0 + b["local_t_start"]
            be_abs = t0 + b["local_t_end"]
            over = proxy_scores[
                (proxy_scores["t_start"] < be_abs) & (proxy_scores["t_end"] > bs_abs)
            ]
            if len(over) > 0:
                scores_max.append(float(over["score"].max()))
                scores_mean.append(float(over["score"].mean()))
            else:
                scores_max.append(0.0)
                scores_mean.append(0.0)
        grid["prior_score_max"] = scores_max
        grid["prior_score_mean"] = scores_mean

    grid["t_start"] = grid["local_t_start"]
    grid["t_end"] = grid["local_t_end"]
    ref["event_type"] = ref["duration"].apply(lambda d: "long_interval" if d >= 1.0 else "point_anchor")
    return grid, ref


def event_overlaps_bin(ev: pd.Series, bs: float, be: float) -> bool:
    return ev["t_start"] < be and ev["t_end"] > bs


def merge_bins(grid: pd.DataFrame, bin_indices: List[int]) -> pd.DataFrame:
    """Merge a set of bin indices into contiguous intervals."""
    if not bin_indices:
        return pd.DataFrame(columns=["t_start", "t_end", "duration", "bin_indices"])
    sorted_bins = sorted(set(bin_indices))
    intervals = []
    cur_bins = [sorted_bins[0]]
    cur_start = float(grid.loc[grid["bin_idx"] == sorted_bins[0], "t_start"].iloc[0])
    cur_end = float(grid.loc[grid["bin_idx"] == sorted_bins[0], "t_end"].iloc[0])
    for b in sorted_bins[1:]:
        b_start = float(grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0])
        b_end = float(grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0])
        if abs(b_start - cur_end) < 1e-6:
            cur_bins.append(b)
            cur_end = b_end
        else:
            intervals.append({"t_start": cur_start, "t_end": cur_end, "duration": cur_end - cur_start, "bin_indices": cur_bins.copy()})
            cur_bins = [b]
            cur_start, cur_end = b_start, b_end
    intervals.append({"t_start": cur_start, "t_end": cur_end, "duration": cur_end - cur_start, "bin_indices": cur_bins.copy()})
    return pd.DataFrame(intervals)


def compute_metrics(selected_bins: List[int], grid: pd.DataFrame, ref: pd.DataFrame) -> Dict:
    selected_bins = sorted(set(selected_bins))
    selected_grid = grid[grid["bin_idx"].isin(selected_bins)]

    # Durations.
    total_selected_duration = selected_grid["t_end"].sum() - selected_grid["t_start"].sum()
    positive_overlap = 0.0
    for _, b in selected_grid.iterrows():
        bs, be = b["t_start"], b["t_end"]
        for _, ev in ref.iterrows():
            inter = max(0.0, min(be, ev["t_end"]) - max(bs, ev["t_start"]))
            positive_overlap += inter
    fp_duration = total_selected_duration - positive_overlap
    selected_precision = positive_overlap / total_selected_duration if total_selected_duration > 0 else 0.0

    # Positive bins / duplicate rate.
    pos_sel = selected_grid[selected_grid["is_positive"]]
    n_pos_bins = len(pos_sel)
    pos_events_hit = set()
    for _, b in pos_sel.iterrows():
        if b["event_id"]:
            pos_events_hit.add(b["event_id"])
    duplicate_rate = (n_pos_bins - len(pos_events_hit)) / max(1, len(pos_events_hit))

    # Merge positive intervals for fragmentation.
    pos_merged = merge_bins(grid, pos_sel["bin_idx"].tolist())

    # Per-event metrics.
    all_merged = merge_bins(grid, selected_bins)
    hit_event_ids = set()
    complete_hits = 0
    iou_03 = 0
    iou_05 = 0
    ious = []
    long_hit = set()
    point_hit = set()
    for _, ev in ref.iterrows():
        ev_hit = False
        best_iou = 0.0
        contained = False
        for _, iv in all_merged.iterrows():
            inter = max(0.0, min(iv["t_end"], ev["t_end"]) - max(iv["t_start"], ev["t_start"]))
            if inter > 0:
                ev_hit = True
                union = max(iv["t_end"], ev["t_end"]) - min(iv["t_start"], ev["t_start"])
                iou = inter / union if union > 0 else 0.0
                best_iou = max(best_iou, iou)
                if iv["t_start"] <= ev["t_start"] + 1e-6 and iv["t_end"] >= ev["t_end"] - 1e-6:
                    contained = True
        ious.append(best_iou)
        if ev_hit:
            hit_event_ids.add(ev["event_id"])
            if ev["event_type"] == "long_interval":
                long_hit.add(ev["event_id"])
            else:
                point_hit.add(ev["event_id"])
            if best_iou >= 0.3:
                iou_03 += 1
            if best_iou >= 0.5:
                iou_05 += 1
            if contained:
                complete_hits += 1

    n_ref = len(ref)
    n_long = len(ref[ref["event_type"] == "long_interval"])
    n_point = n_ref - n_long

    metrics = {
        "event_recall": len(hit_event_ids) / n_ref if n_ref else 0.0,
        "long_event_recall": len(long_hit) / n_long if n_long else float("nan"),
        "point_anchor_recall": len(point_hit) / n_point if n_point else float("nan"),
        "selected_total_duration": total_selected_duration,
        "positive_duration_overlap": positive_overlap,
        "false_positive_duration": fp_duration,
        "selected_precision": selected_precision,
        "complete_event_coverage": complete_hits / n_ref if n_ref else 0.0,
        "boundary_iou_03": iou_03 / n_ref if n_ref else 0.0,
        "boundary_iou_05": iou_05 / n_ref if n_ref else 0.0,
        "duplicate_rate": duplicate_rate,
        "fragmentation_rate": len(pos_merged) / max(1, len(hit_event_ids)),
        "num_selected_bins": len(selected_bins),
        "num_selected_intervals": len(all_merged),
        "num_events": n_ref,
        "num_long_events": n_long,
        "num_point_anchor_events": n_point,
    }
    return metrics


# ---------------------------------------------------------------------------
# B6 / B7 baselines
# ---------------------------------------------------------------------------
def get_event_at_bin(grid: pd.DataFrame, b: int) -> Optional[str]:
    row = grid[grid["bin_idx"] == b]
    if row.empty:
        return None
    eid = row.iloc[0]["event_id"]
    if pd.isna(eid) or eid == "":
        return None
    return str(eid)


def get_label_at_bin(grid: pd.DataFrame, b: int) -> str:
    row = grid[grid["bin_idx"] == b]
    if row.empty:
        return "negative"
    return str(row.iloc[0]["label"])


def get_prior_at_bin(grid: pd.DataFrame, b: int) -> float:
    row = grid[grid["bin_idx"] == b]
    if row.empty:
        return 0.0
    return float(row.iloc[0]["prior_score_max"])


def run_b6(grid: pd.DataFrame, budget: int, chunk_size_s: int, rng: np.random.Generator) -> List[int]:
    n_bins = len(grid)
    bins_per_chunk = max(1, chunk_size_s // int(BIN_SIZE))
    n_chunks = int(math.ceil(n_bins / bins_per_chunk))
    sampled: Set[int] = set()
    n_c = np.zeros(n_chunks, dtype=int)
    discovered_events: List[Dict[str, int]] = [dict() for _ in range(n_chunks)]

    while len(sampled) < budget:
        N1_c = np.zeros(n_chunks, dtype=float)
        for c in range(n_chunks):
            N1_c[c] = sum(1 for cnt in discovered_events[c].values() if cnt == 1)
        theta = rng.gamma(shape=N1_c + 0.1, scale=1.0 / (n_c + 1.0))
        for c in range(n_chunks):
            chunk_bins = list(range(c * bins_per_chunk, min((c + 1) * bins_per_chunk, n_bins)))
            if all(b in sampled for b in chunk_bins):
                theta[c] = -np.inf
        if np.all(theta == -np.inf):
            break
        chosen_c = int(np.argmax(theta))
        chunk_bins = list(range(chosen_c * bins_per_chunk, min((chosen_c + 1) * bins_per_chunk, n_bins)))
        unsampled = [b for b in chunk_bins if b not in sampled]
        if not unsampled:
            break
        b = int(rng.choice(unsampled))
        sampled.add(b)
        n_c[chosen_c] += 1
        e = get_event_at_bin(grid, b)
        if e is not None:
            discovered_events[chosen_c][e] = discovered_events[chosen_c].get(e, 0) + 1
    return sorted(sampled)


def run_b7(grid: pd.DataFrame, budget: int, chunk_size_s: int, k: int, rng: np.random.Generator) -> List[int]:
    n_bins = len(grid)
    bins_per_chunk = max(1, chunk_size_s // int(BIN_SIZE))
    n_chunks = int(math.ceil(n_bins / bins_per_chunk))
    sampled: Set[int] = set()
    n_c = np.zeros(n_chunks, dtype=int)
    discovered_events: List[Dict[str, int]] = [dict() for _ in range(n_chunks)]

    def sample_bin(b: int, c: int) -> bool:
        if b in sampled or b < 0 or b >= n_bins:
            return False
        sampled.add(b)
        n_c[c] += 1
        e = get_event_at_bin(grid, b)
        if e is not None:
            discovered_events[c][e] = discovered_events[c].get(e, 0) + 1
        return True

    def expand(b: int, c: int) -> bool:
        for offset in range(1, k + 1):
            for sign in [-1, 1]:
                nb = b + sign * offset
                if nb < 0 or nb >= n_bins or nb in sampled:
                    continue
                sample_bin(nb, min(nb // bins_per_chunk, n_chunks - 1))
                return True
        return False

    while len(sampled) < budget:
        N1_c = np.zeros(n_chunks, dtype=float)
        for c in range(n_chunks):
            N1_c[c] = sum(1 for cnt in discovered_events[c].values() if cnt == 1)
        theta = rng.gamma(shape=N1_c + 0.1, scale=1.0 / (n_c + 1.0))
        for c in range(n_chunks):
            chunk_bins = range(c * bins_per_chunk, min((c + 1) * bins_per_chunk, n_bins))
            if all(b in sampled for b in chunk_bins):
                theta[c] = -np.inf
        if np.all(theta == -np.inf):
            break
        chosen_c = int(np.argmax(theta))
        chunk_bins = list(range(chosen_c * bins_per_chunk, min((chosen_c + 1) * bins_per_chunk, n_bins)))
        unsampled = [b for b in chunk_bins if b not in sampled]
        if not unsampled:
            break
        b = int(rng.choice(unsampled))
        sample_bin(b, chosen_c)

        if get_label_at_bin(grid, b) == "positive" and len(sampled) < budget:
            for _ in range(k * 2 + 5):
                if len(sampled) >= budget:
                    break
                left_neg = all(
                    get_label_at_bin(grid, b - o) == "negative"
                    for o in range(1, k + 1)
                    if b - o >= 0 and b - o not in sampled
                )
                right_neg = all(
                    get_label_at_bin(grid, b + o) == "negative"
                    for o in range(1, k + 1)
                    if b + o < n_bins and b + o not in sampled
                )
                if left_neg and right_neg:
                    break
                if not expand(b, chosen_c):
                    break
    return sorted(sampled)


# ---------------------------------------------------------------------------
# Ours (Frozen-LATE-AQP-v1) with repair trace
# ---------------------------------------------------------------------------
def run_ours(
    grid: pd.DataFrame,
    ref: pd.DataFrame,
    budget: int,
    rng: np.random.Generator,
    segment_id: str,
    trial: int,
    call_rows: List[Dict],
) -> Tuple[List[int], Dict]:
    n_bins = len(grid)
    e0_pct = 20
    k = max(1, int(round(n_bins * e0_pct / 100.0)))
    top = grid.nlargest(k, "prior_score_max")
    e0 = set(int(x) for x in top["bin_idx"].tolist())

    # Boundary (computed but not used for calls in V3_two_phase)
    boundary = set()
    for b in e0:
        boundary.add(max(0, b - 1))
        boundary.add(min(n_bins - 1, b + 1))
    boundary = boundary - e0

    queried: Set[int] = set()
    selected: Set[int] = set()
    audit_calls = 0
    discovery_calls = 0
    repair_calls = 0
    outside_positives: List[int] = []
    seed_to_trigger_call: Dict[int, str] = {}

    bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}

    def log_call(
        action_type: str,
        b: int,
        trigger_call_id: Optional[str] = None,
        trigger_unit_id: Optional[int] = None,
        repair_utility_value: Optional[float] = None,
        repair_window_start: Optional[float] = None,
        repair_window_end: Optional[float] = None,
        repair_reason: Optional[str] = None,
    ) -> str:
        call_id = f"{segment_id}_ours_b{budget}_t{trial}_{len(call_rows)}"
        row = bin_to_row[b]
        label = "positive" if row["is_positive"] else "negative"
        hit_event_id = row["event_id"] if row["is_positive"] else "none"
        hit_event_type = ""
        event_overlap = 0.0
        if row["is_positive"] and hit_event_id:
            ev = ref[ref["event_id"] == hit_event_id]
            if not ev.empty:
                ev = ev.iloc[0]
                event_overlap = max(0.0, min(row["t_end"], ev["t_end"]) - max(row["t_start"], ev["t_start"]))
                hit_event_type = ev["event_type"]
        call_rows.append({
            "call_id": call_id,
            "segment_id": segment_id,
            "round_id": trial,
            "budget": budget,
            "method": "Frozen-LATE-AQP-v1",
            "action_type": action_type,
            "selected_unit_id": f"b{b}",
            "local_t_start": row["t_start"],
            "local_t_end": row["t_end"],
            "prior_score": row["prior_score_max"],
            "inside_E0_top20": b in e0,
            "oracle_label": label,
            "source_of_action": "V3_two_phase",
            "trigger_call_id": trigger_call_id if trigger_call_id else "",
            "trigger_unit_id": f"b{trigger_unit_id}" if trigger_unit_id is not None else "",
            "trigger_label": "positive" if trigger_unit_id is not None else "",
            "local_envelope_id": "e0_top20",
            "repair_window_start": repair_window_start if repair_window_start is not None else "",
            "repair_window_end": repair_window_end if repair_window_end is not None else "",
            "repair_reason": repair_reason if repair_reason else "",
            "repair_utility_value": repair_utility_value if repair_utility_value is not None else "",
            "audit_probability": "unknown_not_logged",
            "inclusion_probability": "unknown_not_logged",
            "is_used_for_estimator": action_type in ("audit_inside", "audit_outside"),
            "is_used_for_discovery": action_type.startswith("discovery") or action_type == "fallback_discovery",
            "is_used_for_repair": action_type == "repair_expansion",
            "hit_event_id": hit_event_id,
            "hit_event_type": hit_event_type,
            "event_overlap_duration": event_overlap,
            "selected_interval_id": "",
            "notes": "",
        })
        return call_id

    # Audit phase.
    audit_calls_target = min(math.ceil(budget * 0.10), 3 * 2)
    audit_calls_target = max(0, min(audit_calls_target, budget))
    inside_bins = [b for b in range(n_bins) if b in e0]
    outside_bins = [b for b in range(n_bins) if b not in e0]
    n_inside = math.floor(audit_calls_target * 0.5)
    n_outside = audit_calls_target - n_inside

    inside_weights = {b: max(1e-6, bin_to_row[b]["prior_score_max"]) for b in inside_bins}
    outside_weights = {b: max(1e-6, bin_to_row[b]["prior_score_max"]) for b in outside_bins}

    def sample_weighted(pool: List[int], n: int, weights: Dict[int, float]) -> List[int]:
        if n <= 0 or not pool:
            return []
        pool = [b for b in pool if b not in queried]
        if not pool:
            return []
        n = min(n, len(pool))
        w = np.array([weights.get(b, 1e-6) for b in pool])
        w = w / w.sum()
        chosen = rng.choice(pool, size=n, replace=False, p=w).tolist()
        return [int(x) for x in chosen]

    audited_inside = sample_weighted(inside_bins, n_inside, inside_weights)
    audited_outside = sample_weighted(outside_bins, n_outside, outside_weights)
    for b in audited_inside:
        queried.add(b)
        selected.add(b)
        audit_calls += 1
        log_call("audit_inside", b)
    for b in audited_outside:
        queried.add(b)
        selected.add(b)
        audit_calls += 1
        call_id = log_call("audit_outside", b)
        if bin_to_row[b]["is_positive"]:
            outside_positives.append(b)
            seed_to_trigger_call[b] = call_id

    # Second tranche if leakage detected.
    if outside_positives:
        cap = round(budget * 0.25)
        extra = cap - audit_calls
        extra = max(0, min(extra, budget - audit_calls))
        if extra > 0:
            extra_outside = math.ceil(extra * 0.7)
            extra_inside = extra - extra_outside
            more_in = sample_weighted(inside_bins, extra_inside, inside_weights)
            more_out = sample_weighted(outside_bins, extra_outside, outside_weights)
            for b in more_in:
                queried.add(b)
                selected.add(b)
                audit_calls += 1
                log_call("audit_inside", b)
            for b in more_out:
                queried.add(b)
                selected.add(b)
                audit_calls += 1
                call_id = log_call("audit_outside", b)
                if bin_to_row[b]["is_positive"]:
                    outside_positives.append(b)
                    seed_to_trigger_call[b] = call_id

    # Repair phase.
    remaining = budget - audit_calls
    repair_seeds = list(set(outside_positives))
    if repair_seeds and remaining > 0:
        actions = []
        for seed in repair_seeds:
            seed_prior = bin_to_row[seed]["prior_score_max"]
            for nb in [max(0, seed - 1), min(n_bins - 1, seed + 1)]:
                if nb in queried:
                    continue
                utility = seed_prior  # U0_current
                actions.append((utility, seed, nb))
        actions.sort(key=lambda x: x[0], reverse=True)
        for _, seed, nb in actions:
            if remaining <= 0:
                break
            if nb in queried:
                continue
            queried.add(nb)
            selected.add(nb)
            repair_calls += 1
            remaining -= 1
            trigger_call_id = seed_to_trigger_call.get(seed)
            seed_row = bin_to_row[seed]
            log_call(
                "repair_expansion",
                nb,
                trigger_call_id=trigger_call_id,
                trigger_unit_id=seed,
                repair_utility_value=seed_row["prior_score_max"],
                repair_window_start=seed_row["t_start"],
                repair_window_end=seed_row["t_end"],
                repair_reason="audit_outside_positive",
            )

    # Discovery phase.
    remaining = budget - audit_calls - repair_calls
    if remaining > 0:
        unqueried = [b for b in range(n_bins) if b not in queried]
        ranked = sorted(unqueried, key=lambda b: bin_to_row[b]["prior_score_max"], reverse=True)
        for b in ranked[:remaining]:
            queried.add(b)
            selected.add(b)
            discovery_calls += 1
            action = "discovery_initial_envelope" if b in e0 else "fallback_discovery"
            log_call(action, b)

    budget_accounting_error = budget - (audit_calls + repair_calls + discovery_calls)
    diagnostics = {
        "audit_calls": audit_calls,
        "repair_calls": repair_calls,
        "discovery_calls": discovery_calls,
        "budget_accounting_error": budget_accounting_error,
        "outside_positives": len(outside_positives),
    }
    return sorted(selected), diagnostics


# ---------------------------------------------------------------------------
# Post-processing: selected-interval trace
# ---------------------------------------------------------------------------
def build_selected_intervals(
    selected_bins: List[int],
    grid: pd.DataFrame,
    ref: pd.DataFrame,
    segment_id: str,
    method: str,
    budget: int,
    trial: int,
    call_rows: Optional[List[Dict]] = None,
) -> pd.DataFrame:
    intervals = merge_bins(grid, selected_bins)
    rows = []
    for idx, iv in intervals.iterrows():
        # Find calls whose selected unit lies inside this interval.
        created_call_ids = []
        action_types = set()
        if call_rows is not None:
            for c in call_rows:
                if c["segment_id"] != segment_id or c["method"] != method or c["budget"] != budget or c["round_id"] != trial:
                    continue
                if c["local_t_start"] >= iv["t_start"] - 1e-6 and c["local_t_end"] <= iv["t_end"] + 1e-6:
                    created_call_ids.append(c["call_id"])
                    action_types.add(c["action_type"])
                    c["selected_interval_id"] = f"{segment_id}_{method}_b{budget}_t{trial}_i{idx}"
        # Determine hit event.
        best_eid = "none"
        best_etype = ""
        best_overlap = 0.0
        best_iou = 0.0
        for _, ev in ref.iterrows():
            inter = max(0.0, min(iv["t_end"], ev["t_end"]) - max(iv["t_start"], ev["t_start"]))
            if inter > 0:
                union = max(iv["t_end"], ev["t_end"]) - min(iv["t_start"], ev["t_start"])
                iou = inter / union if union > 0 else 0.0
                if iou > best_iou:
                    best_iou = iou
                    best_overlap = inter
                    best_eid = ev["event_id"]
                    best_etype = ev["event_type"]
        rows.append({
            "selected_interval_id": f"{segment_id}_{method}_b{budget}_t{trial}_i{idx}",
            "segment_id": segment_id,
            "method": method,
            "budget": budget,
            "created_from_call_ids": "|".join(created_call_ids),
            "created_by_action_type": "|".join(sorted(action_types)) if action_types else "unknown_not_logged",
            "local_t_start": iv["t_start"],
            "local_t_end": iv["t_end"],
            "selected_duration": iv["duration"],
            "hit_event_id": best_eid,
            "hit_event_type": best_etype,
            "event_overlap_duration": best_overlap,
            "boundary_iou": best_iou,
            "source_lineage_summary": ";".join(sorted(action_types)) if action_types else "unknown_not_logged",
        })
    return pd.DataFrame(rows)


def compute_repair_triggered_hits(selected_bins: List[int], grid: pd.DataFrame, ref: pd.DataFrame, call_rows: List[Dict], segment_id: str, budget: int, trial: int) -> int:
    repair_bins = set()
    non_repair_bins = set()
    for c in call_rows:
        if c["segment_id"] != segment_id or c["method"] != "Frozen-LATE-AQP-v1" or c["budget"] != budget or c["round_id"] != trial:
            continue
        b = int(c["selected_unit_id"].replace("b", ""))
        if c["action_type"] == "repair_expansion":
            repair_bins.add(b)
        elif c["action_type"] != "":
            non_repair_bins.add(b)
    repair_hit_events = set()
    non_repair_hit_events = set()
    for b in repair_bins:
        row = grid[grid["bin_idx"] == b].iloc[0]
        for _, ev in ref.iterrows():
            if ev["event_type"] != "long_interval":
                continue
            if row["t_start"] < ev["t_end"] and row["t_end"] > ev["t_start"]:
                repair_hit_events.add(ev["event_id"])
    for b in non_repair_bins:
        row = grid[grid["bin_idx"] == b].iloc[0]
        for _, ev in ref.iterrows():
            if ev["event_type"] != "long_interval":
                continue
            if row["t_start"] < ev["t_end"] and row["t_end"] > ev["t_start"]:
                non_repair_hit_events.add(ev["event_id"])
    return len(repair_hit_events - non_repair_hit_events)


# ---------------------------------------------------------------------------
# Main experiment loop
# ---------------------------------------------------------------------------
def main():
    full_events = load_full_events()
    proxy_scores = load_proxy_scores()

    all_metrics_rows: List[Dict] = []
    all_interval_rows: List[Dict] = []
    all_call_rows: List[Dict] = []
    segment_grids: Dict[str, pd.DataFrame] = {}
    segment_refs: Dict[str, pd.DataFrame] = {}

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid, ref = build_segment_grid(seg, full_events, proxy_scores)
        segment_grids[seg_id] = grid
        segment_refs[seg_id] = ref
        print(f"Segment {seg_id}: {len(grid)} bins, {len(ref)} events, {ref['event_type'].value_counts().to_dict()}")

        for budget in BUDGETS:
            for trial, seed_offset in enumerate(SEEDS):
                rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)

                # B6
                selected_b6 = run_b6(grid, budget, chunk_size_s=120, rng=rng)
                metrics_b6 = compute_metrics(selected_b6, grid, ref)
                metrics_b6.update({
                    "segment_id": seg_id, "method": "B6_ExSample", "budget": budget, "trial": trial,
                    "audit_calls": len(selected_b6), "discovery_calls": 0, "repair_calls": 0,
                    "budget_accounting_error": budget - len(selected_b6),
                    "repair_triggered_hits": 0,
                })
                all_metrics_rows.append(metrics_b6)
                intervals_b6 = build_selected_intervals(selected_b6, grid, ref, seg_id, "B6_ExSample", budget, trial)
                all_interval_rows.extend(intervals_b6.to_dict("records"))

                # B7
                rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                selected_b7 = run_b7(grid, budget, chunk_size_s=120, k=3, rng=rng)
                metrics_b7 = compute_metrics(selected_b7, grid, ref)
                metrics_b7.update({
                    "segment_id": seg_id, "method": "B7_ExSample_plus_expansion", "budget": budget, "trial": trial,
                    "audit_calls": len(selected_b7), "discovery_calls": 0, "repair_calls": 0,
                    "budget_accounting_error": budget - len(selected_b7),
                    "repair_triggered_hits": 0,
                })
                all_metrics_rows.append(metrics_b7)
                intervals_b7 = build_selected_intervals(selected_b7, grid, ref, seg_id, "B7_ExSample_plus_expansion", budget, trial)
                all_interval_rows.extend(intervals_b7.to_dict("records"))

                # Ours
                rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                ours_calls: List[Dict] = []
                selected_ours, diag = run_ours(grid, ref, budget, rng, seg_id, trial, ours_calls)
                metrics_ours = compute_metrics(selected_ours, grid, ref)
                repair_hits = compute_repair_triggered_hits(selected_ours, grid, ref, ours_calls, seg_id, budget, trial)
                metrics_ours.update({
                    "segment_id": seg_id, "method": "Frozen-LATE-AQP-v1", "budget": budget, "trial": trial,
                    "audit_calls": diag["audit_calls"], "discovery_calls": diag["discovery_calls"],
                    "repair_calls": diag["repair_calls"], "budget_accounting_error": diag["budget_accounting_error"],
                    "repair_triggered_hits": repair_hits,
                })
                all_metrics_rows.append(metrics_ours)
                intervals_ours = build_selected_intervals(selected_ours, grid, ref, seg_id, "Frozen-LATE-AQP-v1", budget, trial, call_rows=ours_calls)
                all_interval_rows.extend(intervals_ours.to_dict("records"))
                all_call_rows.extend(ours_calls)

    # Write raw metrics.
    metrics_df = pd.DataFrame(all_metrics_rows)
    cols = ["segment_id", "method", "budget", "trial"] + [c for c in metrics_df.columns if c not in ("segment_id", "method", "budget", "trial")]
    metrics_df = metrics_df[cols]
    metrics_df.to_csv(OUT / "cross_segment_metrics.csv", index=False)

    # Per-segment/method/budget aggregates.
    agg_rows = []
    for (seg_id, method, budget), g in metrics_df.groupby(["segment_id", "method", "budget"]):
        row = {"segment_id": seg_id, "method": method, "budget": budget, "n_trials": len(g)}
        for col in ["event_recall", "long_event_recall", "point_anchor_recall", "selected_total_duration",
                    "positive_duration_overlap", "false_positive_duration", "selected_precision",
                    "complete_event_coverage", "boundary_iou_03", "boundary_iou_05", "duplicate_rate",
                    "fragmentation_rate", "num_selected_bins", "num_selected_intervals", "audit_calls",
                    "discovery_calls", "repair_calls", "budget_accounting_error", "repair_triggered_hits"]:
            vals = pd.to_numeric(g[col], errors="coerce").dropna()
            row[f"{col}_mean"] = vals.mean() if len(vals) else float("nan")
            row[f"{col}_std"] = vals.std() if len(vals) > 1 else 0.0
        agg_rows.append(row)
    agg_df = pd.DataFrame(agg_rows)
    agg_df.to_csv(OUT / "cross_segment_budget_curves.csv", index=False)

    # Long-event focused table.
    long_rows = agg_df[["segment_id", "method", "budget", "long_event_recall_mean", "long_event_recall_std",
                        "repair_triggered_hits_mean", "repair_triggered_hits_std", "selected_precision_mean",
                        "selected_total_duration_mean", "num_selected_bins_mean"]].copy()
    long_rows.to_csv(OUT / "cross_segment_long_event_metrics.csv", index=False)

    # Selected duration / precision report.
    dur_prec = agg_df[["segment_id", "method", "budget", "selected_total_duration_mean", "positive_duration_overlap_mean",
                       "false_positive_duration_mean", "selected_precision_mean", "num_selected_bins_mean"]].copy()
    dur_prec.to_csv(OUT / "selected_duration_precision_report.csv", index=False)

    # Repair trace CSVs.
    calls_df = pd.DataFrame(all_call_rows)
    if not calls_df.empty:
        calls_df = calls_df[[
            "call_id", "segment_id", "round_id", "budget", "method", "action_type", "selected_unit_id",
            "local_t_start", "local_t_end", "prior_score", "inside_E0_top20", "oracle_label",
            "source_of_action", "trigger_call_id", "trigger_unit_id", "trigger_label", "local_envelope_id",
            "repair_window_start", "repair_window_end", "repair_reason", "repair_utility_value",
            "audit_probability", "inclusion_probability", "is_used_for_estimator", "is_used_for_discovery",
            "is_used_for_repair", "hit_event_id", "hit_event_type", "event_overlap_duration",
            "selected_interval_id", "notes"
        ]]
    calls_df.to_csv(OUT / "repair_trace_calls.csv", index=False)

    intervals_df = pd.DataFrame(all_interval_rows)
    if not intervals_df.empty:
        intervals_df = intervals_df[[
            "selected_interval_id", "segment_id", "method", "budget", "created_from_call_ids",
            "created_by_action_type", "local_t_start", "local_t_end", "selected_duration",
            "hit_event_id", "hit_event_type", "event_overlap_duration", "boundary_iou", "source_lineage_summary"
        ]]
    intervals_df.to_csv(OUT / "repair_trace_selected_intervals.csv", index=False)

    # Segment density report.
    density_rows = []
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid = segment_grids[seg_id]
        ref = segment_refs[seg_id]
        n_bins = len(grid)
        pos_bins = int(grid["is_positive"].sum())
        density = pos_bins / n_bins if n_bins else 0.0
        n_long = int((ref["event_type"] == "long_interval").sum())
        n_point = int((ref["event_type"] == "point_anchor").sum())
        density_rows.append({
            "segment_id": seg_id,
            "time_start": seg["time_start"],
            "time_end": seg["time_end"],
            "duration": seg["time_end"] - seg["time_start"],
            "atomic_bin_size": BIN_SIZE,
            "num_bins": n_bins,
            "num_positive_bins": pos_bins,
            "positive_bin_density": density,
            "num_events": len(ref),
            "num_long_events": n_long,
            "num_point_anchor_events": n_point,
            "has_prior_score": True,
            "has_event_id": True,
            "has_event_intervals": True,
            "is_dev_segment": seg["is_dev"],
            "is_selected_for_test": True,
            "notes": seg.get("density_regime", ""),
        })
    density_df = pd.DataFrame(density_rows)
    density_df.to_csv(OUT / "segment_density_report.csv", index=False)

    # Save grids/refs for downstream reports.
    for seg_id, grid in segment_grids.items():
        grid.to_csv(OUT / f"grid_{seg_id}.csv", index=False)
        segment_refs[seg_id].to_csv(OUT / f"ref_events_{seg_id}.csv", index=False)

    print("Replay complete. Raw outputs written.")


if __name__ == "__main__":
    main()
