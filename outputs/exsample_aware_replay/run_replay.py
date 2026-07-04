"""
ExSample-aware Replay for LATE-AQP (v2).

Implements and compares:
  B6  ExSample-style adaptive chunk sampling
  B7  ExSample + simple temporal expansion
  Ours-full  LATE-AQP with dual ledger + repair

Uses only existing labels/priors from atomic_grid_10s.csv.
No new VLM/YOLO/GPU inference.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

OUTPUT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC/outputs/exsample_aware_replay")
GRID_PATH = OUTPUT_ROOT / "atomic_grid_10s.csv"
REF_EVENTS_PATH = Path("/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv")
CONFIG_PATH = OUTPUT_ROOT / "preregistered_config.json"

BIN_SIZE = 10  # seconds


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_grid() -> pd.DataFrame:
    grid = pd.read_csv(GRID_PATH)
    grid["bin_idx"] = (grid["t_start"] / BIN_SIZE).astype(int)
    return grid


def load_reference_events() -> pd.DataFrame:
    return pd.read_csv(REF_EVENTS_PATH)


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_event_at_bin(grid: pd.DataFrame, bin_idx: int) -> Optional[str]:
    row = grid[grid["bin_idx"] == bin_idx]
    if row.empty:
        return None
    eid = row.iloc[0]["event_id"]
    if pd.isna(eid):
        return None
    return str(eid)


def get_label_at_bin(grid: pd.DataFrame, bin_idx: int) -> str:
    row = grid[grid["bin_idx"] == bin_idx]
    if row.empty:
        return "negative"
    return str(row.iloc[0]["label"])


def get_prior_at_bin(grid: pd.DataFrame, bin_idx: int) -> float:
    row = grid[grid["bin_idx"] == bin_idx]
    if row.empty:
        return 0.0
    return float(row.iloc[0]["prior_score_max"])


def same_event(e1: Optional[str], e2: Optional[str]) -> bool:
    if e1 is None or e2 is None:
        return False
    return e1 == e2


def event_dedup_distance(grid: pd.DataFrame, bin_idx1: int, bin_idx2: int, d_seconds: float) -> bool:
    """Return True if two bins should be considered the same event candidate."""
    t1 = grid.loc[grid["bin_idx"] == bin_idx1, "t_start"].iloc[0]
    t2 = grid.loc[grid["bin_idx"] == bin_idx2, "t_start"].iloc[0]
    return abs(t1 - t2) < d_seconds


def merge_selected_bins(grid: pd.DataFrame, selected: List[int], d_seconds: float) -> pd.DataFrame:
    """Merge selected bins into contiguous intervals using event_id or time proximity."""
    if not selected:
        return pd.DataFrame(columns=["t_start", "t_end", "label", "event_id", "bin_indices"])

    selected = sorted(set(selected))
    intervals = []
    cur_bins = [selected[0]]
    cur_event = get_event_at_bin(grid, selected[0])
    cur_start = grid.loc[grid["bin_idx"] == selected[0], "t_start"].iloc[0]
    cur_end = grid.loc[grid["bin_idx"] == selected[0], "t_end"].iloc[0]

    for b in selected[1:]:
        b_event = get_event_at_bin(grid, b)
        b_start = grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0]
        # merge if same event_id or within proximity threshold and previous bin is adjacent
        adjacent = b_start - cur_end < BIN_SIZE + 1e-6
        same = (same_event(cur_event, b_event) and cur_event is not None) or (
            adjacent and event_dedup_distance(grid, cur_bins[-1], b, d_seconds)
        )
        if same:
            cur_bins.append(b)
            cur_end = grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0]
            if b_event is not None and cur_event is None:
                cur_event = b_event
        else:
            intervals.append({
                "t_start": cur_start,
                "t_end": cur_end,
                "label": "positive" if cur_event is not None else get_label_at_bin(grid, cur_bins[0]),
                "event_id": cur_event,
                "bin_indices": cur_bins.copy(),
            })
            cur_bins = [b]
            cur_event = b_event
            cur_start = b_start
            cur_end = grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0]

    intervals.append({
        "t_start": cur_start,
        "t_end": cur_end,
        "label": "positive" if cur_event is not None else get_label_at_bin(grid, cur_bins[0]),
        "event_id": cur_event,
        "bin_indices": cur_bins.copy(),
    })
    return pd.DataFrame(intervals)


def compute_event_metrics(grid: pd.DataFrame, selected_bins: List[int], ref_events: pd.DataFrame, d_seconds: float) -> dict:
    """Compute metrics from a set of selected bin indices."""
    if not selected_bins:
        return {
            "discovered_positive_temporal_mass": 0.0,
            "event_level_recall": 0.0,
            "complete_event_coverage": 0.0,
            "selected_precision": 0.0,
            "boundary_iou_0_3": 0.0,
            "boundary_iou_0_5": 0.0,
            "fragmentation_rate": 0.0,
            "selected_total_duration": 0.0,
            "duplicate_rate": 0.0,
        }

    # selected positive bins only, for mass / precision / duplicate
    sel_pos_bins = [b for b in selected_bins if get_label_at_bin(grid, b) == "positive"]
    sel_labels = [get_label_at_bin(grid, b) for b in selected_bins]
    selected_precision = sel_labels.count("positive") / len(sel_labels)

    # Merge selected positive bins into intervals for mass/duration/fragmentation
    positive_merged = merge_selected_bins(grid, sel_pos_bins, d_seconds)
    pos_mass = float((positive_merged["t_end"] - positive_merged["t_start"]).sum())

    # Total selected duration (including false positives)
    all_merged = merge_selected_bins(grid, selected_bins, d_seconds)
    total_dur = float((all_merged["t_end"] - all_merged["t_start"]).sum())

    # duplicate rate: selected positive bins / unique positive events discovered
    unique_pos_events = set()
    for b in sel_pos_bins:
        e = get_event_at_bin(grid, b)
        if e is not None:
            unique_pos_events.add(e)
    n_pos_bins = len(sel_pos_bins)
    duplicate_rate = (n_pos_bins - len(unique_pos_events)) / max(1, len(unique_pos_events))

    # Per-event metrics
    matched_any = set()
    matched_iou_0_3 = set()
    matched_iou_0_5 = set()
    complete_cover = 0
    ious = []
    for _, ev in ref_events.iterrows():
        ev_start, ev_end = ev["t_start"], ev["t_end"]
        # Find selected positive bins overlapping this event
        overlap_bins = []
        for b in sel_pos_bins:
            b_start = grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0]
            b_end = grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0]
            if b_start < ev_end and b_end > ev_start:
                overlap_bins.append(b)

        if overlap_bins:
            matched_any.add(ev["event_id"])
            # Merge overlapping bins and compute IoU with event
            merged_overlap = merge_selected_bins(grid, overlap_bins, d_seconds)
            best_iou = 0.0
            fully_covered = False
            for _, sel in merged_overlap.iterrows():
                inter_start = max(ev_start, sel["t_start"])
                inter_end = min(ev_end, sel["t_end"])
                inter = max(0.0, inter_end - inter_start)
                union = max(ev_end, sel["t_end"]) - min(ev_start, sel["t_start"])
                iou = inter / union if union > 0 else 0.0
                if iou > best_iou:
                    best_iou = iou
                # complete coverage: selected interval fully contains the event
                if sel["t_start"] <= ev_start + 1e-6 and sel["t_end"] >= ev_end - 1e-6:
                    fully_covered = True
            ious.append(best_iou)
            if best_iou >= 0.3:
                matched_iou_0_3.add(ev["event_id"])
            if best_iou >= 0.5:
                matched_iou_0_5.add(ev["event_id"])
            if fully_covered:
                complete_cover += 1
        else:
            ious.append(0.0)

    event_recall = len(matched_any) / len(ref_events)
    complete_event_coverage = complete_cover / len(ref_events)
    boundary_iou_0_3 = len(matched_iou_0_3) / len(ref_events)
    boundary_iou_0_5 = len(matched_iou_0_5) / len(ref_events)

    # fragmentation rate: number of selected intervals per matched event
    n_matched = len(matched_any)
    fragmentation_rate = len(positive_merged) / max(1, n_matched)

    return {
        "discovered_positive_temporal_mass": pos_mass,
        "event_level_recall": event_recall,
        "complete_event_coverage": complete_event_coverage,
        "selected_precision": selected_precision,
        "boundary_iou_0_3": boundary_iou_0_3,
        "boundary_iou_0_5": boundary_iou_0_5,
        "fragmentation_rate": fragmentation_rate,
        "selected_total_duration": total_dur,
        "duplicate_rate": duplicate_rate,
    }


# ---------------------------------------------------------------------------
# B6: ExSample-style adaptive chunk sampling
# ---------------------------------------------------------------------------
def run_b6(grid: pd.DataFrame, ref_events: pd.DataFrame, budget: int, chunk_size_s: int,
           d_seconds: float, rng: np.random.Generator) -> Tuple[List[int], Dict]:
    """Return selected bins and budget accounting."""
    n_bins = len(grid)
    bins_per_chunk = max(1, chunk_size_s // BIN_SIZE)
    n_chunks = int(np.ceil(n_bins / bins_per_chunk))

    sampled = set()
    n_c = np.zeros(n_chunks, dtype=int)
    # Track discovered events per chunk (event_id -> count of bins in this chunk)
    discovered_events: List[Dict[str, int]] = [dict() for _ in range(n_chunks)]

    while len(sampled) < budget:
        # Compute N1_c: number of events seen exactly once in chunk c
        N1_c = np.zeros(n_chunks, dtype=float)
        for c in range(n_chunks):
            N1_c[c] = sum(1 for cnt in discovered_events[c].values() if cnt == 1)

        # Thompson sample
        theta = rng.gamma(shape=N1_c + 0.1, scale=1.0 / (n_c + 1.0))
        # Mask chunks with no unsampled bins
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
        b = rng.choice(unsampled)
        sampled.add(b)
        n_c[chosen_c] += 1
        e = get_event_at_bin(grid, b)
        if e is not None:
            discovered_events[chosen_c][e] = discovered_events[chosen_c].get(e, 0) + 1

    budget_used = len(sampled)
    metrics = compute_event_metrics(grid, list(sampled), ref_events, d_seconds)
    return list(sampled), {
        "budget_used": budget_used,
        "budget_target": budget,
        "n_chunks": n_chunks,
        "sampled_bins": sorted(sampled),
        **metrics,
    }


# ---------------------------------------------------------------------------
# B7: ExSample + simple temporal expansion
# ---------------------------------------------------------------------------
def run_b7(grid: pd.DataFrame, ref_events: pd.DataFrame, budget: int, chunk_size_s: int,
           k: int, d_seconds: float, rng: np.random.Generator) -> Tuple[List[int], Dict]:
    n_bins = len(grid)
    bins_per_chunk = max(1, chunk_size_s // BIN_SIZE)
    n_chunks = int(np.ceil(n_bins / bins_per_chunk))

    sampled = set()
    n_c = np.zeros(n_chunks, dtype=int)
    discovered_events: List[Dict[str, int]] = [dict() for _ in range(n_chunks)]

    def sample_bin(b: int, c: int):
        if b in sampled or b < 0 or b >= n_bins:
            return False
        sampled.add(b)
        n_c[c] += 1
        e = get_event_at_bin(grid, b)
        if e is not None:
            discovered_events[c][e] = discovered_events[c].get(e, 0) + 1
        return True

    def expand(b: int, c: int) -> bool:
        """Try one expansion step. Returns True if a bin was sampled."""
        # Find nearest unsampled neighbor within k bins
        for offset in range(1, k + 1):
            for sign in [-1, 1]:
                nb = b + sign * offset
                if nb < 0 or nb >= n_bins or nb in sampled:
                    continue
                # Expansion stays within same chunk? The task says "向左右各扩展 ±k bins".
                # We allow cross-chunk expansion since bins are contiguous.
                sample_bin(nb, min(nb // bins_per_chunk, n_chunks - 1))
                return True
        return False

    while len(sampled) < budget:
        # Adaptive chunk selection
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
        b = rng.choice(unsampled)
        sample_bin(b, chosen_c)

        # If positive, expand
        if get_label_at_bin(grid, b) == "positive" and len(sampled) < budget:
            # Expand left and right until negative boundary or budget
            for _ in range(k * 2 + 5):  # safety bound
                if len(sampled) >= budget:
                    break
                # check if immediate neighbors are negative -> stop
                left_neg = all(get_label_at_bin(grid, b - o) == "negative" for o in range(1, k + 1) if b - o >= 0 and b - o not in sampled)
                right_neg = all(get_label_at_bin(grid, b + o) == "negative" for o in range(1, k + 1) if b + o < n_bins and b + o not in sampled)
                if left_neg and right_neg:
                    break
                if not expand(b, chosen_c):
                    break

    budget_used = len(sampled)
    metrics = compute_event_metrics(grid, list(sampled), ref_events, d_seconds)
    return list(sampled), {
        "budget_used": budget_used,
        "budget_target": budget,
        "n_chunks": n_chunks,
        "sampled_bins": sorted(sampled),
        **metrics,
    }


# ---------------------------------------------------------------------------
# Ours-full: LATE-AQP
# ---------------------------------------------------------------------------
def run_ours_full(grid: pd.DataFrame, ref_events: pd.DataFrame, budget: int,
                  e0_pct: float, d_seconds: float, rng: np.random.Generator,
                  audit_fraction: float = 0.25) -> Tuple[List[int], Dict]:
    """
    Dual-ledger LATE-AQP.
    - E0 = top e0_pct prior bins.
    - Discovery ledger: expected-yield sampling inside E0.
    - Audit ledger: independent stratified random sample of E0 inside/outside.
    - Repair: triggered only by audit-outside positives.
    """
    n_bins = len(grid)
    grid_sorted = grid.sort_values("prior_score_max", ascending=False).reset_index(drop=True)
    cutoff_idx = max(1, int(np.round(e0_pct * n_bins)))
    e0_bin_indices = set(grid_sorted.iloc[:cutoff_idx]["bin_idx"].tolist())

    sampled = set()
    sampled_by_audit = set()  # bins sampled by audit ledger
    sampled_by_discovery = set()
    sampled_by_repair = set()

    n_audit = min(int(np.round(audit_fraction * budget)), budget)
    # Reserve audit budget; remainder for discovery + repair
    n_discovery_repair = budget - n_audit

    # ---- Audit ledger: stratified random sample ----
    inside_bins = [b for b in range(n_bins) if b in e0_bin_indices]
    outside_bins = [b for b in range(n_bins) if b not in e0_bin_indices]
    # Split audit budget evenly between inside/outside, or proportional to size
    n_audit_inside = min(len(inside_bins), n_audit // 2)
    n_audit_outside = min(len(outside_bins), n_audit - n_audit_inside)

    if n_audit_inside > 0:
        audit_inside = set(rng.choice(inside_bins, size=n_audit_inside, replace=False))
    else:
        audit_inside = set()
    if n_audit_outside > 0:
        audit_outside = set(rng.choice(outside_bins, size=n_audit_outside, replace=False))
    else:
        audit_outside = set()

    sampled.update(audit_inside)
    sampled.update(audit_outside)
    sampled_by_audit.update(audit_inside)
    sampled_by_audit.update(audit_outside)

    # Estimate p_in, p_out, L_out from audit only
    inside_pos = sum(1 for b in audit_inside if get_label_at_bin(grid, b) == "positive")
    outside_pos = sum(1 for b in audit_outside if get_label_at_bin(grid, b) == "positive")
    p_in_hat = inside_pos / max(1, len(audit_inside))
    p_out_hat = outside_pos / max(1, len(audit_outside))
    L_out_hat = p_out_hat * len(outside_bins) * BIN_SIZE  # seconds

    # ---- Repair triggers: outside positive found by audit ----
    repair_seeds = [b for b in audit_outside if get_label_at_bin(grid, b) == "positive"]

    # ---- Discovery ledger: expected-yield sampling, prioritising E0 ----
    discovery_budget_remaining = n_discovery_repair

    # Rank all unsampled bins by prior score (expected yield). E0 bins are
    # prioritised by sampling them first; if E0 is exhausted we continue with
    # the next-best bins so the total budget is always fully spent.
    ranked_inside = sorted([b for b in inside_bins if b not in sampled],
                           key=lambda b: get_prior_at_bin(grid, b), reverse=True)
    ranked_outside = sorted([b for b in outside_bins if b not in sampled],
                            key=lambda b: get_prior_at_bin(grid, b), reverse=True)

    discovery_e0 = set()
    for b in ranked_inside:
        if discovery_budget_remaining <= 0:
            break
        sampled.add(b)
        sampled_by_discovery.add(b)
        discovery_e0.add(b)
        discovery_budget_remaining -= 1

    # ---- Repair: expand around outside positives (only triggered by audit) ----
    for seed in repair_seeds:
        if discovery_budget_remaining <= 0:
            break
        left_done = False
        right_done = False
        offset = 1
        while offset < n_bins and discovery_budget_remaining > 0:
            if not left_done:
                nb = seed - offset
                if nb < 0:
                    left_done = True
                elif nb not in sampled:
                    sampled.add(nb)
                    sampled_by_repair.add(nb)
                    discovery_budget_remaining -= 1
                    if get_label_at_bin(grid, nb) == "negative":
                        left_done = True
            if not right_done and discovery_budget_remaining > 0:
                nb = seed + offset
                if nb >= n_bins:
                    right_done = True
                elif nb not in sampled:
                    sampled.add(nb)
                    sampled_by_repair.add(nb)
                    discovery_budget_remaining -= 1
                    if get_label_at_bin(grid, nb) == "negative":
                        right_done = True
            if left_done and right_done:
                break
            offset += 1

    # If budget still remains (no repair or E0+repair exhausted), continue
    # discovery in descending prior order across the whole video.
    for b in ranked_outside:
        if discovery_budget_remaining <= 0:
            break
        if b in sampled:
            continue
        sampled.add(b)
        sampled_by_discovery.add(b)
        discovery_budget_remaining -= 1

    budget_used = len(sampled)
    metrics = compute_event_metrics(grid, list(sampled), ref_events, d_seconds)
    return list(sampled), {
        "budget_used": budget_used,
        "budget_target": budget,
        "e0_pct": e0_pct,
        "n_audit": n_audit,
        "n_discovery": len(sampled_by_discovery),
        "n_repair": len(sampled_by_repair),
        "p_in_hat": p_in_hat,
        "p_out_hat": p_out_hat,
        "L_out_hat_s": L_out_hat,
        "sampled_bins": sorted(sampled),
        **metrics,
    }


# ---------------------------------------------------------------------------
# Main experiment runner
# ---------------------------------------------------------------------------
def run_all():
    config = load_config()
    grid = load_grid()
    ref_events = load_reference_events()

    d_seconds = config["dedup_time_distance_threshold_d_s"]
    chunk_sizes = config["chunk_size_candidates_s"]
    ks = config["expansion_k_candidates_bins"]
    e0_pcts = {"top10": 0.10, "top20": 0.20, "top30": 0.30}
    budgets = [5, 10, 20, 40, 80, 120]
    n_trials = config["n_trials_per_setting"]
    base_seed = config["random_seed"]

    per_budget_rows = []
    selected_interval_rows = []
    budget_audit_rows = []

    for budget in budgets:
        # B6
        for chunk_size in chunk_sizes:
            for trial in range(n_trials):
                rng = np.random.default_rng(base_seed + trial)
                sampled, info = run_b6(grid, ref_events, budget, chunk_size, d_seconds, rng)
                per_budget_rows.append({
                    "method": "B6_ExSample",
                    "chunk_size_s": chunk_size,
                    "k": np.nan,
                    "e0_pct": np.nan,
                    "budget": budget,
                    "trial": trial,
                    **{k: info[k] for k in info if k not in ("sampled_bins",)},
                })
                budget_audit_rows.append({
                    "method": "B6_ExSample",
                    "chunk_size_s": chunk_size,
                    "k": np.nan,
                    "e0_pct": np.nan,
                    "budget": budget,
                    "trial": trial,
                    "budget_target": budget,
                    "budget_used": info["budget_used"],
                    "discrepancy_pct": (info["budget_used"] - budget) / budget * 100,
                })
                for rank, b in enumerate(sampled):
                    selected_interval_rows.append({
                        "method": "B6_ExSample",
                        "chunk_size_s": chunk_size,
                        "k": np.nan,
                        "e0_pct": np.nan,
                        "budget": budget,
                        "trial": trial,
                        "rank": rank,
                        "bin_idx": b,
                        "t_start": grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0],
                        "t_end": grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0],
                        "label": get_label_at_bin(grid, b),
                        "event_id": get_event_at_bin(grid, b),
                    })

        # B7
        for chunk_size in chunk_sizes:
            for k in ks:
                for trial in range(n_trials):
                    rng = np.random.default_rng(base_seed + 1000 + trial)
                    sampled, info = run_b7(grid, ref_events, budget, chunk_size, k, d_seconds, rng)
                    per_budget_rows.append({
                        "method": "B7_ExSample_plus_expansion",
                        "chunk_size_s": chunk_size,
                        "k": k,
                        "e0_pct": np.nan,
                        "budget": budget,
                        "trial": trial,
                        **{k: info[k] for k in info if k not in ("sampled_bins",)},
                    })
                    budget_audit_rows.append({
                        "method": "B7_ExSample_plus_expansion",
                        "chunk_size_s": chunk_size,
                        "k": k,
                        "e0_pct": np.nan,
                        "budget": budget,
                        "trial": trial,
                        "budget_target": budget,
                        "budget_used": info["budget_used"],
                        "discrepancy_pct": (info["budget_used"] - budget) / budget * 100,
                    })
                    for rank, b in enumerate(sampled):
                        selected_interval_rows.append({
                            "method": "B7_ExSample_plus_expansion",
                            "chunk_size_s": chunk_size,
                            "k": k,
                            "e0_pct": np.nan,
                            "budget": budget,
                            "trial": trial,
                            "rank": rank,
                            "bin_idx": b,
                            "t_start": grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0],
                            "t_end": grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0],
                            "label": get_label_at_bin(grid, b),
                            "event_id": get_event_at_bin(grid, b),
                        })

        # Ours-full
        for e0_name, e0_pct in e0_pcts.items():
            for trial in range(n_trials):
                rng = np.random.default_rng(base_seed + 2000 + trial)
                sampled, info = run_ours_full(grid, ref_events, budget, e0_pct, d_seconds, rng)
                per_budget_rows.append({
                    "method": "Ours_full_LATE_AQP",
                    "chunk_size_s": np.nan,
                    "k": np.nan,
                    "e0_pct": e0_name,
                    "e0_fraction": e0_pct,
                    "budget": budget,
                    "trial": trial,
                    **{k: info[k] for k in info if k not in ("sampled_bins", "e0_pct")},
                })
                budget_audit_rows.append({
                    "method": "Ours_full_LATE_AQP",
                    "chunk_size_s": np.nan,
                    "k": np.nan,
                    "e0_pct": e0_name,
                    "e0_fraction": e0_pct,
                    "budget": budget,
                    "trial": trial,
                    "budget_target": budget,
                    "budget_used": info["budget_used"],
                    "discrepancy_pct": (info["budget_used"] - budget) / budget * 100,
                    "n_audit": info["n_audit"],
                    "n_discovery": info["n_discovery"],
                    "n_repair": info["n_repair"],
                    "p_in_hat": info["p_in_hat"],
                    "p_out_hat": info["p_out_hat"],
                    "L_out_hat_s": info["L_out_hat_s"],
                })
                for rank, b in enumerate(sampled):
                    selected_interval_rows.append({
                        "method": "Ours_full_LATE_AQP",
                        "chunk_size_s": np.nan,
                        "k": np.nan,
                        "e0_pct": e0_name,
                        "e0_fraction": e0_pct,
                        "budget": budget,
                        "trial": trial,
                        "rank": rank,
                        "bin_idx": b,
                        "t_start": grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0],
                        "t_end": grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0],
                        "label": get_label_at_bin(grid, b),
                        "event_id": get_event_at_bin(grid, b),
                    })

    # Save raw outputs
    per_budget_df = pd.DataFrame(per_budget_rows)
    selected_df = pd.DataFrame(selected_interval_rows)
    budget_audit_df = pd.DataFrame(budget_audit_rows)

    per_budget_df.to_csv(OUTPUT_ROOT / "per_budget_metrics.csv", index=False)
    selected_df.to_csv(OUTPUT_ROOT / "per_method_selected_intervals.csv", index=False)
    budget_audit_df.to_csv(OUTPUT_ROOT / "budget_accounting_audit.csv", index=False)

    print(f"Wrote per_budget_metrics.csv ({len(per_budget_df)} rows)")
    print(f"Wrote per_method_selected_intervals.csv ({len(selected_df)} rows)")
    print(f"Wrote budget_accounting_audit.csv ({len(budget_audit_df)} rows)")

    # Aggregate summary
    summary_rows = []
    for (method, chunk_size, k, e0_pct), g in per_budget_df.groupby(["method", "chunk_size_s", "k", "e0_pct"], dropna=False):
        for budget, gg in g.groupby("budget"):
            row = {
                "method": method,
                "chunk_size_s": chunk_size,
                "k": k,
                "e0_pct": e0_pct,
                "budget": budget,
                "n_trials": len(gg),
            }
            for col in ["discovered_positive_temporal_mass", "event_level_recall", "complete_event_coverage",
                        "selected_precision", "boundary_iou_0_3", "boundary_iou_0_5", "fragmentation_rate",
                        "selected_total_duration", "duplicate_rate"]:
                row[f"{col}_mean"] = gg[col].mean()
                row[f"{col}_std"] = gg[col].std()
            summary_rows.append(row)
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(OUTPUT_ROOT / "baseline_results.csv", index=False)
    print(f"Wrote baseline_results.csv ({len(summary_df)} rows)")


if __name__ == "__main__":
    run_all()
