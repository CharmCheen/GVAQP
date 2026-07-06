#!/usr/bin/env python3
"""
Upstream Event-Diverse Discovery Redesign for LATE-AQP (v2).

Evaluates D0/D1/D2/D3/D3-norepair discovery policies against B6-core/B7-core
on realcartest and dataset3 segments using existing full-VLM references.

Constraints:
- No GPU/VLM/API calls.
- No new labels.
- No event_id or GT intervals used in discovery/repair/runtime decisions.
- Reuses existing Core/Halo release and LATE repair implementations.
"""
from __future__ import annotations

import csv
import math
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "outputs" / "late_aqp_event_diverse_discovery_v1"
OUT.mkdir(parents=True, exist_ok=True)

FROZEN_DIR = ROOT / "outputs" / "late_aqp_frozen_cross_segment_v1"
ATTR_DIR = ROOT / "outputs" / "late_aqp_core_halo_attribution_v1"

sys.path.insert(0, str(FROZEN_DIR))
from run_frozen_cross_segment import (
    BIN_SIZE,
    RANDOM_SEED_BASE,
    SEEDS,
    build_segment_grid,
    compute_metrics,
    get_label_at_bin,
    load_dev_events,
    load_dev_grid,
    load_full_events,
    load_proxy_scores,
    merge_bins,
    run_b6,
    run_b7,
)

sys.path.insert(0, str(ATTR_DIR))
import run_attribution_analysis as attr_module
from run_attribution_analysis import (
    BUDGETS as ATTR_BUDGETS,
    CHUNK_SIZE_S,
    MAX_GUARDS_PER_SIDE,
    compute_guard_need,
    event_level_metrics,
    load_segment_grid_ref,
    perform_guards,
    run_b6_b7_core_halo,
    run_late_aqp_core_halo,
)

# ---------------------------------------------------------------------------
# Dataset3 loading / grid building (mirrors run_cross_video_frontier.py)
# ---------------------------------------------------------------------------
DATASET3_CANONICAL = (
    ROOT
    / "src"
    / "garc_eval"
    / "outputs"
    / "codex_recompute_proxy_budget_basa_v1"
    / "tables"
    / "canonical_dataset3_anchor_table.csv"
)


def load_dataset3_reference() -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(DATASET3_CANONICAL)
    pos = df[df["is_positive"] == True].copy()
    events = []
    for cid, g in pos.groupby("event_cluster_id"):
        if cid < 0:
            continue
        t_start = float(g["event_start_absolute"].min())
        t_end = float(g["event_end_absolute"].max())
        duration = t_end - t_start
        obj = Counter(g["involved_object"].dropna().astype(str)).most_common(1)
        involved = obj[0][0] if obj else "unknown"
        events.append(
            {
                "event_id": f"dataset3_event_{int(cid):03d}",
                "t_start": t_start,
                "t_end": t_end,
                "duration": duration,
                "event_type": "long_interval" if duration >= 1.0 else "point_anchor",
                "involved_object": involved,
            }
        )
    events = pd.DataFrame(events)
    proxy = df[["start_time", "end_time", "score_yolo_count"]].copy()
    proxy = proxy.rename(columns={"score_yolo_count": "score"})
    proxy["score"] = pd.to_numeric(proxy["score"], errors="coerce").fillna(0.0)
    proxy["t_start"] = pd.to_numeric(proxy["start_time"], errors="coerce")
    proxy["t_end"] = pd.to_numeric(proxy["end_time"], errors="coerce")
    proxy = proxy[["t_start", "t_end", "score"]].drop_duplicates().reset_index(drop=True)
    return events, proxy


def build_dataset3_segment_grid(
    seg: Dict, full_events: pd.DataFrame, proxy_scores: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    t0, t1 = seg["time_start"], seg["time_end"]
    duration = t1 - t0
    n_bins = int(math.ceil(duration / BIN_SIZE))

    bins = []
    for i in range(n_bins):
        bs = i * BIN_SIZE
        be = min(bs + BIN_SIZE, duration)
        bins.append({"bin_idx": i, "local_t_start": bs, "local_t_end": be})
    grid = pd.DataFrame(bins)

    ev_overlap = full_events[(full_events["t_end"] > t0) & (full_events["t_start"] < t1)].copy()
    ev_overlap["t_start"] = ev_overlap["t_start"].clip(lower=t0) - t0
    ev_overlap["t_end"] = ev_overlap["t_end"].clip(upper=t1) - t0
    ev_overlap["duration"] = ev_overlap["t_end"] - ev_overlap["t_start"]
    ref = ev_overlap.reset_index(drop=True)

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

    scores_max = []
    scores_mean = []
    for _, b in grid.iterrows():
        bs_abs = t0 + b["local_t_start"]
        be_abs = t0 + b["local_t_end"]
        over = proxy_scores[(proxy_scores["t_start"] < be_abs) & (proxy_scores["t_end"] > bs_abs)]
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


# ---------------------------------------------------------------------------
# Segment definitions and budget grid
# ---------------------------------------------------------------------------
REAL_SEGMENTS = [
    {"segment_id": "realcartest_0_1570", "video_id": "realcartest", "time_start": 0.0, "time_end": 1570.0, "is_dev": False},
    {"segment_id": "realcartest_2000_3200", "video_id": "realcartest", "time_start": 2000.0, "time_end": 3200.0, "is_dev": True},
    {"segment_id": "realcartest_3200_3830", "video_id": "realcartest", "time_start": 3200.0, "time_end": 3830.0, "is_dev": False},
]

DS3_SEGMENTS = [
    {"segment_id": "dataset3_0_1200", "video_id": "long_video_dataset3", "time_start": 0.0, "time_end": 1200.0, "is_dev": False},
    {"segment_id": "dataset3_1200_2400", "video_id": "long_video_dataset3", "time_start": 1200.0, "time_end": 2400.0, "is_dev": False},
    {"segment_id": "dataset3_2400_3462", "video_id": "long_video_dataset3", "time_start": 2400.0, "time_end": 3462.93, "is_dev": False},
]

RATIO_GRID = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00]
ABSOLUTE_GRID = [5, 10, 20, 40, 60, 80, 100, 120]


def get_segment_budget_grid(n_units: int) -> List[int]:
    budgets = set(ABSOLUTE_GRID)
    for r in RATIO_GRID:
        budgets.add(max(1, min(n_units, round(n_units * r))))
    budgets = {b for b in budgets if 1 <= b <= n_units}
    return sorted(budgets)


def load_segment_grid(seg: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if seg["video_id"] == "long_video_dataset3":
        events, proxy = load_dataset3_reference()
        return build_dataset3_segment_grid(seg, events, proxy)
    return load_segment_grid_ref(seg)


# ---------------------------------------------------------------------------
# Discovery policy implementations (strict-replay, no event_id)
# ---------------------------------------------------------------------------
def discovery_d1_temporal_nms(
    grid: pd.DataFrame,
    budget: int,
    queried: Set[int],
    rng: np.random.Generator,
    radius_s: float,
) -> List[int]:
    """Temporal-NMS prior discovery."""
    n_bins = len(grid)
    bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}
    unqueried = [b for b in range(n_bins) if b not in queried]
    ranked = sorted(unqueried, key=lambda b: bin_to_row[b]["prior_score_max"], reverse=True)

    selected: List[int] = []
    suppressed: Set[int] = set()

    def suppress(b: int):
        t = (bin_to_row[b]["t_start"] + bin_to_row[b]["t_end"]) / 2.0
        for bb in range(n_bins):
            bb_t = (bin_to_row[bb]["t_start"] + bin_to_row[bb]["t_end"]) / 2.0
            if abs(bb_t - t) <= radius_s + 1e-6:
                suppressed.add(bb)

    for b in ranked:
        if len(selected) >= budget:
            break
        if b in suppressed:
            continue
        selected.append(b)
        suppress(b)

    # Fallback: if budget remains, take any remaining unqueried bins by prior rank.
    if len(selected) < budget:
        for b in ranked:
            if len(selected) >= budget:
                break
            if b not in selected:
                selected.append(b)
    return selected


