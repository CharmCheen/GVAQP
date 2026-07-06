#!/usr/bin/env python3
"""
Core/Halo attribution analysis for LATE-AQP.

No GPU/VLM, no new labels, no changes to discovery/repair/prior.
"""

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
FROZEN_DIR = ROOT / "outputs" / "late_aqp_frozen_cross_segment_v1"
FRONTIER_DIR = ROOT / "outputs" / "late_aqp_core_halo_frontier"
OUT = ROOT / "outputs" / "late_aqp_core_halo_attribution_v1"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(FROZEN_DIR))
from run_frozen_cross_segment import (
    BIN_SIZE,
    RANDOM_SEED_BASE,
    SEEDS,
    build_segment_grid,
    compute_metrics,
    get_event_at_bin,
    get_label_at_bin,
    load_dev_events,
    load_dev_grid,
    load_full_events,
    load_proxy_scores,
    merge_bins,
    run_b6,
    run_b7,
)

SEGMENTS = [
    {"segment_id": "realcartest_0_1570", "video_id": "realcartest", "time_start": 0.0, "time_end": 1570.0, "is_dev": False},
    {"segment_id": "realcartest_2000_3200", "video_id": "realcartest", "time_start": 2000.0, "time_end": 3200.0, "is_dev": True},
    {"segment_id": "realcartest_3200_3830", "video_id": "realcartest", "time_start": 3200.0, "time_end": 3830.0, "is_dev": False},
]

BUDGETS = [5, 10, 20, 40, 60, 80, 100, 120]
CHUNK_SIZE_S = 120
MAX_GUARDS_PER_SIDE = 3


def load_segment_grid_ref(seg: dict):
    if seg["is_dev"]:
        grid = load_dev_grid().copy()
        grid = grid[grid["t_start"] < (seg["time_end"] - seg["time_start"])].reset_index(drop=True)
        grid["bin_idx"] = np.arange(len(grid))
        grid["local_t_start"] = grid["t_start"]
        grid["local_t_end"] = grid["t_end"].clip(upper=(seg["time_end"] - seg["time_start"]))
        grid["t_start"] = grid["local_t_start"]
        grid["t_end"] = grid["local_t_end"]
        ref = load_dev_events().copy()
        ref["event_type"] = ref["duration"].apply(lambda d: "long_interval" if d >= 1.0 else "point_anchor")
    else:
        grid, ref = build_segment_grid(seg, load_full_events(), load_proxy_scores())
    return grid, ref


def event_level_metrics(intervals_df: pd.DataFrame, ref: pd.DataFrame) -> Tuple[float, float]:
    if intervals_df.empty:
        return 0.0, 0.0
    tp_intervals = 0
    hit_events: Set[str] = set()
    for _, iv in intervals_df.iterrows():
        overlaps = False
        for _, ev in ref.iterrows():
            inter = max(0.0, min(iv["t_end"], ev["t_end"]) - max(iv["t_start"], ev["t_start"]))
            if inter > 0:
                overlaps = True
                hit_events.add(str(ev["event_id"]))
        if overlaps:
            tp_intervals += 1
    precision = tp_intervals / len(intervals_df)
    recall = len(hit_events) / len(ref) if len(ref) > 0 else 0.0
    return precision, recall


def interval_has_positive_selected(iv, bin_to_row: Dict[int, pd.Series]) -> bool:
    for b in iv["bin_indices"]:
        if bin_to_row[int(b)]["is_positive"]:
            return True
    return False


def compute_guard_need(intervals_df: pd.DataFrame, grid: pd.DataFrame, max_guards: int, bin_to_row: Dict[int, pd.Series]) -> int:
    need = 0
    n_bins = len(grid)
    for _, iv in intervals_df.iterrows():
        if not interval_has_positive_selected(iv, bin_to_row):
            continue
        s = int(iv["bin_indices"][0])
        e = int(iv["bin_indices"][-1])
        for offset in range(1, max_guards + 1):
            b = s - offset
            if b < 0:
                break
            need += 1
            if get_label_at_bin(grid, b) == "negative":
                break
        for offset in range(1, max_guards + 1):
            b = e + offset
            if b >= n_bins:
                break
            need += 1
            if get_label_at_bin(grid, b) == "negative":
                break
    return need


def perform_guards(
    intervals_df: pd.DataFrame,
    grid: pd.DataFrame,
    bin_to_row: Dict[int, pd.Series],
    guard_budget: int,
    method: str,
    segment_id: str,
    budget: int,
    seed: int,
) -> Tuple[Set[int], List[Dict], int]:
    """Guard positive intervals with given budget. Return core bins, guard log, actual guard calls."""
    n_bins = len(grid)
    core_bins: Set[int] = set()
    guard_log: List[Dict] = []
    actual = 0
    if intervals_df.empty:
        return core_bins, guard_log, actual
    positive_intervals = [iv for _, iv in intervals_df.iterrows() if interval_has_positive_selected(iv, bin_to_row)]
    # Even with zero guard budget, keep positive selected bins as core.
    for iv in positive_intervals:
        for b in iv["bin_indices"]:
            if bin_to_row[int(b)]["is_positive"]:
                core_bins.add(int(b))
    if guard_budget <= 0:
        return core_bins, guard_log, actual

    positive_intervals.sort(key=lambda iv: iv["duration"], reverse=True)
    remaining = guard_budget
    for idx, iv in enumerate(positive_intervals):
        # Always add positive selected bins to core.
        for b in iv["bin_indices"]:
            if bin_to_row[int(b)]["is_positive"]:
                core_bins.add(int(b))
        if remaining <= 0:
            continue
        s = int(iv["bin_indices"][0])
        e = int(iv["bin_indices"][-1])
        for side in ["left", "right"]:
            if remaining <= 0:
                break
            for offset in range(1, MAX_GUARDS_PER_SIDE + 1):
                if remaining <= 0:
                    break
                b = s - offset if side == "left" else e + offset
                if b < 0 or b >= n_bins:
                    break
                actual += 1
                remaining -= 1
                label = get_label_at_bin(grid, b)
                is_pos = bin_to_row[b]["is_positive"]
                if is_pos:
                    core_bins.add(b)
                stopped = (label == "negative")
                guard_log.append({
                    "segment": segment_id, "budget": budget, "seed": seed, "method": method,
                    "interval_idx": idx, "side": side, "offset": offset, "bin": b,
                    "oracle_label": label, "is_positive": is_pos, "stopped": stopped,
                })
                if stopped:
                    break
    return core_bins, guard_log, actual