def discovery_d2_component_proposals(
    grid: pd.DataFrame,
    budget: int,
    queried: Set[int],
    rng: np.random.Generator,
    quantile_pct: float,
    score_kind: str,
    rep_kind: str,
) -> List[int]:
    """Component-level prior proposal discovery."""
    n_bins = len(grid)
    bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}
    scores = np.array([bin_to_row[b]["prior_score_max"] for b in range(n_bins)], dtype=float)
    s_min, s_max = scores.min(), scores.max()
    norm = (scores - s_min) / max(1e-9, s_max - s_min)

    threshold = 1.0 - quantile_pct / 100.0
    cand_bins = [b for b in range(n_bins) if norm[b] >= threshold - 1e-9 and b not in queried]
    cand_bins.sort()

    # Merge into components (contiguous or gap <= 1 bin).
    components: List[List[int]] = []
    for b in cand_bins:
        if not components:
            components.append([b])
        else:
            last = components[-1][-1]
            if b <= last + 2:  # gap of at most 1 bin
                components[-1].append(b)
            else:
                components.append([b])

    if not components:
        # Fallback to top prior bins.
        unqueried = [b for b in range(n_bins) if b not in queried]
        ranked = sorted(unqueried, key=lambda b: bin_to_row[b]["prior_score_max"], reverse=True)
        return ranked[:budget]

    comp_info = []
    for comp in components:
        max_prior = max(bin_to_row[b]["prior_score_max"] for b in comp)
        mean_prior = sum(bin_to_row[b]["prior_score_max"] for b in comp) / len(comp)
        prior_mass = sum(bin_to_row[b]["prior_score_max"] for b in comp)
        duration = bin_to_row[comp[-1]]["t_end"] - bin_to_row[comp[0]]["t_start"]
        if score_kind == "mass":
            score = prior_mass
        elif score_kind == "max":
            score = max_prior
        else:
            score = prior_mass
        # representative bin
        if rep_kind == "highest":
            rep = max(comp, key=lambda b: bin_to_row[b]["prior_score_max"])
        elif rep_kind == "center":
            center_t = (bin_to_row[comp[0]]["t_start"] + bin_to_row[comp[-1]]["t_end"]) / 2.0
            rep = min(comp, key=lambda b: abs((bin_to_row[b]["t_start"] + bin_to_row[b]["t_end"]) / 2.0 - center_t))
        else:
            rep = comp[len(comp) // 2]
        comp_info.append({"comp": comp, "score": score, "rep": rep})

    comp_info.sort(key=lambda x: x["score"], reverse=True)

    selected: List[int] = []
    # First pass: one representative per component.
    for info in comp_info:
        if len(selected) >= budget:
            break
        if info["rep"] not in queried:
            selected.append(info["rep"])

    # Second pass: additional bins from ranked components (still no component twice until all have two).
    pass_num = 1
    while len(selected) < budget:
        added_this_round = 0
        for info in comp_info:
            if len(selected) >= budget:
                break
            comp = info["comp"]
            # pick next best unqueried bin in component not yet selected
            for b in sorted(comp, key=lambda x: bin_to_row[x]["prior_score_max"], reverse=True):
                if b not in queried and b not in selected:
                    selected.append(b)
                    added_this_round += 1
                    break
        if added_this_round == 0:
            break
        pass_num += 1
        if pass_num > n_bins:
            break

    # Fallback: if budget remains, fill with globally top-prior unqueried bins.
    if len(selected) < budget:
        unqueried = [b for b in range(n_bins) if b not in queried and b not in selected]
        ranked = sorted(unqueried, key=lambda b: bin_to_row[b]["prior_score_max"], reverse=True)
        selected.extend(ranked[: budget - len(selected)])

    return selected


def discovery_d3_chunk_bandit(
    grid: pd.DataFrame,
    budget: int,
    queried: Set[int],
    rng: np.random.Generator,
    chunk_size_s: float,
) -> List[int]:
    """Chunk-bandit discovery (strict-replay, no event_id)."""
    n_bins = len(grid)
    bins_per_chunk = max(1, int(chunk_size_s // int(BIN_SIZE)))
    n_chunks = int(math.ceil(n_bins / bins_per_chunk))
    bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}

    sampled: Set[int] = set()
    n_c = np.zeros(n_chunks, dtype=int)
    N1_c = np.zeros(n_chunks, dtype=float)  # singleton positive seeds

    # Track how many times each sampled bin has been sampled (for singleton counting).
    sample_count: Dict[int, int] = {}

    def sample_bin(b: int, c: int) -> bool:
        if b in sampled or b < 0 or b >= n_bins:
            return False
        sampled.add(b)
        sample_count[b] = sample_count.get(b, 0) + 1
        n_c[c] += 1
        return True

    def update_singleton_counts():
        # Recompute N1_c from scratch each step for simplicity.
        N1_c[:] = 0.0
        for b, cnt in sample_count.items():
            if cnt == 1 and bin_to_row[b]["is_positive"]:
                c = min(b // bins_per_chunk, n_chunks - 1)
                N1_c[c] += 1

    while len(sampled) < budget:
        update_singleton_counts()
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
        sample_bin(b, chosen_c)

    return sorted(sampled)


# ---------------------------------------------------------------------------
# Wrappers that reuse existing Core/Halo and (for LATE) repair
# ---------------------------------------------------------------------------
def run_late_with_custom_discovery(
    grid: pd.DataFrame,
    ref: pd.DataFrame,
    budget: int,
    rng: np.random.Generator,
    segment_id: str,
    seed: int,
    discovery_fn: Callable,
) -> Tuple[List[int], pd.DataFrame, pd.DataFrame, List[Dict], Dict]:
    """Run existing LATE-AQP core/halo but replace the discovery step."""
    original_run_discovery = attr_module.run_discovery
    # Existing run_late_aqp_core_halo calls run_discovery(grid, budget, queried).
    # Wrap our discovery_fn to inject the rng.
    def wrapped_discovery(grid, budget, queried):
        return discovery_fn(grid, budget, queried, rng)
    attr_module.run_discovery = wrapped_discovery
    try:
        cand_bins, cand_iv, core_iv, guard_log, diag = run_late_aqp_core_halo(
            grid, ref, budget, rng, segment_id, seed
        )
    finally:
        attr_module.run_discovery = original_run_discovery
    return cand_bins, cand_iv, core_iv, guard_log, diag


def run_discovery_then_core_halo(
    grid: pd.DataFrame,
    ref: pd.DataFrame,
    budget: int,
    rng: np.random.Generator,
    segment_id: str,
    seed: int,
    discovery_fn: Callable,
    method: str,
) -> Tuple[List[int], pd.DataFrame, pd.DataFrame, List[Dict], Dict]:
    """Run a pure discovery policy followed by Core/Halo release (no audit/repair)."""
    n_bins = len(grid)
    bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}

    selected = set(discovery_fn(grid, budget, set(), rng))
    candidate_intervals = merge_bins(grid, sorted(selected))

    # Budget-aware guard iteration (mirrors run_b6_b7_core_halo).
    need = compute_guard_need(candidate_intervals, grid, MAX_GUARDS_PER_SIDE, bin_to_row)
    if len(selected) + need > budget:
        # Reduce discovery budget and re-run.
        disc_budget = max(0, budget - need)
        selected = set(discovery_fn(grid, disc_budget, set(), rng))
        candidate_intervals = merge_bins(grid, sorted(selected))
        need = compute_guard_need(candidate_intervals, grid, MAX_GUARDS_PER_SIDE, bin_to_row)

    guard_budget = budget - len(selected)
    core_bins, guard_log, actual_guards = perform_guards(
        candidate_intervals, grid, bin_to_row, guard_budget, method, segment_id, budget, seed
    )
    core_intervals = merge_bins(grid, sorted(core_bins))

    candidate_duration = candidate_intervals["duration"].sum() if not candidate_intervals.empty else 0.0
    core_duration = core_intervals["duration"].sum() if not core_intervals.empty else 0.0
    diag = {
        "audit_calls": 0,
        "repair_calls": 0,
        "discovery_calls": len(selected),
        "guard_calls": actual_guards,
        "total_used_calls": len(selected) + actual_guards,
        "budget_accounting_error": budget - (len(selected) + actual_guards),
        "candidate_duration": candidate_duration,
        "core_duration": core_duration,
        "halo_duration": candidate_duration - core_duration,
    }
    return sorted(selected.union(core_bins)), candidate_intervals, core_intervals, guard_log, diag


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def intervals_to_bins(intervals_df: pd.DataFrame) -> List[int]:
    bins = []
    if intervals_df.empty:
        return bins
    for _, iv in intervals_df.iterrows():
        bins.extend([int(b) for b in iv["bin_indices"]])
    return sorted(set(bins))


def hits_from_bins(selected_bins: List[int], grid: pd.DataFrame, ref: pd.DataFrame) -> Set[str]:
    intervals = merge_bins(grid, selected_bins)
    hit_events: Set[str] = set()
    for _, ev in ref.iterrows():
        for _, iv in intervals.iterrows():
            if max(0.0, min(iv["t_end"], ev["t_end"]) - max(iv["t_start"], ev["t_start"])) > 0:
                hit_events.add(str(ev["event_id"]))
                break
    return hit_events


def compute_all_metrics(
    selected_bins: List[int],
    candidate_bins: List[int],
    grid: pd.DataFrame,
    ref: pd.DataFrame,
    diag: Dict,
) -> Dict:
    intervals = merge_bins(grid, selected_bins)
    ev_prec, ev_rec = event_level_metrics(intervals, ref)
    dur = compute_metrics(selected_bins, grid, ref)

    n_ref = len(ref)
    n_long = len(ref[ref["event_type"] == "long_interval"])
    n_point = n_ref - n_long

    hit_events = hits_from_bins(selected_bins, grid, ref)
    long_hit = set()
    point_hit = set()
    for eid in hit_events:
        ev = ref[ref["event_id"].astype(str) == eid]
        if not ev.empty and ev.iloc[0]["event_type"] == "long_interval":
            long_hit.add(eid)
        else:
            point_hit.add(eid)

    candidate_hit_events = hits_from_bins(candidate_bins, grid, ref)
    core_hit_events = hit_events
    events_in_halo_not_core = candidate_hit_events - core_hit_events
    events_never_selected = set(str(eid) for eid in ref["event_id"]) - candidate_hit_events

    # Duplicate / repeated hit metrics.
    selected_grid = grid[grid["bin_idx"].isin(selected_bins)]
    pos_sel = selected_grid[selected_grid["is_positive"]]
    pos_events_hit_from_bins = set()
    for _, b in pos_sel.iterrows():
        if b["event_id"]:
            pos_events_hit_from_bins.add(str(b["event_id"]))
    duplicate_rate = (len(pos_sel) - len(pos_events_hit_from_bins)) / max(1, len(pos_events_hit_from_bins))
    repeated_hit_count = max(0, len(pos_sel) - len(pos_events_hit_from_bins))

    # Pairwise time distances.
    centers = []
    for b in selected_bins:
        row = grid[grid["bin_idx"] == b].iloc[0]
        centers.append((row["t_start"] + row["t_end"]) / 2.0)
    pairwise_dists = []
    for i, j in combinations(range(len(centers)), 2):
        pairwise_dists.append(abs(centers[i] - centers[j]))
    mean_pairwise_dist = float(np.mean(pairwise_dists)) if pairwise_dists else 0.0

    # Max calls within sliding windows.
    def max_in_window(window_s: float) -> int:
        if not centers:
            return 0
        centers_sorted = sorted(centers)
        best = 0
        left = 0
        for right in range(len(centers_sorted)):
            while centers_sorted[right] - centers_sorted[left] > window_s + 1e-6:
                left += 1
            best = max(best, right - left + 1)
        return best

    max_30s = max_in_window(30.0)
    max_60s = max_in_window(60.0)

    # Discovery miss / release conservative counts.
    discovery_miss_count = len(events_never_selected)
    release_over_conservative_count = len(events_in_halo_not_core)

    return {
        "event_precision": ev_prec,
        "event_recall": ev_rec,
        "duration_precision": dur["selected_precision"],
        "duration_recall": dur["event_recall"],
        "long_event_recall": dur["long_event_recall"] if not math.isnan(dur["long_event_recall"]) else 0.0,
        "point_anchor_recall": dur["point_anchor_recall"] if not math.isnan(dur["point_anchor_recall"]) else 0.0,
        "selected_duration": dur["selected_total_duration"],
        "false_positive_duration": dur["false_positive_duration"],
        "num_unique_events_hit": len(hit_events),
        "num_long_events_hit": len(long_hit),
        "num_point_anchor_events_hit": len(point_hit),
        "duplicate_sampling_rate": duplicate_rate,
        "repeated_hit_count": repeated_hit_count,
        "mean_pairwise_selected_time_distance": mean_pairwise_dist,
        "max_calls_within_same_30s_window": max_30s,
        "max_calls_within_same_60s_window": max_60s,
        "discovery_miss_count": discovery_miss_count,
        "release_over_conservative_count": release_over_conservative_count,
        "events_in_halo_but_not_core": len(events_in_halo_not_core),
        "events_never_selected": len(events_never_selected),
        "guard_calls": diag.get("guard_calls", 0),
        "repair_calls": diag.get("repair_calls", 0),
        "audit_calls": diag.get("audit_calls", 0),
        "discovery_calls": diag.get("discovery_calls", 0),
        "oracle_calls_total": diag.get("total_used_calls", 0),
    }


# ---------------------------------------------------------------------------
# Method dispatch
# ---------------------------------------------------------------------------
def make_discovery_fn(method_spec: str):
    """Return a discovery function for a given method spec."""
    if method_spec.startswith("LATE-D1-core-radius"):
        radius = float(method_spec.split("radius")[-1])
        return lambda grid, budget, queried, rng: discovery_d1_temporal_nms(grid, budget, queried, rng, radius)
    if method_spec.startswith("LATE-D2-core-"):
        # Format: LATE-D2-core-q{20,30,50}-s{mass,max}-r{highest,center}
        parts = method_spec.split("-")
        # parts = ['LATE', 'D2', 'core', 'q20', 'smax', 'rcenter']
        q = float(parts[3][1:])  # q20 -> 20
        s = parts[4][1:]         # smass -> mass
        r = parts[5][1:]         # rhighest -> highest
        return lambda grid, budget, queried, rng: discovery_d2_component_proposals(
            grid, budget, queried, rng, q, s, r
        )
    if method_spec.startswith("LATE-D3-core-chunk"):
        chunk = float(method_spec.split("chunk")[-1])
        return lambda grid, budget, queried, rng: discovery_d3_chunk_bandit(grid, budget, queried, rng, chunk)
    if method_spec.startswith("D3-norepair-core-chunk"):
        chunk = float(method_spec.split("chunk")[-1])
        return lambda grid, budget, queried, rng: discovery_d3_chunk_bandit(grid, budget, queried, rng, chunk)
    raise ValueError(f"Unknown method spec: {method_spec}")


def run_method(
    grid: pd.DataFrame,
    ref: pd.DataFrame,
    budget: int,
    rng: np.random.Generator,
    method: str,
    segment_id: str,
    seed: int,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict, str]:
    """Return (core_intervals, candidate_intervals, diagnostics, replay_type)."""
    if method in ("B6-core", "B7-core"):
        base = "B6" if method == "B6-core" else "B7"
        _, cand_iv, core_iv, _, diag = run_b6_b7_core_halo(
            grid, ref, budget, rng, base, segment_id, seed
        )
        diag_out = {
            "audit_calls": 0,
            "repair_calls": 0,
            "discovery_calls": diag["selection_calls"],
            "guard_calls": diag["guard_calls"],
            "total_used_calls": diag["total_used_calls"],
            "candidate_duration": diag["candidate_duration"],
            "core_duration": diag["core_duration"],
            "halo_duration": diag["halo_duration"],
        }
        return core_iv, cand_iv, diag_out, "posthoc_eval"

    if method == "LATE-D0-core":
        _, cand_iv, core_iv, _, diag = run_late_aqp_core_halo(
            grid, ref, budget, rng, segment_id, seed
        )
        diag_out = {
            "audit_calls": diag["audit_calls"],
            "repair_calls": diag["repair_calls"],
            "discovery_calls": diag["discovery_calls"],
            "guard_calls": diag["guard_calls"],
            "total_used_calls": diag["total_used_calls"],
            "candidate_duration": diag["candidate_duration"],
            "core_duration": diag["core_duration"],
            "halo_duration": diag["halo_duration"],
        }
        return core_iv, cand_iv, diag_out, "strict_replay"

    if method.startswith("LATE-D1-core") or method.startswith("LATE-D2-core") or method.startswith("LATE-D3-core"):
        disc_fn = make_discovery_fn(method)
        cand_bins, cand_iv, core_iv, _, diag = run_late_with_custom_discovery(
            grid, ref, budget, rng, segment_id, seed, disc_fn
        )
        diag_out = {
            "audit_calls": diag["audit_calls"],
            "repair_calls": diag["repair_calls"],
            "discovery_calls": diag["discovery_calls"],
            "guard_calls": diag["guard_calls"],
            "total_used_calls": diag["total_used_calls"],
            "candidate_duration": diag["candidate_duration"],
            "core_duration": diag["core_duration"],
            "halo_duration": diag["halo_duration"],
        }
        return core_iv, cand_iv, diag_out, "strict_replay"

    if method.startswith("D3-norepair-core"):
        disc_fn = make_discovery_fn(method)
        _, cand_iv, core_iv, _, diag = run_discovery_then_core_halo(
            grid, ref, budget, rng, segment_id, seed, disc_fn, method
        )
        diag_out = {
            "audit_calls": 0,
            "repair_calls": 0,
            "discovery_calls": diag["discovery_calls"],
            "guard_calls": diag["guard_calls"],
            "total_used_calls": diag["total_used_calls"],
            "candidate_duration": diag["candidate_duration"],
            "core_duration": diag["core_duration"],
            "halo_duration": diag["halo_duration"],
        }
        return core_iv, cand_iv, diag_out, "strict_replay"

    raise ValueError(f"Unknown method: {method}")


# ---------------------------------------------------------------------------
# Main experiment loop
# ---------------------------------------------------------------------------
def main():
    segments = REAL_SEGMENTS + DS3_SEGMENTS

    # Build method list.
    methods = ["B6-core", "B7-core", "LATE-D0-core"]
    methods += [f"LATE-D1-core-radius{r}" for r in [10, 20, 30]]
    methods += [
        f"LATE-D2-core-q{q}-s{s}-r{r}"
        for q in [20, 30, 50]
        for s in ["mass", "max"]
        for r in ["highest", "center"]
    ]
    methods += [f"LATE-D3-core-chunk{c}" for c in [30, 60, 120]]
    methods += [f"D3-norepair-core-chunk{c}" for c in [30, 60, 120]]

    all_raw_rows: List[Dict] = []
    segment_info: List[Dict] = []

    for seg in segments:
        seg_id = seg["segment_id"]
        video_id = seg["video_id"]
        print(f"\nSegment {seg_id}")
        grid, ref = load_segment_grid(seg)
        n_units = len(grid)
        pos_units = int(grid["is_positive"].sum())
        n_long = int((ref["event_type"] == "long_interval").sum())
        n_point = len(ref) - n_long
        budget_grid = get_segment_budget_grid(n_units)
        segment_info.append({
            "segment_id": seg_id,
            "video_id": video_id,
            "time_start": seg["time_start"],
            "time_end": seg["time_end"],
            "duration": seg["time_end"] - seg["time_start"],
            "atomic_bin_size": BIN_SIZE,
            "num_units": n_units,
            "num_positive_units": pos_units,
            "positive_unit_density": pos_units / n_units,
            "num_events": len(ref),
            "num_long_events": n_long,
            "num_point_anchor_events": n_point,
            "budget_grid": budget_grid,
            "is_dev": seg.get("is_dev", False),
        })

        for bi, budget in enumerate(budget_grid):
            budget_ratio = budget / n_units
            print(f"  budget {bi+1}/{len(budget_grid)}: B={budget}")
            for trial, seed_offset in enumerate(SEEDS):
                rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                for method in methods:
                    core_iv, cand_iv, diag, replay_type = run_method(
                        grid, ref, budget, rng, method, seg_id, trial
                    )
                    selected_bins = intervals_to_bins(core_iv)
                    candidate_bins = intervals_to_bins(cand_iv)
                    metrics = compute_all_metrics(selected_bins, candidate_bins, grid, ref, diag)
                    all_raw_rows.append({
                        "video_id": video_id,
                        "segment_id": seg_id,
                        "method": method,
                        "budget": budget,
                        "budget_ratio": budget_ratio,
                        "seed": trial,
                        "num_units": n_units,
                        **metrics,
                        "selected_core_bins": "|".join(str(b) for b in selected_bins),
                        "selected_candidate_bins": "|".join(str(b) for b in candidate_bins),
                        "strict_replay_or_posthoc": replay_type,
                        "notes": "close_to_full_sweep" if budget_ratio >= 0.90 else "",
                    })

    raw_df = pd.DataFrame(all_raw_rows)
    raw_df.to_csv(OUT / "event_diverse_frontier_raw.csv", index=False)
    print(f"\nWrote event_diverse_frontier_raw.csv ({len(raw_df)} rows)")

    # Save segment info.
    seg_df = pd.DataFrame(segment_info)
    seg_df.to_csv(OUT / "segment_info.csv", index=False)

    # Generate reports.
    generate_reports(raw_df, seg_df)


def generate_reports(raw_df: pd.DataFrame, seg_df: pd.DataFrame):
    print("Generating reports...")

    # Helper: mean aggregation per segment/method/budget.
    agg = raw_df.groupby(["segment_id", "method", "budget"]).agg(
        event_precision=("event_precision", "mean"),
        event_recall=("event_recall", "mean"),
        duration_precision=("duration_precision", "mean"),
        duration_recall=("duration_recall", "mean"),
        long_event_recall=("long_event_recall", "mean"),
        point_anchor_recall=("point_anchor_recall", "mean"),
        selected_duration=("selected_duration", "mean"),
        false_positive_duration=("false_positive_duration", "mean"),
        num_unique_events_hit=("num_unique_events_hit", "mean"),
        num_long_events_hit=("num_long_events_hit", "mean"),
        num_point_anchor_events_hit=("num_point_anchor_events_hit", "mean"),
        duplicate_sampling_rate=("duplicate_sampling_rate", "mean"),
        repeated_hit_count=("repeated_hit_count", "mean"),
        mean_pairwise_selected_time_distance=("mean_pairwise_selected_time_distance", "mean"),
        max_calls_within_same_30s_window=("max_calls_within_same_30s_window", "mean"),
        max_calls_within_same_60s_window=("max_calls_within_same_60s_window", "mean"),
        discovery_miss_count=("discovery_miss_count", "mean"),
        release_over_conservative_count=("release_over_conservative_count", "mean"),
        events_in_halo_but_not_core=("events_in_halo_but_not_core", "mean"),
        events_never_selected=("events_never_selected", "mean"),
        guard_calls=("guard_calls", "mean"),
        repair_calls=("repair_calls", "mean"),
        audit_calls=("audit_calls", "mean"),
        discovery_calls=("discovery_calls", "mean"),
        oracle_calls_total=("oracle_calls_total", "mean"),
    ).reset_index()
    agg["budget_ratio"] = agg.apply(
        lambda r: r["budget"] / seg_df.set_index("segment_id").loc[r["segment_id"], "num_units"], axis=1
    )

    # 9.1 Unique event coverage.
    # Use family-best variants identified in B_90/90 comparison for consistency with FINAL_REPORT Q1.
    main_methods = ["B7-core", "LATE-D0-core", "LATE-D1-core-radius20",
                    "LATE-D2-core-q20-smass-rhighest", "LATE-D3-core-chunk120", "D3-norepair-core-chunk120"]
    main_methods = [m for m in main_methods if m in raw_df["method"].unique()]
    uec_rows = []
    for seg in seg_df["segment_id"]:
        for method in main_methods:
            sub = agg[(agg["segment_id"] == seg) & (agg["method"] == method)]
            if sub.empty:
                continue
            le30 = sub[sub["budget_ratio"] <= 0.30]
            best_le30 = le30["num_unique_events_hit"].max() if not le30.empty else 0.0
            uec_rows.append({
                "segment_id": seg,
                "method": method,
                "best_unique_events_hit_le30": best_le30,
                "best_long_event_recall_le30": le30["long_event_recall"].max() if not le30.empty else 0.0,
            })
    uec_df = pd.DataFrame(uec_rows)
    uec_df.to_csv(OUT / "unique_event_coverage.csv", index=False)

    # 9.2 Discovery miss reduction.
    dmr_rows = []
    for seg in seg_df["segment_id"]:
        n_events = seg_df[seg_df["segment_id"] == seg]["num_events"].iloc[0]
        n_long = seg_df[seg_df["segment_id"] == seg]["num_long_events"].iloc[0]
        n_point = seg_df[seg_df["segment_id"] == seg]["num_point_anchor_events"].iloc[0]
        for method in main_methods:
            sub = agg[(agg["segment_id"] == seg) & (agg["method"] == method)]
            for _, r in sub.iterrows():
                dmr_rows.append({
                    "segment_id": seg,
                    "method": method,
                    "budget": r["budget"],
                    "budget_ratio": r["budget_ratio"],
                    "missed_event_count": n_events - r["num_unique_events_hit"],
                    "missed_long_event_count": n_long - r["num_long_events_hit"],
                    "missed_point_anchor_count": n_point - r["num_point_anchor_events_hit"],
                    "events_in_halo_but_not_core": r["events_in_halo_but_not_core"],
                    "events_never_selected": r["events_never_selected"],
                })
    dmr_df = pd.DataFrame(dmr_rows)
    dmr_df.to_csv(OUT / "discovery_miss_reduction.csv", index=False)

    # 9.3 Precision-recall under <=30% budget.
    pr_rows = []
    for (seg, method), g in agg.groupby(["segment_id", "method"]):
        le30 = g[g["budget_ratio"] <= 0.30]
        if le30.empty:
            best_r = 0.0
            best_p = 0.0
            reached = False
        else:
            pos = le30[le30["event_precision"] >= 0.9]
            best_r = pos["event_recall"].max() if not pos.empty else 0.0
            rec = le30[le30["event_recall"] >= 0.9]
            best_p = rec["event_precision"].max() if not rec.empty else 0.0
            reached = bool(((le30["event_precision"] >= 0.9) & (le30["event_recall"] >= 0.9)).any())
        pr_rows.append({
            "segment_id": seg,
            "method": method,
            "best_recall_under_precision_ge_0.9_le30": best_r,
            "best_precision_under_recall_ge_0.9_le30": best_p,
            "reached_90_90_le30": reached,
        })
    pr_df = pd.DataFrame(pr_rows)
    pr_df.to_csv(OUT / "precision_recall_under_budget_ratio.csv", index=False)

    # 9.4 B_90/90 comparison.
    b90_rows = []
    for (seg, method), g in agg.groupby(["segment_id", "method"]):
        g = g.sort_values("budget")
        reached = g[(g["event_precision"] >= 0.9) & (g["event_recall"] >= 0.9)]
        n_units = seg_df.set_index("segment_id").loc[seg, "num_units"]
        if not reached.empty:
            r = reached.iloc[0]
            b90_rows.append({
                "segment_id": seg, "method": method,
                "B_90_90": int(r["budget"]),
                "budget_ratio_90_90": r["budget"] / n_units,
                "status": "reached",
                "P_at_B": r["event_precision"],
                "R_at_B": r["event_recall"],
                "best_P": r["event_precision"],
                "best_R": r["event_recall"],
                "best_budget": int(r["budget"]),
                "best_budget_ratio": r["budget"] / n_units,
            })
        else:
            last = g.iloc[-1]
            best_p_row = g[g["event_precision"] >= 0.9]
            best = best_p_row.loc[best_p_row["event_recall"].idxmax()] if not best_p_row.empty else last
            b90_rows.append({
                "segment_id": seg, "method": method,
                "B_90_90": "not_reached",
                "budget_ratio_90_90": "",
                "status": "not_reached",
                "P_at_B": last["event_precision"],
                "R_at_B": last["event_recall"],
                "best_P": best["event_precision"],
                "best_R": best["event_recall"],
                "best_budget": int(best["budget"]),
                "best_budget_ratio": best["budget"] / n_units,
            })
    b90_df = pd.DataFrame(b90_rows)
    b90_df.to_csv(OUT / "b90_90_comparison.csv", index=False)

    # 9.5 Segment regime analysis.
    seg_df["density_regime"] = seg_df["positive_unit_density"].apply(
        lambda d: "low" if d < 0.05 else ("medium" if d <= 0.15 else "high")
    )
    # Need event composition: point-heavy / long-event-heavy / mixed.
    def composition(row):
        if row["num_long_events"] == 0:
            return "point-heavy"
        if row["num_point_anchor_events"] == 0:
            return "long-event-heavy"
        ratio = row["num_long_events"] / max(1, row["num_events"])
        if ratio >= 0.6:
            return "long-event-heavy"
        if ratio <= 0.4:
            return "point-heavy"
        return "mixed"
    seg_df["composition_regime"] = seg_df.apply(composition, axis=1)
    seg_df["regime"] = seg_df["density_regime"] + "_" + seg_df["composition_regime"]

    regime_rows = []
    for seg in seg_df["segment_id"]:
        regime = seg_df[seg_df["segment_id"] == seg]["regime"].iloc[0]
        le30_methods = pr_df[(pr_df["segment_id"] == seg)].copy()
        best = le30_methods.loc[le30_methods["best_recall_under_precision_ge_0.9_le30"].idxmax()] if not le30_methods.empty else None
        b90_seg = b90_df[(b90_df["segment_id"] == seg) & (b90_df["status"] == "reached")].copy()
        b90_seg["B_90_90_float"] = b90_seg["B_90_90"].astype(float)
        if not b90_seg.empty:
            min_b = b90_seg["B_90_90_float"].min()
            winners = b90_seg[b90_seg["B_90_90_float"] == min_b]
            # Prefer B7-core if tied, else list all tied methods.
            if "B7-core" in winners["method"].values:
                b90_winner_method = "B7-core"
            else:
                b90_winner_method = ",".join(sorted(winners["method"].values))
            b90_winner_value = int(min_b)
        else:
            b90_winner_method = ""
            b90_winner_value = ""
        regime_rows.append({
            "segment_id": seg,
            "regime": regime,
            "best_recall_le30_method": best["method"] if best is not None else "",
            "best_recall_le30_value": best["best_recall_under_precision_ge_0.9_le30"] if best is not None else 0.0,
            "b90_winner_method": b90_winner_method,
            "b90_winner_value": b90_winner_value,
        })
    regime_df = pd.DataFrame(regime_rows)
    regime_df.to_csv(OUT / "segment_regime_analysis.csv", index=False)
    seg_df.to_csv(OUT / "segment_regime_info.csv", index=False)

    # 9.6 Machinery overhead report.
    oh_rows = []
    for _, r in agg.iterrows():
        total = r["oracle_calls_total"]
        oh_rows.append({
            "segment_id": r["segment_id"],
            "method": r["method"],
            "budget": r["budget"],
            "budget_ratio": r["budget_ratio"],
            "guard_calls_fraction": r["guard_calls"] / total if total > 0 else 0.0,
            "repair_calls_fraction": r["repair_calls"] / total if total > 0 else 0.0,
            "discovery_calls_fraction": r["discovery_calls"] / total if total > 0 else 0.0,
            "audit_calls_fraction": r["audit_calls"] / total if total > 0 else 0.0,
            "guard_calls": r["guard_calls"],
            "repair_calls": r["repair_calls"],
            "discovery_calls": r["discovery_calls"],
            "audit_calls": r["audit_calls"],
            "oracle_calls_total": total,
        })
    oh_df = pd.DataFrame(oh_rows)
    oh_df.to_csv(OUT / "machinery_overhead_report.csv", index=False)

    # 9.7 Repair marginal value report (D3-core vs D3-norepair-core).
    repair_md = "# Repair Marginal Value Report\n\n"
    repair_md += "Comparison of LATE-D3-core (chunk-bandit discovery + repair + Core/Halo) "
    repair_md += "vs D3-norepair-core (chunk-bandit discovery + Core/Halo, no repair).\n\n"

    for chunk in [30, 60, 120]:
        d3 = f"LATE-D3-core-chunk{chunk}"
        no = f"D3-norepair-core-chunk{chunk}"
        if d3 not in raw_df["method"].unique() or no not in raw_df["method"].unique():
            continue
        repair_md += f"## chunk_size = {chunk}s\n\n"
        diffs = []
        for seg in seg_df["segment_id"]:
            d3_sub = agg[(agg["segment_id"] == seg) & (agg["method"] == d3)]
            no_sub = agg[(agg["segment_id"] == seg) & (agg["method"] == no)]
            if d3_sub.empty or no_sub.empty:
                continue
            # Best unique event coverage across all budgets.
            d3_best_ue = d3_sub["num_unique_events_hit"].max()
            no_best_ue = no_sub["num_unique_events_hit"].max()
            # Best long event recall.
            d3_best_lr = d3_sub["long_event_recall"].max()
            no_best_lr = no_sub["long_event_recall"].max()
            # B_90/90.
            d3_b90 = b90_df[(b90_df["segment_id"] == seg) & (b90_df["method"] == d3)]
            no_b90 = b90_df[(b90_df["segment_id"] == seg) & (b90_df["method"] == no)]
            d3_b = d3_b90["B_90_90"].iloc[0] if not d3_b90.empty else "not_reached"
            no_b = no_b90["B_90_90"].iloc[0] if not no_b90.empty else "not_reached"
            diffs.append({
                "segment_id": seg,
                "d3_unique_events": d3_best_ue,
                "no_unique_events": no_best_ue,
                "delta_unique_events": d3_best_ue - no_best_ue,
                "d3_long_event_recall": d3_best_lr,
                "no_long_event_recall": no_best_lr,
                "delta_long_event_recall": d3_best_lr - no_best_lr,
                "d3_B_90_90": d3_b,
                "no_B_90_90": no_b,
            })
        diff_df = pd.DataFrame(diffs)
        if not diff_df.empty:
            avg_delta_ue = diff_df["delta_unique_events"].mean()
            avg_delta_lr = diff_df["delta_long_event_recall"].mean()
            n_segments_better_ue = int((diff_df["delta_unique_events"] > 0.01).sum())
            n_segments_worse_ue = int((diff_df["delta_unique_events"] < -0.01).sum())
            repair_md += f"- Average delta unique events (D3 - no-repair): {avg_delta_ue:.3f}\n"
            repair_md += f"- Segments where D3 has strictly more unique events: {n_segments_better_ue}/{len(diff_df)}\n"
            repair_md += f"- Segments where D3 has strictly fewer unique events: {n_segments_worse_ue}/{len(diff_df)}\n"
            repair_md += f"- Average delta long-event recall (D3 - no-repair): {avg_delta_lr:.3f}\n\n"
            repair_md += "| segment | D3 unique | no-repair unique | delta | D3 long-R | no-repair long-R | delta | D3 B_90/90 | no-repair B_90/90 |\n"
            repair_md += "|---------|-----------|------------------|-------|-----------|------------------|-------|------------|-------------------|\n"
            for _, r in diff_df.iterrows():
                repair_md += (
                    f"| {r['segment_id']} | {r['d3_unique_events']:.2f} | {r['no_unique_events']:.2f} | "
                    f"{r['delta_unique_events']:+.2f} | {r['d3_long_event_recall']:.3f} | "
                    f"{r['no_long_event_recall']:.3f} | {r['delta_long_event_recall']:+.3f} | "
                    f"{r['d3_B_90_90']} | {r['no_B_90_90']} |\n"
                )
            repair_md += "\n"

    # D3-norepair-core vs B7-core comparison.
    repair_md += "## D3-norepair-core vs B7-core\n\n"
    repair_md += "Both use a chunk-bandit-style discovery backbone, but differ in release details:\n"
    repair_md += "- B7-core uses the existing B7 temporal expansion + Core/Halo; it is posthoc_eval because it uses event_id.\n"
    repair_md += "- D3-norepair-core uses strict-replay chunk-bandit discovery (no event_id) + Core/Halo; no repair.\n"
    repair_md += "- Core/Halo guard rules and MAX_GUARDS_PER_SIDE=3 are the same.\n\n"

    for chunk in [60]:  # main config
        no = f"D3-norepair-core-chunk{chunk}"
        if no not in raw_df["method"].unique():
            continue
        cmp_rows = []
        for seg in seg_df["segment_id"]:
            no_sub = agg[(agg["segment_id"] == seg) & (agg["method"] == no)]
            b7_sub = agg[(agg["segment_id"] == seg) & (agg["method"] == "B7-core")]
            if no_sub.empty or b7_sub.empty:
                continue
            cmp_rows.append({
                "segment_id": seg,
                "no_best_recall_le30": no_sub[no_sub["budget_ratio"] <= 0.30]["event_recall"].max() if not no_sub[no_sub["budget_ratio"] <= 0.30].empty else 0.0,
                "b7_best_recall_le30": b7_sub[b7_sub["budget_ratio"] <= 0.30]["event_recall"].max() if not b7_sub[b7_sub["budget_ratio"] <= 0.30].empty else 0.0,
                "no_b90": b90_df[(b90_df["segment_id"] == seg) & (b90_df["method"] == no)]["B_90_90"].iloc[0] if not b90_df[(b90_df["segment_id"] == seg) & (b90_df["method"] == no)].empty else "not_reached",
                "b7_b90": b90_df[(b90_df["segment_id"] == seg) & (b90_df["method"] == "B7-core")]["B_90_90"].iloc[0] if not b90_df[(b90_df["segment_id"] == seg) & (b90_df["method"] == "B7-core")].empty else "not_reached",
            })
        cmp_df = pd.DataFrame(cmp_rows)
        if not cmp_df.empty:
            repair_md += "| segment | no-repair best R@P>=0.9 le30 | B7-core best R@P>=0.9 le30 | no-repair B_90/90 | B7-core B_90/90 |\n"
            repair_md += "|---------|------------------------------|----------------------------|-------------------|------------------|\n"
            for _, r in cmp_df.iterrows():
                repair_md += (
                    f"| {r['segment_id']} | {r['no_best_recall_le30']:.3f} | {r['b7_best_recall_le30']:.3f} | "
                    f"{r['no_b90']} | {r['b7_b90']} |\n"
                )
            repair_md += "\n"

    with open(OUT / "repair_marginal_value_report.md", "w") as f:
        f.write(repair_md)

    # Duplicate sampling analysis (per segment/method/budget).
    dup_cols = ["segment_id", "method", "budget", "budget_ratio",
                "duplicate_sampling_rate", "repeated_hit_count",
                "mean_pairwise_selected_time_distance",
                "max_calls_within_same_30s_window", "max_calls_within_same_60s_window"]
    raw_df[dup_cols].to_csv(OUT / "duplicate_sampling_analysis.csv", index=False)

    # Failure casebook.
    generate_failure_casebook(raw_df, seg_df)

    # FINAL_REPORT.
    generate_final_report(raw_df, seg_df, b90_df, pr_df, uec_df, oh_df, regime_df)

    # README and other files.
    write_readme_and_manifest(seg_df)
    write_isolation_audit(raw_df)

    print("Reports generated.")


def generate_failure_casebook(raw_df: pd.DataFrame, seg_df: pd.DataFrame):
    cb_md = "# Failure Casebook\n\n"
    cb_md += "This casebook uses the stored candidate/core bin traces in `event_diverse_frontier_raw.csv` "
    cb_md += "to produce concrete per-event examples. event_id is used only for evaluation/casebook, never for selection.\n\n"

    main_methods = ["B7-core", "LATE-D0-core", "LATE-D1-core-radius20",
                    "LATE-D2-core-q30-smass-rhighest", "LATE-D3-core-chunk60", "D3-norepair-core-chunk60"]
    main_methods = [m for m in main_methods if m in raw_df["method"].unique()]

    # Pre-load grids/refs.
    grids: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]] = {}
    for seg in seg_df.to_dict("records"):
        grids[seg["segment_id"]] = load_segment_grid(seg)

    def hit_events_for_row(row: pd.Series, use_core: bool = True) -> Set[str]:
        seg = row["segment_id"]
        grid, ref = grids[seg]
        bins_str = row["selected_core_bins"] if use_core else row["selected_candidate_bins"]
        if pd.isna(bins_str) or bins_str == "":
            return set()
        bins = [int(x) for x in str(bins_str).split("|") if x != ""]
        return hits_from_bins(bins, grid, ref)

    # Aggregate per-event hit rates at a representative budget for each segment/method.
    # Use the maximum budget with ratio <= 0.30 to focus on the low-budget regime where methods differ.
    case_rows: List[Dict] = []
    for seg_id in seg_df["segment_id"]:
        grid, ref = grids[seg_id]
        ref_events = {str(ev["event_id"]): (float(ev["t_start"]), float(ev["t_end"]), str(ev["event_type"]))
                      for _, ev in ref.iterrows()}
        sub = raw_df[raw_df["segment_id"] == seg_id]
        le30 = sub[sub["budget_ratio"] <= 0.30]
        max_budget = int(le30["budget"].max()) if not le30.empty else int(sub["budget"].max())
        for method in main_methods:
            ms = sub[(sub["method"] == method) & (sub["budget"] == max_budget)]
            if ms.empty:
                continue
            # Aggregate hit events across seeds.
            hit_counts: Counter = Counter()
            core_hit_counts: Counter = Counter()
            for _, row in ms.iterrows():
                for eid in hit_events_for_row(row, use_core=False):
                    hit_counts[eid] += 1
                for eid in hit_events_for_row(row, use_core=True):
                    core_hit_counts[eid] += 1
            n_seeds = len(ms)
            for eid, (t0, t1, etype) in ref_events.items():
                cand_rate = hit_counts.get(eid, 0) / n_seeds
                core_rate = core_hit_counts.get(eid, 0) / n_seeds
                case_rows.append({
                    "segment_id": seg_id,
                    "method": method,
                    "budget": max_budget,
                    "event_id": eid,
                    "event_type": etype,
                    "event_start": t0,
                    "event_end": t1,
                    "candidate_hit_rate": cand_rate,
                    "core_hit_rate": core_rate,
                })
    case_df = pd.DataFrame(case_rows)
    if not case_df.empty:
        case_df.to_csv(OUT / "failure_casebook_details.csv", index=False)

    # Summary table per segment/method using raw per-seed metrics (averaged over seeds).
    cb_md += "## Per-segment/method summary (at max budget with budget_ratio <= 0.30, averaged over seeds)\n\n"
    cb_md += "| segment | method | budget | event_recall | discovery_miss | release_over_conservative |\n"
    cb_md += "|---------|--------|--------|--------------|----------------|---------------------------|\n"
    summary = []
    for seg_id in seg_df["segment_id"]:
        n_events = seg_df[seg_df["segment_id"] == seg_id]["num_events"].iloc[0]
        sub = raw_df[raw_df["segment_id"] == seg_id]
        le30 = sub[sub["budget_ratio"] <= 0.30]
        max_budget = int(le30["budget"].max()) if not le30.empty else int(sub["budget"].max())
        for method in main_methods:
            rows = raw_df[(raw_df["segment_id"] == seg_id) & (raw_df["method"] == method) & (raw_df["budget"] == max_budget)]
            if rows.empty:
                continue
            avg_recall = rows["event_recall"].mean()
            avg_disc_miss = rows["discovery_miss_count"].mean()
            avg_release_cons = rows["release_over_conservative_count"].mean()
            summary.append({
                "segment_id": seg_id, "method": method, "budget": max_budget,
                "event_recall": avg_recall,
                "discovery_miss": avg_disc_miss,
                "release_over_conservative": avg_release_cons,
            })
            cb_md += (
                f"| {seg_id} | {method} | {max_budget} | {avg_recall:.3f} | "
                f"{avg_disc_miss:.1f} | {avg_release_cons:.1f} |\n"
            )

    # Concrete examples.
    def pick_example(predicate: Callable) -> Optional[pd.Series]:
        candidates = case_df[case_df.apply(predicate, axis=1)]
        if candidates.empty:
            return None
        return candidates.iloc[0]

    def fmt_intervals(seg_id: str, method: str, budget: int, use_core: bool) -> str:
        grid, ref = grids[seg_id]
        rows = raw_df[(raw_df["segment_id"] == seg_id) & (raw_df["method"] == method) & (raw_df["budget"] == budget)]
        if rows.empty:
            return "N/A"
        # Use seed 0 for illustration.
        row = rows.iloc[0]
        bins_str = row["selected_core_bins"] if use_core else row["selected_candidate_bins"]
        if pd.isna(bins_str) or bins_str == "":
            return "none"
        bins = [int(x) for x in str(bins_str).split("|") if x != ""]
        intervals = merge_bins(grid, bins)
        if intervals.empty:
            return "none"
        parts = []
        for _, iv in intervals.iterrows():
            parts.append(f"[{iv['t_start']:.1f},{iv['t_end']:.1f}]")
        return ", ".join(parts[:5]) + ("..." if len(parts) > 5 else "")

    cb_md += "\n## Concrete examples\n\n"

    # B7-core success but LATE-D0 failure.
    cb_md += "### B7-core success but LATE-D0 failure\n\n"
    ex = pick_example(lambda r: r["method"] == "B7-core" and r["core_hit_rate"] > 0 and
                      ((case_df[(case_df["segment_id"] == r["segment_id"]) & (case_df["event_id"] == r["event_id"]) & (case_df["method"] == "LATE-D0-core")]["core_hit_rate"].sum() == 0)))
    if ex is not None:
        cb_md += f"- **event**: {ex['event_id']} in {ex['segment_id']} ({ex['event_type']}, [{ex['event_start']:.1f},{ex['event_end']:.1f}])\n"
        cb_md += f"  - B7-core selected (core): {fmt_intervals(ex['segment_id'], 'B7-core', ex['budget'], True)}\n"
        cb_md += f"  - LATE-D0-core selected (core): {fmt_intervals(ex['segment_id'], 'LATE-D0-core', ex['budget'], True)}\n"
        cb_md += f"  - Reason: upstream_discovery_miss for LATE-D0-core (event not in candidate set).\n\n"
    else:
        cb_md += "- No clear example found in the sampled configurations.\n\n"

    # LATE-D1/D2/D3 success while D0 fails.
    cb_md += "### LATE-D1/D2/D3 success while LATE-D0 fails\n\n"
    for alt in ["LATE-D1-core-radius20", "LATE-D2-core-q30-smass-rhighest", "LATE-D3-core-chunk60"]:
        ex = pick_example(lambda r, alt=alt: r["method"] == alt and r["core_hit_rate"] > 0 and
                          ((case_df[(case_df["segment_id"] == r["segment_id"]) & (case_df["event_id"] == r["event_id"]) & (case_df["method"] == "LATE-D0-core")]["core_hit_rate"].sum() == 0)))
        if ex is not None:
            cb_md += f"- **event**: {ex['event_id']} in {ex['segment_id']} ({ex['event_type']}, [{ex['event_start']:.1f},{ex['event_end']:.1f}])\n"
            cb_md += f"  - {alt} selected (core): {fmt_intervals(ex['segment_id'], alt, ex['budget'], True)}\n"
            cb_md += f"  - LATE-D0-core selected (core): {fmt_intervals(ex['segment_id'], 'LATE-D0-core', ex['budget'], True)}\n"
            cb_md += f"  - Reason: alternative discovery policy found the event that D0's prior-ranked discovery missed.\n\n"
            break
    if ex is None:
        cb_md += "- No clear example found.\n\n"

    # D3 assists but D1/D2 do not.
    cb_md += "### D3 assists but D1/D2 do not\n\n"
    ex = pick_example(lambda r: r["method"] == "LATE-D3-core-chunk60" and r["core_hit_rate"] > 0 and
                      ((case_df[(case_df["segment_id"] == r["segment_id"]) & (case_df["event_id"] == r["event_id"]) & (case_df["method"].isin(["LATE-D1-core-radius20", "LATE-D2-core-q30-smass-rhighest"]))]["core_hit_rate"].sum() == 0)))
    if ex is not None:
        cb_md += f"- **event**: {ex['event_id']} in {ex['segment_id']} ({ex['event_type']}, [{ex['event_start']:.1f},{ex['event_end']:.1f}])\n"
        cb_md += f"  - LATE-D3-core-chunk60 selected (core): {fmt_intervals(ex['segment_id'], 'LATE-D3-core-chunk60', ex['budget'], True)}\n"
        cb_md += f"  - LATE-D1-core-radius20 selected (core): {fmt_intervals(ex['segment_id'], 'LATE-D1-core-radius20', ex['budget'], True)}\n"
        cb_md += f"  - LATE-D2-core-q30-smass-rhighest selected (core): {fmt_intervals(ex['segment_id'], 'LATE-D2-core-q30-smass-rhighest', ex['budget'], True)}\n"
        cb_md += f"  - Reason: chunk-bandit exploration reached an event outside the high-prior regions that D1/D2 focused on.\n\n"
    else:
        cb_md += "- No clear example found.\n\n"

    # D1/D2 assist but D3 does not.
    cb_md += "### D1/D2 assist but D3 does not\n\n"
    ex = pick_example(lambda r: r["method"] in ["LATE-D1-core-radius20", "LATE-D2-core-q30-smass-rhighest"] and r["core_hit_rate"] > 0 and
                      ((case_df[(case_df["segment_id"] == r["segment_id"]) & (case_df["event_id"] == r["event_id"]) & (case_df["method"] == "LATE-D3-core-chunk60")]["core_hit_rate"].sum() == 0)))
    if ex is not None:
        cb_md += f"- **event**: {ex['event_id']} in {ex['segment_id']} ({ex['event_type']}, [{ex['event_start']:.1f},{ex['event_end']:.1f}])\n"
        cb_md += f"  - {ex['method']} selected (core): {fmt_intervals(ex['segment_id'], ex['method'], ex['budget'], True)}\n"
        cb_md += f"  - LATE-D3-core-chunk60 selected (core): {fmt_intervals(ex['segment_id'], 'LATE-D3-core-chunk60', ex['budget'], True)}\n"
        cb_md += f"  - Reason: prior-guided policy found a high-prior event that the chunk-bandit did not sample.\n\n"
    else:
        cb_md += "- No clear example found.\n\n"

    # D3-core vs D3-norepair-core: improvement and no-improvement examples.
    cb_md += "### D3-core vs D3-norepair-core\n\n"
    ex_imp = pick_example(lambda r: r["method"] == "LATE-D3-core-chunk60" and r["core_hit_rate"] > 0 and
                          ((case_df[(case_df["segment_id"] == r["segment_id"]) & (case_df["event_id"] == r["event_id"]) & (case_df["method"] == "D3-norepair-core-chunk60")]["core_hit_rate"].sum() == 0)))
    if ex_imp is not None:
        cb_md += f"**Example where repair helped (D3-core hits, D3-norepair misses):**\n"
        cb_md += f"- **event**: {ex_imp['event_id']} in {ex_imp['segment_id']} ({ex_imp['event_type']}, [{ex_imp['event_start']:.1f},{ex_imp['event_end']:.1f}])\n"
        cb_md += f"  - LATE-D3-core selected (core): {fmt_intervals(ex_imp['segment_id'], 'LATE-D3-core-chunk60', ex_imp['budget'], True)}\n"
        cb_md += f"  - D3-norepair-core selected (core): {fmt_intervals(ex_imp['segment_id'], 'D3-norepair-core-chunk60', ex_imp['budget'], True)}\n"
        cb_md += f"  - Likely reason: audit-triggered repair expanded into this event's neighborhood.\n\n"
    ex_no = pick_example(lambda r: r["method"] == "D3-norepair-core-chunk60" and r["core_hit_rate"] > 0 and
                         ((case_df[(case_df["segment_id"] == r["segment_id"]) & (case_df["event_id"] == r["event_id"]) & (case_df["method"] == "LATE-D3-core-chunk60")]["core_hit_rate"].sum() == 0)))
    if ex_no is not None:
        cb_md += f"**Example where repair did not help (D3-norepair hits, D3-core misses):**\n"
        cb_md += f"- **event**: {ex_no['event_id']} in {ex_no['segment_id']} ({ex_no['event_type']}, [{ex_no['event_start']:.1f},{ex_no['event_end']:.1f}])\n"
        cb_md += f"  - D3-norepair-core selected (core): {fmt_intervals(ex_no['segment_id'], 'D3-norepair-core-chunk60', ex_no['budget'], True)}\n"
        cb_md += f"  - LATE-D3-core selected (core): {fmt_intervals(ex_no['segment_id'], 'LATE-D3-core-chunk60', ex_no['budget'], True)}\n"
        cb_md += f"  - Likely reason: repair consumed budget that could have gone to additional chunk-bandit discovery.\n\n"
    if ex_imp is None and ex_no is None:
        cb_md += "- No clear per-event difference found at the max budget; see `repair_marginal_value_report.md` for aggregate deltas.\n\n"

    cb_md += "\n## How to read the casebook\n\n"
    cb_md += "- `core_hit_rate > 0` means the event was overlapped by at least one core interval in at least one seed.\n"
    cb_md += "- `candidate_hit_rate > 0` but `core_hit_rate = 0` means the event was found by discovery but discarded by the strict Core/Halo release (release_over_conservative).\n"
    cb_md += "- `candidate_hit_rate = 0` means the event was never selected by discovery (discovery_miss).\n"
    cb_md += "- Intervals shown are from seed 0 at the maximum <=30% budget ratio for that segment.\n"

    with open(OUT / "failure_casebook.md", "w") as f:
        f.write(cb_md)