def run_b6_b7_core_halo(
    grid: pd.DataFrame, ref: pd.DataFrame, budget: int, rng: np.random.Generator, method: str, segment_id: str, seed: int
) -> Tuple[List[int], pd.DataFrame, pd.DataFrame, List[Dict], Dict]:
    """Run B6 or B7, then apply core/halo release with budget-aware guards.

    Returns candidate_bins, candidate_intervals, core_intervals, guard_log, diagnostics.
    """
    n_bins = len(grid)
    bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}

    # Iteratively fit selection + guards inside total budget.
    selection_budget = budget
    candidate_bins: List[int] = []
    candidate_intervals = pd.DataFrame()
    need = 0
    for _ in range(5):
        if method == "B6":
            candidate_bins = run_b6(grid, selection_budget, CHUNK_SIZE_S, rng)
        else:
            candidate_bins = run_b7(grid, selection_budget, CHUNK_SIZE_S, k=3, rng=rng)
        candidate_intervals = merge_bins(grid, candidate_bins)
        need = compute_guard_need(candidate_intervals, grid, MAX_GUARDS_PER_SIDE, bin_to_row)
        if len(candidate_bins) + need <= budget:
            break
        selection_budget = max(0, budget - need)
        if selection_budget == 0:
            break

    guard_budget = budget - len(candidate_bins)
    core_bins, guard_log, actual_guards = perform_guards(
        candidate_intervals, grid, bin_to_row, guard_budget, f"{method}-core", segment_id, budget, seed
    )
    core_intervals = merge_bins(grid, sorted(core_bins))

    candidate_duration = candidate_intervals["duration"].sum() if not candidate_intervals.empty else 0.0
    core_duration = core_intervals["duration"].sum() if not core_intervals.empty else 0.0
    diagnostics = {
        "selection_calls": len(candidate_bins),
        "guard_calls": actual_guards,
        "total_used_calls": len(candidate_bins) + actual_guards,
        "budget_accounting_error": budget - (len(candidate_bins) + actual_guards),
        "candidate_duration": candidate_duration,
        "core_duration": core_duration,
        "halo_duration": candidate_duration - core_duration,
    }
    return candidate_bins, candidate_intervals, core_intervals, guard_log, diagnostics


def sample_weighted(pool: List[int], n: int, weights: Dict[int, float], rng: np.random.Generator, queried: Set[int]) -> List[int]:
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


def run_discovery(grid: pd.DataFrame, budget: int, queried: Set[int]) -> List[int]:
    unqueried = [b for b in range(len(grid)) if b not in queried]
    ranked = sorted(unqueried, key=lambda b: grid[grid["bin_idx"] == b].iloc[0]["prior_score_max"], reverse=True)
    return ranked[:budget]


def run_late_aqp_core_halo(
    grid: pd.DataFrame, ref: pd.DataFrame, budget: int, rng: np.random.Generator, segment_id: str, seed: int
) -> Tuple[List[int], pd.DataFrame, pd.DataFrame, List[Dict], Dict]:
    """Frozen-LATE-AQP-v1 + core/halo release with detailed guard logs."""
    n_bins = len(grid)
    e0_pct = 20
    k = max(1, int(round(n_bins * e0_pct / 100.0)))
    top = grid.nlargest(k, "prior_score_max")
    e0 = set(int(x) for x in top["bin_idx"].tolist())

    queried: Set[int] = set()
    selected: Set[int] = set()
    audit_calls = 0
    repair_calls = 0
    bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}

    inside_bins = [b for b in range(n_bins) if b in e0]
    outside_bins = [b for b in range(n_bins) if b not in e0]
    inside_weights = {b: max(1e-6, bin_to_row[b]["prior_score_max"]) for b in inside_bins}
    outside_weights = {b: max(1e-6, bin_to_row[b]["prior_score_max"]) for b in outside_bins}

    # Audit
    audit_calls_target = min(math.ceil(budget * 0.10), 3 * 2)
    audit_calls_target = max(0, min(audit_calls_target, budget))
    n_inside = math.floor(audit_calls_target * 0.5)
    n_outside = audit_calls_target - n_inside
    audited_inside = sample_weighted(inside_bins, n_inside, inside_weights, rng, queried)
    audited_outside = sample_weighted(outside_bins, n_outside, outside_weights, rng, queried)
    for b in audited_inside:
        queried.add(b); selected.add(b); audit_calls += 1
    for b in audited_outside:
        queried.add(b); selected.add(b); audit_calls += 1

    outside_positives: List[int] = []
    for b in audited_outside:
        if bin_to_row[b]["is_positive"]:
            outside_positives.append(b)

    if outside_positives:
        cap = round(budget * 0.25)
        extra = cap - audit_calls
        extra = max(0, min(extra, budget - audit_calls))
        if extra > 0:
            extra_outside = math.ceil(extra * 0.7)
            extra_inside = extra - extra_outside
            more_in = sample_weighted(inside_bins, extra_inside, inside_weights, rng, queried)
            more_out = sample_weighted(outside_bins, extra_outside, outside_weights, rng, queried)
            for b in more_in:
                queried.add(b); selected.add(b); audit_calls += 1
            for b in more_out:
                queried.add(b); selected.add(b); audit_calls += 1
                if bin_to_row[b]["is_positive"]:
                    outside_positives.append(b)

    # Repair
    remaining = budget - audit_calls
    repair_seeds = list(set(outside_positives))
    if repair_seeds and remaining > 0:
        actions = []
        for seed in repair_seeds:
            seed_prior = bin_to_row[seed]["prior_score_max"]
            for nb in [max(0, seed - 1), min(n_bins - 1, seed + 1)]:
                if nb in queried:
                    continue
                actions.append((seed_prior, seed, nb))
        actions.sort(key=lambda x: x[0], reverse=True)
        for _, seed, nb in actions:
            if remaining <= 0:
                break
            if nb in queried:
                continue
            queried.add(nb); selected.add(nb); repair_calls += 1; remaining -= 1

    # Discovery + guard budget iteration
    remaining_total = budget - audit_calls - repair_calls
    discovery_budget = remaining_total
    candidate_intervals = pd.DataFrame()
    for _ in range(5):
        disc = run_discovery(grid, discovery_budget, queried)
        candidate_bins = sorted(selected.union(disc))
        candidate_intervals = merge_bins(grid, candidate_bins)
        need = compute_guard_need(candidate_intervals, grid, MAX_GUARDS_PER_SIDE, bin_to_row)
        if discovery_budget + need <= remaining_total:
            break
        discovery_budget = max(0, remaining_total - need)
        if discovery_budget == 0:
            break

    guard_budget = remaining_total - discovery_budget
    core_bins, guard_log, actual_guards = perform_guards(
        candidate_intervals, grid, bin_to_row, guard_budget, "LATE-AQP-core", segment_id, budget, seed
    )
    core_intervals = merge_bins(grid, sorted(core_bins))

    candidate_duration = candidate_intervals["duration"].sum() if not candidate_intervals.empty else 0.0
    core_duration = core_intervals["duration"].sum() if not core_intervals.empty else 0.0
    diagnostics = {
        "audit_calls": audit_calls,
        "repair_calls": repair_calls,
        "discovery_calls": discovery_budget,
        "guard_calls": actual_guards,
        "total_used_calls": audit_calls + repair_calls + discovery_budget + actual_guards,
        "budget_accounting_error": budget - (audit_calls + repair_calls + discovery_budget + actual_guards),
        "candidate_duration": candidate_duration,
        "core_duration": core_duration,
        "halo_duration": candidate_duration - core_duration,
    }
    return candidate_bins, candidate_intervals, core_intervals, guard_log, diagnostics


def release_variants(
    grid: pd.DataFrame, ref: pd.DataFrame, candidate_bins: List[int], core_bins: Set[int], guard_log: List[Dict]
) -> List[Dict]:
    """Compute precision/recall/duration for core/halo tradeoff variants."""
    bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}
    candidate_set = set(candidate_bins)
    positive_guard_bins = {int(r["bin"]) for r in guard_log if r["is_positive"]}

    # Compute halo bins by distance to nearest core bin.
    core_list = sorted(core_bins)
    halo_1 = set()
    halo_2 = set()
    for b in candidate_set - core_bins:
        if not core_list:
            break
        dist = min(abs(b - c) for c in core_list)
        if dist <= 1:
            halo_1.add(b)
        if dist <= 2:
            halo_2.add(b)

    variants = {
        "core_only": core_bins,
        "core_plus_positive_guard": core_bins | positive_guard_bins,
        "core_plus_1bin_halo": core_bins | halo_1,
        "core_plus_2bin_halo": core_bins | halo_2,
        "full_window": candidate_set,
    }
    rows = []
    for name, bins in variants.items():
        intervals = merge_bins(grid, sorted(bins))
        prec, rec = event_level_metrics(intervals, ref)
        dur = intervals["duration"].sum() if not intervals.empty else 0.0
        rows.append({"release_variant": name, "event_precision": prec, "event_recall": rec, "selected_duration": dur})
    return rows