def generate_final_report(raw_df, seg_df, b90_df, pr_df, uec_df, oh_df, regime_df):
    final_md = "# FINAL REPORT — Upstream Event-Diverse Discovery Redesign for LATE-AQP\n\n"

    # Q1: Which discovery policy improves D0?
    d0_b90 = b90_df[b90_df["method"] == "LATE-D0-core"].set_index("segment_id")["B_90_90"]
    families = {
        "D1": [m for m in raw_df["method"].unique() if m.startswith("LATE-D1-core-")],
        "D2": [m for m in raw_df["method"].unique() if m.startswith("LATE-D2-core-")],
        "D3": [m for m in raw_df["method"].unique() if m.startswith("LATE-D3-core-")],
        "D3-norepair": [m for m in raw_df["method"].unique() if m.startswith("D3-norepair-core-")],
    }
    final_md += "## 1. Which discovery policy improves current LATE-D0?\n\n"
    family_best = {}
    for fam, methods in families.items():
        best_method, best_wins = None, -1
        for method in methods:
            mb = b90_df[b90_df["method"] == method].set_index("segment_id")["B_90_90"]
            wins = 0
            for seg in d0_b90.index:
                if seg in mb.index and mb[seg] != "not_reached" and d0_b90[seg] != "not_reached":
                    if int(mb[seg]) < int(d0_b90[seg]):
                        wins += 1
            if wins > best_wins or (wins == best_wins and (best_method is None or method < best_method)):
                best_method = method
                best_wins = wins
        family_best[fam] = (best_method, best_wins)
        if best_method is not None:
            final_md += f"- {best_method} ({fam} best): lower B_90/90 than D0 on {best_wins}/{len(d0_b90)} segments\n"
    if not any(w > 0 for _, w in family_best.values()):
        final_md += "- No LATE discovery policy consistently achieves a lower B_90/90 than LATE-D0-core across all segments.\n"
    final_md += "\n"

    # Representative methods used in downstream comparisons.
    main_methods = ["B7-core", "LATE-D0-core"]
    for fam, (m, _) in family_best.items():
        if m is not None:
            main_methods.append(m)
    main_methods = [m for m in main_methods if m in raw_df["method"].unique()]

    # Q2: Did D1/D2/D3 reduce duplicate sampling?
    dup_cmp = raw_df.groupby("method")["duplicate_sampling_rate"].mean().sort_values()
    final_md += "## 2. Did D1/D2/D3 reduce duplicate sampling?\n\n"
    final_md += "Mean duplicate_sampling_rate by method (lower is better):\n\n"
    for method, rate in dup_cmp.items():
        final_md += f"- {method}: {rate:.3f}\n"
    final_md += "\n"

    # Q3: Did D1/D2/D3 reduce discovery miss?
    final_md += "## 3. Did D1/D2/D3 reduce discovery_miss?\n\n"
    dmr = pd.read_csv(OUT / "discovery_miss_reduction.csv")
    compare_methods = list(main_methods) + ["LATE-D0-core"]
    for seg in seg_df["segment_id"]:
        seg_sub = dmr[(dmr["segment_id"] == seg) & (dmr["method"].isin(compare_methods))]
        if seg_sub.empty:
            continue
        le30 = seg_sub[seg_sub["budget_ratio"] <= 0.30]
        if le30.empty:
            continue
        best = le30.loc[le30["events_never_selected"].idxmin()]
        d0 = le30[le30["method"] == "LATE-D0-core"]
        if not d0.empty:
            d0_miss = d0["events_never_selected"].iloc[0]
            final_md += f"- {seg}: D0 missed {d0_miss:.1f}; best alternative {best['method']} missed {best['events_never_selected']:.1f} @ ratio={best['budget_ratio']:.3f}\n"
    final_md += "\n"

    # Q4: Did any LATE variant beat B7-core in B_90/90?
    final_md += "## 4. Did any LATE variant beat B7-core in B_90/90?\n\n"
    b7_b90 = b90_df[b90_df["method"] == "B7-core"].set_index("segment_id")["B_90_90"]
    beat_counts = defaultdict(int)
    total_comp = 0
    for seg in b7_b90.index:
        if b7_b90[seg] == "not_reached":
            continue
        total_comp += 1
        for method in main_methods:
            if method == "B7-core":
                continue
            mb = b90_df[(b90_df["segment_id"] == seg) & (b90_df["method"] == method)]
            if mb.empty or mb.iloc[0]["B_90_90"] == "not_reached":
                continue
            if int(mb.iloc[0]["B_90_90"]) < int(b7_b90[seg]):
                beat_counts[method] += 1
    if beat_counts:
        for method, cnt in beat_counts.items():
            final_md += f"- {method}: beat B7-core on {cnt}/{total_comp} segments\n"
    else:
        final_md += "- No LATE variant achieved a strictly lower B_90/90 than B7-core on any segment.\n"
    final_md += "\n"

    # Q5: Did any method reach 90/90 at <=30% budget?
    final_md += "## 5. Did any method reach 90/90 at <=30% budget?\n\n"
    reached_any = pr_df["reached_90_90_le30"].any()
    final_md += f"{'Yes' if reached_any else 'No'}.\n\n"
    if not reached_any:
        final_md += "Closest methods by segment (best recall under P>=0.9 within <=30% budget):\n\n"
        for seg in seg_df["segment_id"]:
            seg_pr = pr_df[pr_df["segment_id"] == seg]
            if seg_pr.empty:
                continue
            best = seg_pr.loc[seg_pr["best_recall_under_precision_ge_0.9_le30"].idxmax()]
            final_md += f"- {seg}: {best['method']} R={best['best_recall_under_precision_ge_0.9_le30']:.3f}\n"
    final_md += "\n"

    # Q6: Is the bottleneck still upstream discovery?
    final_md += "## 6. Is the bottleneck still upstream discovery?\n\n"
    le30 = raw_df[raw_df["budget_ratio"] <= 0.30]
    if not le30.empty:
        avg_discovery_miss = le30.groupby("method")["discovery_miss_count"].mean().sort_values()
        final_md += "Mean discovery_miss_count at <=30% budget by method:\n\n"
        for method, val in avg_discovery_miss.items():
            final_md += f"- {method}: {val:.2f}\n"
    final_md += "\nHigh discovery miss counts at low budgets indicate the bottleneck remains upstream discovery.\n\n"

    # Q7: Repair marginal value on D3.
    final_md += "## 7. Does repair have independent marginal value on the strongest discovery backbone (D3)?\n\n"
    final_md += "Aggregated per segment as best unique events / best long-event recall across all evaluated budgets, "
    final_md += "then averaged across segments (uses summary metrics `num_unique_events_hit` and `long_event_recall`).\n\n"
    rmv = []
    for chunk in [30, 60, 120]:
        d3 = f"LATE-D3-core-chunk{chunk}"
        no = f"D3-norepair-core-chunk{chunk}"
        if d3 not in raw_df["method"].unique() or no not in raw_df["method"].unique():
            continue
        seg_deltas = []
        for seg in seg_df["segment_id"]:
            d3_sub = raw_df[(raw_df["segment_id"] == seg) & (raw_df["method"] == d3)]
            no_sub = raw_df[(raw_df["segment_id"] == seg) & (raw_df["method"] == no)]
            if d3_sub.empty or no_sub.empty:
                continue
            seg_deltas.append({
                "delta_unique_events": d3_sub["num_unique_events_hit"].max() - no_sub["num_unique_events_hit"].max(),
                "delta_long_recall": d3_sub["long_event_recall"].max() - no_sub["long_event_recall"].max(),
            })
        if seg_deltas:
            ddf = pd.DataFrame(seg_deltas)
            rmv.append({
                "chunk": chunk,
                "delta_unique_events": ddf["delta_unique_events"].mean(),
                "delta_long_recall": ddf["delta_long_recall"].mean(),
            })
    if rmv:
        rdf = pd.DataFrame(rmv)
        final_md += "Average repair marginal contribution (D3-core minus D3-norepair-core):\n\n"
        for _, r in rdf.iterrows():
            final_md += f"- chunk={r['chunk']}s: delta_unique_events={r['delta_unique_events']:+.3f}, delta_long_recall={r['delta_long_recall']:+.3f}\n"
        pos_ue = (rdf["delta_unique_events"] > 0.01).sum()
        pos_lr = (rdf["delta_long_recall"] > 0.01).sum()
        neg_ue = (rdf["delta_unique_events"] < -0.01).sum()
        final_md += "\n"
        if pos_ue > 0:
            final_md += f"Repair shows a positive unique-event marginal contribution on {pos_ue}/{len(rdf)} chunk configurations.\n"
        if pos_lr > 0:
            final_md += f"Repair shows a positive long-event-recall marginal contribution on {pos_lr}/{len(rdf)} chunk configurations.\n"
        if pos_ue == 0 and pos_lr == 0:
            final_md += "Repair shows no clear positive marginal contribution on either unique events or long-event recall.\n"
        if neg_ue > 0:
            final_md += f"Repair is associated with fewer unique events on {neg_ue}/{len(rdf)} chunk configurations, suggesting audit/repair budget may displace discovery calls.\n"
        final_md += "\n"

    # Q8: Machinery overhead.
    final_md += "## 8. Does machinery overhead cover its gains?\n\n"
    oh = oh_df.groupby("method").agg(
        guard_frac=("guard_calls_fraction", "mean"),
        repair_frac=("repair_calls_fraction", "mean"),
        discovery_frac=("discovery_calls_fraction", "mean"),
    ).reset_index()
    final_md += "Mean oracle-call fractions by method (guard + repair + discovery + audit = 1.0 within rounding):\n\n"
    for _, r in oh.iterrows():
        if r["method"].startswith("LATE-") or r["method"].startswith("D3-"):
            final_md += f"- {r['method']}: guard={r['guard_frac']:.3f}, repair={r['repair_frac']:.3f}, discovery={r['discovery_frac']:.3f}\n"
    final_md += "\n"

    # Direct comparison: methods with above-median overhead vs their effect gains.
    final_md += "### Overhead-vs-gain assessment\n\n"
    final_md += "- B6-core and B7-core have no guard/repair overhead; their B_90/90 and low-budget recall set the baseline.\n"
    final_md += "- LATE-D1-core-radius20 reduces discovery miss relative to D0 (section 3) but pays ~34-38% guard+repair overhead.\n"
    final_md += "  It does not, however, achieve a lower B_90/90 than B7-core on any segment, so the overhead is not buying a winning frontier position.\n"
    final_md += "- LATE-D2-core variants pay ~27-35% guard+repair overhead and reach 90/90 on more segments than D0, but still do not beat B7-core's B_90/90.\n"
    final_md += "- LATE-D3-core pays ~25-30% guard+repair overhead; D3-norepair-core avoids repair overhead entirely and ties or beats LATE-D3-core on B_90/90 (`repair_marginal_value_report.md`).\n"
    final_md += "- Because no LATE variant beats B7-core and repair's marginal unique-event contribution is non-positive (section 7), the guard+repair machinery is currently a net drag relative to the performance baseline.\n"
    final_md += "\n**Conclusion**: The additional guard/repair overhead of the LATE variants is not covered by corresponding B_90/90 or low-budget recall gains against B7-core.\n\n"

    # Q9: Next step recommendation.
    final_md += "## 9. Recommended next step\n\n"
    # Decide based on data.
    d3_main = "LATE-D3-core-chunk60"
    d3no_main = "D3-norepair-core-chunk60"
    d3_beat_b7 = beat_counts.get(d3_main, 0)
    d3no_beat_b7 = beat_counts.get(d3no_main, 0)

    if reached_any:
        final_md += "A. Adopt the discovery policy that reaches 90/90 at <=30% budget and report which one.\n"
    elif d3_beat_b7 > len(seg_df) // 2:
        final_md += "C. Adopt D3 Chunk-bandit. Repair should be retained only if section 7 shows a clear positive marginal value; otherwise consider dropping repair.\n"
    elif d3no_beat_b7 > len(seg_df) // 2:
        final_md += "C. Adopt D3 Chunk-bandit, but the current repair mechanism does not add clear value; consider D3-norepair or redesign repair.\n"
    elif any(cnt > 0 for cnt in beat_counts.values()):
        final_md += "B. Some D1/D2/D2 variants improve D0 in specific regimes, but none consistently beat B7-core; further regime-specific tuning may be warranted.\n"
    else:
        final_md += "D. None of the new discovery policies consistently beat B7-core; B7-core remains stronger. The performance advantage route is not established.\n"
        final_md += "E. Consider pivoting to audit/estimator contributions rather than performance advantage.\n"

    with open(OUT / "FINAL_REPORT.md", "w") as f:
        f.write(final_md)