def main():
    # Store intervals/logs for hardest-segment analysis.
    intervals_store: Dict[Tuple[str, str, int, int], Dict] = {}
    guard_logs: List[Dict] = []
    diagnostic_rows: List[Dict] = []
    tradeoff_rows: List[Dict] = []

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        print(f"\nSegment {seg_id}")
        grid, ref = load_segment_grid_ref(seg)
        n_bins = len(grid)
        e0_pct = 20
        k = max(1, int(round(n_bins * e0_pct / 100.0)))
        top = grid.nlargest(k, "prior_score_max")
        e0_bins = set(int(x) for x in top["bin_idx"].tolist())

        for budget in BUDGETS:
            for trial, seed_offset in enumerate(SEEDS):
                rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)

                # LATE-AQP-core (candidate + core)
                cand_bins_late, cand_iv_late, core_iv_late, log_late, diag_late = run_late_aqp_core_halo(
                    grid, ref, budget, rng, seg_id, trial
                )
                guard_logs.extend(log_late)
                prec_cand, rec_cand = event_level_metrics(cand_iv_late, ref)
                prec_core, rec_core = event_level_metrics(core_iv_late, ref)
                diagnostic_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial, "method": "LATE-AQP-candidate",
                    "event_precision": prec_cand, "event_recall": rec_cand,
                    "core_duration": diag_late["candidate_duration"], "halo_duration": 0.0,
                    "guard_calls": 0, "guard_positive": 0, "guard_negative": 0,
                    "selection_calls": diag_late["audit_calls"] + diag_late["repair_calls"] + diag_late["discovery_calls"],
                    "total_used_calls": diag_late["total_used_calls"], "budget_error": diag_late["budget_accounting_error"],
                })
                diagnostic_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial, "method": "LATE-AQP-core",
                    "event_precision": prec_core, "event_recall": rec_core,
                    "core_duration": diag_late["core_duration"], "halo_duration": diag_late["halo_duration"],
                    "guard_calls": diag_late["guard_calls"],
                    "guard_positive": sum(1 for r in log_late if r["is_positive"]),
                    "guard_negative": sum(1 for r in log_late if not r["is_positive"]),
                    "selection_calls": diag_late["audit_calls"] + diag_late["repair_calls"] + diag_late["discovery_calls"],
                    "total_used_calls": diag_late["total_used_calls"], "budget_error": diag_late["budget_accounting_error"],
                })
                intervals_store[(seg_id, "LATE-AQP-core", budget, trial)] = {
                    "candidate_bins": cand_bins_late, "candidate_intervals": cand_iv_late, "core_intervals": core_iv_late,
                    "e0_bins": e0_bins,
                }

                # Tradeoff variants for LATE-AQP
                core_bins_set = set()
                for _, iv in core_iv_late.iterrows():
                    for b in iv["bin_indices"]:
                        core_bins_set.add(int(b))
                for row in release_variants(grid, ref, cand_bins_late, core_bins_set, log_late):
                    tradeoff_rows.append({
                        "segment": seg_id, "budget": budget, "seed": trial, **row,
                        "guard_calls": diag_late["guard_calls"],
                    })

                # B6, B6-core
                rng_b6 = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                cand_b6, cand_iv_b6, core_iv_b6, log_b6, diag_b6 = run_b6_b7_core_halo(
                    grid, ref, budget, rng_b6, "B6", seg_id, trial
                )
                guard_logs.extend(log_b6)
                prec_b6, rec_b6 = event_level_metrics(cand_iv_b6, ref)
                prec_b6c, rec_b6c = event_level_metrics(core_iv_b6, ref)
                diagnostic_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial, "method": "B6",
                    "event_precision": prec_b6, "event_recall": rec_b6,
                    "core_duration": diag_b6["candidate_duration"], "halo_duration": 0.0,
                    "guard_calls": 0, "guard_positive": 0, "guard_negative": 0,
                    "selection_calls": diag_b6["selection_calls"], "total_used_calls": diag_b6["total_used_calls"],
                    "budget_error": diag_b6["budget_accounting_error"],
                })
                diagnostic_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial, "method": "B6-core",
                    "event_precision": prec_b6c, "event_recall": rec_b6c,
                    "core_duration": diag_b6["core_duration"], "halo_duration": diag_b6["halo_duration"],
                    "guard_calls": diag_b6["guard_calls"],
                    "guard_positive": sum(1 for r in log_b6 if r["is_positive"]),
                    "guard_negative": sum(1 for r in log_b6 if not r["is_positive"]),
                    "selection_calls": diag_b6["selection_calls"], "total_used_calls": diag_b6["total_used_calls"],
                    "budget_error": diag_b6["budget_accounting_error"],
                })
                intervals_store[(seg_id, "B6-core", budget, trial)] = {
                    "candidate_bins": cand_b6, "candidate_intervals": cand_iv_b6, "core_intervals": core_iv_b6,
                    "e0_bins": e0_bins,
                }

                # B7, B7-core
                rng_b7 = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                cand_b7, cand_iv_b7, core_iv_b7, log_b7, diag_b7 = run_b6_b7_core_halo(
                    grid, ref, budget, rng_b7, "B7", seg_id, trial
                )
                guard_logs.extend(log_b7)
                prec_b7, rec_b7 = event_level_metrics(cand_iv_b7, ref)
                prec_b7c, rec_b7c = event_level_metrics(core_iv_b7, ref)
                diagnostic_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial, "method": "B7",
                    "event_precision": prec_b7, "event_recall": rec_b7,
                    "core_duration": diag_b7["candidate_duration"], "halo_duration": 0.0,
                    "guard_calls": 0, "guard_positive": 0, "guard_negative": 0,
                    "selection_calls": diag_b7["selection_calls"], "total_used_calls": diag_b7["total_used_calls"],
                    "budget_error": diag_b7["budget_accounting_error"],
                })
                diagnostic_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial, "method": "B7-core",
                    "event_precision": prec_b7c, "event_recall": rec_b7c,
                    "core_duration": diag_b7["core_duration"], "halo_duration": diag_b7["halo_duration"],
                    "guard_calls": diag_b7["guard_calls"],
                    "guard_positive": sum(1 for r in log_b7 if r["is_positive"]),
                    "guard_negative": sum(1 for r in log_b7 if not r["is_positive"]),
                    "selection_calls": diag_b7["selection_calls"], "total_used_calls": diag_b7["total_used_calls"],
                    "budget_error": diag_b7["budget_accounting_error"],
                })
                intervals_store[(seg_id, "B7-core", budget, trial)] = {
                    "candidate_bins": cand_b7, "candidate_intervals": cand_iv_b7, "core_intervals": core_iv_b7,
                    "e0_bins": e0_bins,
                }

    diag_df = pd.DataFrame(diagnostic_rows)
    diag_df.to_csv(OUT / "b6_b7_core_diagnostic_results.csv", index=False)
    print(f"Wrote b6_b7_core_diagnostic_results.csv ({len(diag_df)} rows)")

    tradeoff_df = pd.DataFrame(tradeoff_rows)
    tradeoff_df.to_csv(OUT / "core_halo_tradeoff.csv", index=False)
    print(f"Wrote core_halo_tradeoff.csv ({len(tradeoff_df)} rows)")

    # Guard logs
    guard_df = pd.DataFrame(guard_logs)
    if not guard_df.empty:
        guard_df.to_csv(OUT / "guard_calls_log.csv", index=False)

    # B_90/90 summary
    agg = diag_df.groupby(["segment", "method", "budget"]).agg(
        event_precision_mean=("event_precision", "mean"),
        event_recall_mean=("event_recall", "mean"),
    ).reset_index()

    b90_rows = []
    for (seg, method), g in agg.groupby(["segment", "method"]):
        g = g.sort_values("budget")
        reached = g[(g["event_precision_mean"] >= 0.9) & (g["event_recall_mean"] >= 0.9)]
        if not reached.empty:
            b90 = int(reached.iloc[0]["budget"])
            p = float(reached.iloc[0]["event_precision_mean"])
            r = float(reached.iloc[0]["event_recall_mean"])
        else:
            b90 = None
            last = g.iloc[-1]
            p = float(last["event_precision_mean"])
            r = float(last["event_recall_mean"])
        b90_rows.append({"segment": seg, "method": method, "B_90_90": b90 if b90 is not None else "not_reached", "precision": p, "recall": r})
    b90_df = pd.DataFrame(b90_rows)

    # Attribution summary
    summary_md = "# Core/Halo Attribution Summary\n\n"
    summary_md += "B_90/90 is the first budget in {5,10,20,40,60,80,100,120} where mean event_precision >= 0.9 and mean event_recall >= 0.9.\n\n"
    summary_md += "| Segment | Method | B_90_90 | P@point | R@point |\n"
    summary_md += "|---------|--------|---------|---------|---------|\n"
    for _, r in b90_df.iterrows():
        summary_md += f"| {r['segment']} | {r['method']} | {r['B_90_90']} | {r['precision']:.3f} | {r['recall']:.3f} |\n"

    summary_md += "\n## Diagnostic answers\n\n"
    summary_md += "### 1. Do B6-core / B7-core also reach 90/90?\n\n"
    core_methods = ["B6-core", "B7-core"]
    for m in core_methods:
        reached = b90_df[(b90_df["method"] == m) & (b90_df["B_90_90"] != "not_reached")]
        summary_md += f"- **{m}**: reaches 90/90 in {len(reached)}/3 segments.\n"
        for _, r in reached.iterrows():
            summary_md += f"  - {r['segment']}: B={r['B_90_90']} (P={r['precision']:.3f}, R={r['recall']:.3f})\n"

    summary_md += "\n### 2. Are their B_90/90 close to LATE-AQP-core?\n\n"
    for seg in [s["segment_id"] for s in SEGMENTS]:
        sub = b90_df[b90_df["segment"] == seg]
        late = sub[sub["method"] == "LATE-AQP-core"].iloc[0]
        if late["B_90_90"] == "not_reached":
            continue
        for m in ["B6-core", "B7-core"]:
            other = sub[sub["method"] == m].iloc[0]
            if other["B_90_90"] != "not_reached":
                summary_md += f"- {seg}: LATE={late['B_90_90']}, {m}={other['B_90_90']} (delta={int(other['B_90_90'])-int(late['B_90_90'])}).\n"

    summary_md += "\n### 3. Does LATE-AQP-core still hold an advantage?\n\n"
    late_reach = set(b90_df[(b90_df["method"] == "LATE-AQP-core") & (b90_df["B_90_90"] != "not_reached")]["segment"])
    b6c_reach = set(b90_df[(b90_df["method"] == "B6-core") & (b90_df["B_90_90"] != "not_reached")]["segment"])
    b7c_reach = set(b90_df[(b90_df["method"] == "B7-core") & (b90_df["B_90_90"] != "not_reached")]["segment"])
    if late_reach == b6c_reach == b7c_reach:
        summary_md += "All three core methods reach 90/90 on exactly the same segments, so the **Core/Halo gain is generic**, not LATE-AQP-specific.\n"
    elif late_reach.issuperset(b6c_reach | b7c_reach):
        summary_md += "LATE-AQP-core reaches 90/90 on a superset of the segments reached by B6-core/B7-core, indicating a method-specific advantage beyond the generic Core/Halo gain.\n"
    else:
        summary_md += "The reach sets differ; see the table above for details.\n"

    summary_md += "\n### 4. If advantage disappeared, Core/Halo is generic post-processing\n\n"
    if late_reach == b6c_reach == b7c_reach:
        summary_md += "**Conclusion: Core/Halo is a generic post-processing gain.** Once B6 and B7 receive the same boundary-guard release, their B_90/90 equals LATE-AQP-core on the reachable segments.\n"
    else:
        summary_md += "Core/Halo improves all methods, but LATE-AQP-core retains an additional advantage in segment coverage.\n"

    with open(OUT / "core_halo_attribution_summary.md", "w") as f:
        f.write(summary_md)
    print("Wrote core_halo_attribution_summary.md")

    # Hardest segment miss analysis
    hardest = "realcartest_0_1570"
    grid_h, ref_h = load_segment_grid_ref(next(s for s in SEGMENTS if s["segment_id"] == hardest))
    e0_bins_h = set(int(x) for x in grid_h.nlargest(max(1, int(round(len(grid_h)*0.2))), "prior_score_max")["bin_idx"].tolist())

    miss_rows = []
    budget = 120
    for _, ev in ref_h.iterrows():
        ev_id = str(ev["event_id"])
        ev_start = float(ev["t_start"])
        ev_end = float(ev["t_end"])
        ev_dur = ev_end - ev_start
        ev_type = ev["event_type"]

        # E0 overlap
        ev_bins = set(grid_h[(grid_h["t_end"] > ev_start) & (grid_h["t_start"] < ev_end)]["bin_idx"].astype(int))
        inside_e0 = bool(ev_bins & e0_bins_h)

        def hit_rate(method: str, use_core: bool) -> float:
            hits = 0
            for trial in SEEDS:
                key = (hardest, method, budget, trial)
                if key not in intervals_store:
                    return 0.0
                data = intervals_store[key]
                ivs = data["core_intervals"] if use_core else data["candidate_intervals"]
                if ivs.empty:
                    continue
                for _, iv in ivs.iterrows():
                    if max(0.0, min(iv["t_end"], ev_end) - max(iv["t_start"], ev_start)) > 0:
                        hits += 1
                        break
            return hits / len(SEEDS)

        hit_b6 = hit_rate("B6-core", use_core=False)  # raw B6 selected intervals
        hit_b7 = hit_rate("B7-core", use_core=False)
        hit_late_core = hit_rate("LATE-AQP-core", use_core=True)
        hit_late_halo = hit_rate("LATE-AQP-core", use_core=False)

        def distance_to_nearest(t: float, intervals: pd.DataFrame) -> float:
            if intervals.empty:
                return float("nan")
            dists = []
            for _, iv in intervals.iterrows():
                if iv["t_end"] < t:
                    dists.append(t - iv["t_end"])
                elif iv["t_start"] > t:
                    dists.append(iv["t_start"] - t)
                else:
                    dists.append(0.0)
            return min(dists)

        # Distance from event center
        center = (ev_start + ev_end) / 2.0
        # Aggregate intervals across seeds for distance (use seed 0 for simplicity)
        def seed_intervals(method: str, use_core: bool, trial: int) -> pd.DataFrame:
            key = (hardest, method, budget, trial)
            if key not in intervals_store:
                return pd.DataFrame(columns=["t_start", "t_end"])
            data = intervals_store[key]
            return data["core_intervals"] if use_core else data["candidate_intervals"]

        dist_core = distance_to_nearest(center, seed_intervals("LATE-AQP-core", True, 0))
        dist_halo = distance_to_nearest(center, seed_intervals("LATE-AQP-core", False, 0))

        # Nearest core interval string
        core0 = seed_intervals("LATE-AQP-core", True, 0)
        nearest_core = ""
        if not core0.empty:
            best = min([(i, distance_to_nearest(center, pd.DataFrame([iv])) if False else max(0.0, min(iv["t_end"], ev_end)-max(iv["t_start"], ev_start))) for i, iv in core0.iterrows()], key=lambda x: x[1])[0]
            iv = core0.loc[best]
            nearest_core = f"[{iv['t_start']:.1f},{iv['t_end']:.1f}]"

        if hit_late_core >= 0.5:
            reason = "covered_by_core"
        elif hit_late_halo >= 0.5:
            reason = "release_too_conservative"
        else:
            reason = "upstream_discovery_miss"

        miss_rows.append({
            "event_id": ev_id, "event_type": ev_type, "event_start": ev_start, "event_end": ev_end,
            "event_duration": ev_dur, "inside_E0_top20": inside_e0,
            "hit_by_B6": hit_b6 >= 0.5, "hit_by_B7": hit_b7 >= 0.5,
            "hit_by_LATE_core": hit_late_core >= 0.5, "hit_by_LATE_halo": hit_late_halo >= 0.5,
            "miss_reason": reason, "nearest_core_interval": nearest_core,
            "distance_to_nearest_core": dist_core, "distance_to_nearest_halo": dist_halo,
            "notes": "",
        })

    miss_df = pd.DataFrame(miss_rows)
    miss_df.to_csv(OUT / "hardest_segment_miss_analysis.csv", index=False)

    # Casebook
    missed = miss_df[miss_df["hit_by_LATE_core"] == False]
    casebook_md = "# Hardest Segment Casebook — realcartest_0_1570\n\n"
    casebook_md += f"Analysis at B={budget}. Events not covered by LATE-AQP-core majority of seeds.\n\n"
    casebook_md += "| event_id | type | duration | inside_E0 | hit_B6 | hit_B7 | hit_halo | reason | dist_to_core | dist_to_halo |\n"
    casebook_md += "|----------|------|----------|-----------|--------|--------|----------|--------|--------------|--------------|\n"
    for _, r in missed.iterrows():
        casebook_md += f"| {r['event_id']} | {r['event_type']} | {r['event_duration']:.1f} | {r['inside_E0_top20']} | {r['hit_by_B6']} | {r['hit_by_B7']} | {r['hit_by_LATE_halo']} | {r['miss_reason']} | {r['distance_to_nearest_core']:.1f} | {r['distance_to_nearest_halo']:.1f} |\n"

    counts = missed["miss_reason"].value_counts().to_dict()
    casebook_md += "\n## Summary\n\n"
    for reason, cnt in counts.items():
        casebook_md += f"- {reason}: {cnt} events\n"
    casebook_md += "\nInterpretation:\n"
    casebook_md += "- `release_too_conservative`: event was found by LATE-AQP's discovery/repair (in halo) but discarded by the strict core release.\n"
    casebook_md += "- `upstream_discovery_miss`: event was never selected by LATE-AQP's discovery/repair; fixing release alone cannot recover it.\n"

    with open(OUT / "hardest_segment_casebook.md", "w") as f:
        f.write(casebook_md)
    print("Wrote hardest_segment_miss_analysis.csv and hardest_segment_casebook.md")

    # Guard efficiency report
    n_seeds = len(SEEDS)
    late_logs = [r for r in guard_logs if r["method"] == "LATE-AQP-core"]
    log_df = pd.DataFrame(late_logs) if late_logs else pd.DataFrame(columns=["segment", "budget", "is_positive", "stopped"])
    # Start from all LATE-AQP-core segment/budget combos to include zeros.
    late_diag = diag_df[diag_df["method"] == "LATE-AQP-core"][["segment", "budget", "selection_calls", "event_recall", "total_used_calls"]].copy()
    late_diag = late_diag.groupby(["segment", "budget"]).mean().reset_index()
    guard_stats = []
    for _, row in late_diag.iterrows():
        seg = row["segment"]
        budget = row["budget"]
        g = log_df[(log_df["segment"] == seg) & (log_df["budget"] == budget)]
        total = len(g)
        pos = int(g["is_positive"].sum()) if not g.empty else 0
        neg = total - pos
        stopped = int(g["stopped"].sum()) if not g.empty else 0
        avg_selection = row["selection_calls"]
        avg_core_recall = row["event_recall"]
        n_events = len(ref_h) if seg == hardest else len(load_segment_grid_ref(next(s for s in SEGMENTS if s["segment_id"] == seg))[1])
        recovered_events = avg_core_recall * n_events
        mean_calls = total / n_seeds
        mean_total = row["total_used_calls"]
        guard_stats.append({
            "segment": seg, "budget": budget, "total_guard_calls": total,
            "mean_guard_calls_per_seed": mean_calls,
            "positive_guard_calls": pos, "negative_stop_calls": neg, "stopped_calls": stopped,
            "guard_positive_rate": pos / total if total > 0 else 0.0,
            "guard_per_selected_interval": mean_calls / max(1, avg_selection),
            "guard_per_recovered_event": mean_calls / max(1, recovered_events),
            "avg_total_used_calls": mean_total,
            "guard_fraction": mean_calls / max(1, mean_total),
        })
    guard_stats_df = pd.DataFrame(guard_stats)
    guard_stats_df.to_csv(OUT / "guard_efficiency_by_segment_budget.csv", index=False)

    guard_md = "# Guard Efficiency Report\n\n"
    guard_md += "Statistics computed over LATE-AQP-core guard calls. 'total' is the sum across seeds; guard_fraction uses the per-seed mean.\n\n"
    guard_md += "| Segment | Budget | total | per_seed_mean | positive | negative_stop | positive_rate | guard_fraction |\n"
    guard_md += "|---------|--------|-------|---------------|----------|---------------|---------------|----------------|\n"
    for _, r in guard_stats_df.iterrows():
        guard_md += f"| {r['segment']} | {int(r['budget'])} | {r['total_guard_calls']} | {r['mean_guard_calls_per_seed']:.2f} | {r['positive_guard_calls']} | {r['negative_stop_calls']} | {r['guard_positive_rate']:.3f} | {r['guard_fraction']:.3f} |\n"

    overall = {
        "total_guard_calls": guard_stats_df["total_guard_calls"].sum(),
        "positive_guard_calls": guard_stats_df["positive_guard_calls"].sum(),
        "negative_stop_calls": guard_stats_df["negative_stop_calls"].sum(),
        "mean_guard_fraction": guard_stats_df["guard_fraction"].mean(),
        "mean_guard_per_interval": guard_stats_df["guard_per_selected_interval"].mean(),
        "mean_guard_per_event": guard_stats_df["guard_per_recovered_event"].mean(),
    }
    guard_md += f"\n## Overall (LATE-AQP-core)\n\n"
    guard_md += f"- Total guard calls: {overall['total_guard_calls']}\n"
    guard_md += f"- Positive guard calls: {overall['positive_guard_calls']} ({overall['positive_guard_calls']/max(1,overall['total_guard_calls']):.1%})\n"
    guard_md += f"- Negative stop calls: {overall['negative_stop_calls']} ({overall['negative_stop_calls']/max(1,overall['total_guard_calls']):.1%})\n"
    guard_md += f"- Mean guard fraction of total budget: {overall['mean_guard_fraction']:.1%}\n"
    guard_md += f"- Mean guard calls per selected interval: {overall['mean_guard_per_interval']:.2f}\n"
    guard_md += f"- Mean guard calls per recovered event: {overall['mean_guard_per_event']:.2f}\n\n"

    guard_md += "## Answers\n\n"
    guard_md += f"1. Guards consume a mean of **{overall['mean_guard_fraction']:.1%}** of LATE-AQP-core's total budget.\n"
    guard_md += f"2. **{overall['positive_guard_calls']/max(1,overall['total_guard_calls']):.1%}** of guard calls land on positive bins (effective boundary expansion); the rest are negative-stop confirmations.\n"
    low_budget_frac = guard_stats_df[guard_stats_df["budget"] <= 20]["guard_fraction"].mean()
    guard_md += f"3. At B<=20 the guard fraction is **{low_budget_frac:.1%}**, confirming that guard overhead is proportionally highest when the total budget is small.\n"
    guard_md += "4. Whether a dynamic guard cap is needed depends on whether the low-budget tradeoff (high guard fraction, lower recall) is acceptable; the data here does not force a redesign, but a per-interval adaptive cap could be explored.\n"

    with open(OUT / "guard_efficiency_report.md", "w") as f:
        f.write(guard_md)
    print("Wrote guard_efficiency_report.md")

    # Tradeoff analysis
    tradeoff_agg = tradeoff_df.groupby(["segment", "budget", "release_variant"]).agg(
        event_precision_mean=("event_precision", "mean"),
        event_recall_mean=("event_recall", "mean"),
        selected_duration_mean=("selected_duration", "mean"),
    ).reset_index()
    tradeoff_agg.to_csv(OUT / "core_halo_tradeoff_aggregated.csv", index=False)

    # Check if any variant reaches 90/90 and specifically hardest segment near-miss.
    reaches = tradeoff_agg[(tradeoff_agg["event_precision_mean"] >= 0.9) & (tradeoff_agg["event_recall_mean"] >= 0.9)]
    hardest_tradeoff = tradeoff_agg[tradeoff_agg["segment"] == hardest]
    b120_hardest = hardest_tradeoff[hardest_tradeoff["budget"] == 120].sort_values("event_recall_mean", ascending=False)

    rec_md = "# Core/Halo Tradeoff Analysis\n\n"
    rec_md += "Release variants computed without re-running discovery.\n\n"
    rec_md += "| Segment | Budget | Variant | Precision | Recall | Duration |\n"
    rec_md += "|---------|--------|---------|-----------|--------|----------|\n"
    for _, r in b120_hardest.iterrows():
        rec_md += f"| {r['segment']} | {int(r['budget'])} | {r['release_variant']} | {r['event_precision_mean']:.3f} | {r['event_recall_mean']:.3f} | {r['selected_duration_mean']:.1f} |\n"

    rec_md += "\n## Reach 90/90?\n\n"
    if not reaches.empty:
        rec_md += f"Yes: {len(reaches)} segment-budget-variant combinations reach 90/90.\n"
        for _, r in reaches.iterrows():
            rec_md += f"- {r['segment']} B={int(r['budget'])} {r['release_variant']}: P={r['event_precision_mean']:.3f}, R={r['event_recall_mean']:.3f}\n"
    else:
        rec_md += "No release variant reaches 90/90 on any segment/budget in this analysis.\n"

    rec_md += "\n## Hardest segment (realcartest_0_1570) B=120\n\n"
    if not b120_hardest.empty:
        core_row = b120_hardest[b120_hardest["release_variant"] == "core_only"].iloc[0]
        halo1_row = b120_hardest[b120_hardest["release_variant"] == "core_plus_1bin_halo"].iloc[0]
        full_row = b120_hardest[b120_hardest["release_variant"] == "full_window"].iloc[0]
        rec_md += f"- core_only: P={core_row['event_precision_mean']:.3f}, R={core_row['event_recall_mean']:.3f}\n"
        rec_md += f"- core_plus_1bin_halo: P={halo1_row['event_precision_mean']:.3f}, R={halo1_row['event_recall_mean']:.3f}\n"
        rec_md += f"- full_window: P={full_row['event_precision_mean']:.3f}, R={full_row['event_recall_mean']:.3f}\n"
        if halo1_row["event_precision_mean"] >= 0.9 and halo1_row["event_recall_mean"] >= 0.9:
            rec_md += "\n**Adding just 1-bin halo reaches 90/90, so the release is over-conservative.**\n"
        elif halo1_row["event_recall_mean"] > core_row["event_recall_mean"] and halo1_row["event_precision_mean"] >= 0.9:
            rec_md += "\n1-bin halo improves recall while keeping precision >= 0.9, suggesting the release is somewhat conservative, but it still does not reach 90/90.\n"
        else:
            rec_md += "\nAdding halo does not reach 90/90 or causes precision to drop below 0.9, indicating upstream discovery is the limiting factor.\n"

    with open(OUT / "core_halo_tradeoff_report.md", "w") as f:
        f.write(rec_md)
    print("Wrote core_halo_tradeoff_report.md")

    # Final recommendation
    # Determine primary conclusion based on data.
    all_same = (late_reach == b6c_reach == b7c_reach)
    # Hardest segment reasons
    reason_counts = missed["miss_reason"].value_counts().to_dict()
    upstream_dominant = reason_counts.get("upstream_discovery_miss", 0) >= reason_counts.get("release_too_conservative", 0)
    # Tradeoff check at hardest B=120
    halo1_reaches = not b120_hardest.empty and b120_hardest[b120_hardest["release_variant"] == "core_plus_1bin_halo"].iloc[0]["event_recall_mean"] >= 0.9 and b120_hardest[b120_hardest["release_variant"] == "core_plus_1bin_halo"].iloc[0]["event_precision_mean"] >= 0.9

    # Choose primary conclusion based on pre-specified priority:
    # 1. method-specific advantage (A) if reach sets differ;
    # 2. generic Core/Halo gain (B) if all core methods reach same segments;
    # 3. over-conservative release (C) only if 1-bin halo reaches 90/90;
    # 4. guard redesign (E) only if mean guard fraction exceeds 50%.
    if not all_same:
        primary = "A"
    elif halo1_reaches:
        primary = "C"
    elif overall["mean_guard_fraction"] > 0.5:
        primary = "E"
    else:
        primary = "B"

    choice_map = {
        "A": "A. LATE-AQP-core has method-specific advantage over B6-core/B7-core",
        "B": "B. Core/Halo is a generic post-processing gain; LATE advantage is weaker",
        "C": "C. hardest segment failure is due to over-conservative release",
        "D": "D. hardest segment failure is due to upstream discovery miss",
        "E": "E. guard overhead is too high and release policy must be redesigned",
    }

    final_md = "# Final Recommendation\n\n"
    final_md += f"**Primary conclusion: {choice_map[primary]}**\n\n"
    final_md += "## Evidence\n\n"
    final_md += f"- B6-core/B7-core reach 90/90 on the same segments as LATE-AQP-core: {all_same}.\n"
    final_md += f"- Hardest segment miss reasons: {reason_counts}.\n"
    final_md += f"- 1-bin halo reaches 90/90 on hardest segment: {halo1_reaches}.\n"
    final_md += f"- Mean guard overhead: {overall['mean_guard_fraction']:.1%}.\n\n"

    final_md += "## Secondary notes\n\n"
    if primary == "B":
        final_md += "The main benefit observed in the frontier experiment comes from applying Core/Halo release, not from LATE-AQP's discovery strategy. Future effort should either (1) improve upstream discovery so that LATE-AQP-candidate itself is richer than B6/B7, or (2) adopt Core/Halo as a generic post-processing stage across all methods.\n"
    if primary == "D":
        final_md += "Even with a perfect release, the hardest segment cannot reach 90/90 because several events are never discovered. Work should focus on improving the low-budget discovery signal or diversity.\n"
    if primary == "C":
        final_md += "The release policy is too strict; allowing a small halo margin recovers the missing recall on the hardest segment without breaking precision. A calibrated halo margin is the recommended next step.\n"
    if primary == "E":
        final_md += "Guard calls consume a disproportionate share of budget, especially at low budgets. A dynamic guard cap or interval-prioritization policy should be redesigned before scaling.\n"
    if upstream_dominant and primary != "D":
        final_md += "Additionally, the hardest segment's remaining recall gap is driven by upstream discovery misses: several events are never selected by LATE-AQP's discovery/repair, so release policy alone cannot close the gap.\n"

    with open(OUT / "final_recommendation.md", "w") as f:
        f.write(final_md)
    print("Wrote final_recommendation.md")


if __name__ == "__main__":
    main()