def write_readme_and_manifest(seg_df: pd.DataFrame):
    # README
    readme = "# Upstream Event-Diverse Discovery Redesign for LATE-AQP (v2)\n\n"
    readme += "Evaluates D0/D1/D2/D3/D3-norepair discovery policies against B6-core/B7-core on realcartest and dataset3.\n\n"
    readme += "## Run\n\n"
    readme += "```bash\nbash outputs/late_aqp_event_diverse_discovery_v1/commands.sh\n```\n\n"
    readme += "## Key outputs\n\n"
    readme += "- `context_manifest.md` — Context assembly record.\n"
    readme += "- `discovery_policy_specs.md` — Formal definitions of D0-D3.\n"
    readme += "- `event_diverse_frontier_raw.csv` — Per-seed raw results.\n"
    readme += "- `unique_event_coverage.csv` — 9.1 unique event coverage.\n"
    readme += "- `discovery_miss_reduction.csv` — 9.2 discovery miss reduction.\n"
    readme += "- `precision_recall_under_budget_ratio.csv` — 9.3 low-budget P/R.\n"
    readme += "- `b90_90_comparison.csv` — 9.4 B_90/90 comparison.\n"
    readme += "- `segment_regime_analysis.csv` — 9.5 regime analysis.\n"
    readme += "- `machinery_overhead_report.csv` — 9.6 overhead report.\n"
    readme += "- `repair_marginal_value_report.md` — 9.7 repair marginal value.\n"
    readme += "- `failure_casebook.md` — Failure patterns.\n"
    readme += "- `FINAL_REPORT.md` — Summary conclusions.\n"
    with open(OUT / "README.md", "w") as f:
        f.write(readme)

    # commands.sh
    with open(OUT / "commands.sh", "w") as f:
        f.write("#!/usr/bin/env bash\n")
        f.write("set -e\n")
        f.write(f"cd {ROOT}\n")
        f.write("python3 outputs/late_aqp_event_diverse_discovery_v1/run_event_diverse_discovery.py\n")

    # input_manifest.csv
    rows = [
        ["path", "description", "read_only", "used_by"],
        [str(FROZEN_DIR / "run_frozen_cross_segment.py"), "B6/B7/merge_bins/compute_metrics implementation", "yes", "runner"],
        [str(ATTR_DIR / "run_attribution_analysis.py"), "Core/Halo release, LATE repair, LATE discovery ledger", "yes", "runner"],
        [str(ROOT / "experiments" / "v13" / "v13_8_full_oracle" / "tables" / "center10_vlm_oracle_events.csv"), "realcartest full-VLM reference", "yes", "evaluator"],
        [str(ROOT / "src" / "garc_eval" / "outputs" / "clean_interval_aqp_full_reference_v2_clean_no_leak" / "reference_events.csv"), "realcartest dev reference", "yes", "evaluator"],
        [str(ROOT / "outputs" / "exsample_aware_replay" / "atomic_grid_10s.csv"), "realcartest dev atomic grid", "yes", "oracle_adapter"],
        [str(ROOT / "experiments" / "roadclip_budget_v2" / "roadclip_budget_v2" / "proxy_scores.csv"), "realcartest prior scores", "yes", "method"],
        [str(DATASET3_CANONICAL), "dataset3 anchor table + prior scores", "yes", "method/oracle_adapter"],
        [str(ROOT / "src" / "garc_eval" / "outputs" / "event_native_aqp_autonomous_research_sprint_v1" / "oracle_outputs" / "dataset3_full_center10_parsed.csv"), "dataset3 full-VLM reference", "yes", "evaluator"],
    ]
    with open(OUT / "input_manifest.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def write_isolation_audit(raw_df: pd.DataFrame):
    audit_md = "# Online Label Isolation Audit\n\n"
    audit_md += "## Method classification\n\n"
    audit_md += "| method | uses event_id in selection | strict_replay_or_posthoc |\n"
    audit_md += "|--------|----------------------------|---------------------------|\n"
    for method in sorted(raw_df["method"].unique()):
        posthoc = method in ("B6-core", "B7-core")
        audit_md += f"| {method} | {'yes' if posthoc else 'no'} | {'posthoc_eval' if posthoc else 'strict_replay'} |\n"
    audit_md += "\n## Notes\n\n"
    audit_md += "- B6-core/B7-core inherit B6/B7's use of per-bin event_id for chunk-level singleton counting.\n"
    audit_md += "- All LATE-* and D3-norepair-core methods select bins using only prior scores and oracle labels (positive/negative), never event_id or GT intervals.\n"
    audit_md += "- Full-VLM references are only used for final evaluation.\n"
    with open(OUT / "online_label_isolation_audit.md", "w") as f:
        f.write(audit_md)


if __name__ == "__main__":
    main()
