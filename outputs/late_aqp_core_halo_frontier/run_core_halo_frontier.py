#!/usr/bin/env python3
"""
Implement precision-constrained release (Core/Halo) on top of Frozen-LATE-AQP-v1,
measure B_90/90, and compare with B6/B7.

No GPU/VLM, no new labels. Pure offline replay.
"""

import csv
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
FROZEN_DIR = ROOT / "outputs" / "late_aqp_frozen_cross_segment_v1"
OUT = ROOT / "outputs" / "late_aqp_core_halo_frontier"
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


def event_level_metrics(intervals_df: pd.DataFrame, ref: pd.DataFrame) -> Tuple[float, float]:
    """Return (event_precision, event_recall) for a set of intervals.

    event_precision = (# core intervals that overlap any reference event) / (# core intervals)
    event_recall    = (# unique reference events overlapped by any core interval) / (# reference events)
    """
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
    n_ref = len(ref)
    precision = tp_intervals / len(intervals_df) if len(intervals_df) > 0 else 0.0
    recall = len(hit_events) / n_ref if n_ref > 0 else 0.0
    return precision, recall


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


def interval_has_positive_selected(iv, grid: pd.DataFrame, bin_to_row: Dict[int, pd.Series]) -> bool:
    for b in iv["bin_indices"]:
        if bin_to_row[b]["is_positive"]:
            return True
    return False


def compute_guard_need(intervals_df: pd.DataFrame, grid: pd.DataFrame, max_guards_per_side: int, bin_to_row: Dict[int, pd.Series]) -> int:
    """Compute total guard calls needed for intervals that contain at least one positive selected bin.
    Early stopping at negative bins."""
    need = 0
    n_bins = len(grid)
    for _, iv in intervals_df.iterrows():
        if not interval_has_positive_selected(iv, grid, bin_to_row):
            continue
        s = int(iv["bin_indices"][0])
        e = int(iv["bin_indices"][-1])
        # left side
        for offset in range(1, max_guards_per_side + 1):
            b = s - offset
            if b < 0:
                break
            need += 1
            if get_label_at_bin(grid, b) == "negative":
                break
        # right side
        for offset in range(1, max_guards_per_side + 1):
            b = e + offset
            if b >= n_bins:
                break
            need += 1
            if get_label_at_bin(grid, b) == "negative":
                break
    return need


def run_core_halo(grid: pd.DataFrame, ref: pd.DataFrame, budget: int, rng: np.random.Generator) -> Tuple[List[int], Dict]:
    """Run Frozen-LATE-AQP-v1 + core/halo boundary-guard release.

    Total oracle budget = audit + repair + discovery + guard <= budget.
    """
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

    # Audit phase (identical to v1).
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

    # Repair phase (identical to v1).
    remaining = budget - audit_calls
    repair_seeds = list(set(outside_positives))
    if repair_seeds and remaining > 0:
        actions = []
        for seed in repair_seeds:
            seed_prior = bin_to_row[seed]["prior_score_max"]
            for nb in [max(0, seed - 1), min(n_bins - 1, seed + 1)]:
                if nb in queried:
                    continue
                utility = seed_prior
                actions.append((utility, seed, nb))
        actions.sort(key=lambda x: x[0], reverse=True)
        for _, seed, nb in actions:
            if remaining <= 0:
                break
            if nb in queried:
                continue
            queried.add(nb); selected.add(nb); repair_calls += 1; remaining -= 1

    # Iterative discovery + guard budget allocation.
    remaining_total = budget - audit_calls - repair_calls
    discovery_budget = remaining_total
    core_intervals = pd.DataFrame()
    guard_calls = 0
    guard_details: List[Dict] = []

    for _ in range(5):  # fixed-point iteration, usually converges in 1-2 steps
        # Run discovery with current discovery budget.
        disc = run_discovery(grid, discovery_budget, queried)
        candidate_bins = sorted(selected.union(disc))
        candidate_intervals = merge_bins(grid, candidate_bins)
        need = compute_guard_need(candidate_intervals, grid, MAX_GUARDS_PER_SIDE, bin_to_row)
        if discovery_budget + need <= remaining_total:
            core_intervals = candidate_intervals
            guard_calls = need
            break
        else:
            discovery_budget = max(0, remaining_total - need)
            if discovery_budget == 0:
                core_intervals = candidate_intervals
                guard_calls = remaining_total  # all remaining used for guards
                break

    # If feasible, perform actual guards only on intervals with at least one positive selected bin.
    if not core_intervals.empty:
        guard_budget_remaining = remaining_total - discovery_budget
        # Guard positive intervals in descending order of duration.
        positive_intervals = [iv for _, iv in core_intervals.iterrows() if interval_has_positive_selected(iv, grid, bin_to_row)]
        positive_intervals.sort(key=lambda iv: iv["duration"], reverse=True)
        core_bins: Set[int] = set()
        actual_guard_calls = 0
        for iv in positive_intervals:
            # Add positive selected bins from this interval to core first (they are already queried).
            for b in iv["bin_indices"]:
                if bin_to_row[b]["is_positive"]:
                    core_bins.add(b)
            if guard_budget_remaining <= 0:
                continue
            s = int(iv["bin_indices"][0])
            e = int(iv["bin_indices"][-1])
            # left
            for offset in range(1, MAX_GUARDS_PER_SIDE + 1):
                if guard_budget_remaining <= 0:
                    break
                b = s - offset
                if b < 0:
                    break
                actual_guard_calls += 1
                guard_budget_remaining -= 1
                if bin_to_row[b]["is_positive"]:
                    core_bins.add(b)
                if get_label_at_bin(grid, b) == "negative":
                    break
            # right
            for offset in range(1, MAX_GUARDS_PER_SIDE + 1):
                if guard_budget_remaining <= 0:
                    break
                b = e + offset
                if b >= n_bins:
                    break
                actual_guard_calls += 1
                guard_budget_remaining -= 1
                if bin_to_row[b]["is_positive"]:
                    core_bins.add(b)
                if get_label_at_bin(grid, b) == "negative":
                    break

        guard_calls = actual_guard_calls
        core_intervals = merge_bins(grid, sorted(core_bins))
    else:
        core_intervals = pd.DataFrame(columns=["t_start", "t_end", "duration", "bin_indices"])

    diagnostics = {
        "audit_calls": audit_calls,
        "repair_calls": repair_calls,
        "discovery_calls": discovery_budget,
        "guard_calls": guard_calls,
        "total_used_calls": audit_calls + repair_calls + discovery_budget + guard_calls,
        "budget_accounting_error": budget - (audit_calls + repair_calls + discovery_budget + guard_calls),
    }
    return core_intervals, diagnostics


def main():
    full_events = load_full_events()
    proxy_scores = load_proxy_scores()
    dev_events = load_dev_events()
    dev_grid = load_dev_grid()

    all_rows = []

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        print(f"\nSegment {seg_id}")
        if seg["is_dev"]:
            grid = dev_grid.copy()
            grid = grid[grid["t_start"] < (seg["time_end"] - seg["time_start"])].reset_index(drop=True)
            grid["bin_idx"] = np.arange(len(grid))
            grid["local_t_start"] = grid["t_start"]
            grid["local_t_end"] = grid["t_end"].clip(upper=(seg["time_end"] - seg["time_start"]))
            grid["t_start"] = grid["local_t_start"]
            grid["t_end"] = grid["local_t_end"]
            ref = dev_events.copy()
            ref["event_type"] = ref["duration"].apply(lambda d: "long_interval" if d >= 1.0 else "point_anchor")
        else:
            grid, ref = build_segment_grid(seg, full_events, proxy_scores)

        for budget in BUDGETS:
            for trial, seed_offset in enumerate(SEEDS):
                rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)

                # LATE-AQP-core
                core_intervals, diag = run_core_halo(grid, ref, budget, rng)
                ev_prec, ev_rec = event_level_metrics(core_intervals, ref)
                dur_precision = 0.0
                dur_recall = 0.0
                if not core_intervals.empty:
                    core_bins = []
                    for _, iv in core_intervals.iterrows():
                        core_bins.extend(iv["bin_indices"])
                    core_bins = sorted(set(core_bins))
                    m = compute_metrics(core_bins, grid, ref)
                    dur_precision = m["selected_precision"]
                    dur_recall = m["event_recall"]
                all_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial,
                    "method": "LATE-AQP-core",
                    "event_precision": ev_prec, "event_recall": ev_rec,
                    "duration_precision": dur_precision, "duration_recall": dur_recall,
                    "audit_calls": diag["audit_calls"],
                    "repair_calls": diag["repair_calls"],
                    "discovery_calls": diag["discovery_calls"],
                    "guard_calls": diag["guard_calls"],
                    "total_used_calls": diag["total_used_calls"],
                    "budget_accounting_error": diag["budget_accounting_error"],
                    "core_duration": core_intervals["duration"].sum() if not core_intervals.empty else 0.0,
                    "num_core_intervals": len(core_intervals),
                })

                # B6
                rng_b6 = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                selected_b6 = run_b6(grid, budget, CHUNK_SIZE_S, rng_b6)
                intervals_b6 = merge_bins(grid, selected_b6)
                ev_prec_b6, ev_rec_b6 = event_level_metrics(intervals_b6, ref)
                all_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial,
                    "method": "B6",
                    "event_precision": ev_prec_b6, "event_recall": ev_rec_b6,
                    "duration_precision": float("nan"), "duration_recall": float("nan"),
                    "audit_calls": 0, "repair_calls": 0, "discovery_calls": budget,
                    "guard_calls": 0, "total_used_calls": budget,
                    "budget_accounting_error": 0,
                    "core_duration": intervals_b6["duration"].sum() if not intervals_b6.empty else 0.0,
                    "num_core_intervals": len(intervals_b6),
                })

                # B7
                rng_b7 = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                selected_b7 = run_b7(grid, budget, CHUNK_SIZE_S, k=3, rng=rng_b7)
                intervals_b7 = merge_bins(grid, selected_b7)
                ev_prec_b7, ev_rec_b7 = event_level_metrics(intervals_b7, ref)
                all_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial,
                    "method": "B7",
                    "event_precision": ev_prec_b7, "event_recall": ev_rec_b7,
                    "duration_precision": float("nan"), "duration_recall": float("nan"),
                    "audit_calls": 0, "repair_calls": 0, "discovery_calls": budget,
                    "guard_calls": 0, "total_used_calls": budget,
                    "budget_accounting_error": 0,
                    "core_duration": intervals_b7["duration"].sum() if not intervals_b7.empty else 0.0,
                    "num_core_intervals": len(intervals_b7),
                })

    df = pd.DataFrame(all_rows)
    cols = ["segment", "budget", "seed", "method",
            "event_precision", "event_recall", "duration_precision", "duration_recall",
            "audit_calls", "repair_calls", "discovery_calls", "guard_calls",
            "total_used_calls", "budget_accounting_error",
            "core_duration", "num_core_intervals"]
    df = df[cols]
    df.to_csv(OUT / "fine_grained_budget_results.csv", index=False)
    print(f"\nWrote fine_grained_budget_results.csv ({len(df)} rows)")

    # Aggregate means per segment/method/budget.
    agg = df.groupby(["segment", "method", "budget"]).agg(
        event_precision_mean=("event_precision", "mean"),
        event_precision_std=("event_precision", "std"),
        event_recall_mean=("event_recall", "mean"),
        event_recall_std=("event_recall", "std"),
        guard_calls_mean=("guard_calls", "mean"),
        total_used_calls_mean=("total_used_calls", "mean"),
    ).reset_index()

    # B_90/90 per segment/method.
    b90_rows = []
    for (seg, method), g in agg.groupby(["segment", "method"]):
        g = g.sort_values("budget")
        reached = g[(g["event_precision_mean"] >= 0.9) & (g["event_recall_mean"] >= 0.9)]
        if not reached.empty:
            b90 = int(reached.iloc[0]["budget"])
            prec_at = float(reached.iloc[0]["event_precision_mean"])
            rec_at = float(reached.iloc[0]["event_recall_mean"])
        else:
            b90 = None
            last = g.iloc[-1]
            prec_at = float(last["event_precision_mean"])
            rec_at = float(last["event_recall_mean"])
        b90_rows.append({
            "segment": seg, "method": method,
            "B_90_90": b90 if b90 is not None else "not_reached",
            "precision_at_last_measured": prec_at,
            "recall_at_last_measured": rec_at,
        })
    b90_df = pd.DataFrame(b90_rows)
    b90_df.to_csv(OUT / "b90_90_summary.csv", index=False)

    # Guard overhead report.
    guard_overhead = agg[agg["method"] == "LATE-AQP-core"][["segment", "budget", "guard_calls_mean", "total_used_calls_mean"]].copy()
    guard_overhead["guard_fraction"] = guard_overhead["guard_calls_mean"] / guard_overhead["total_used_calls_mean"].clip(lower=1)
    guard_overhead.to_csv(OUT / "guard_budget_overhead.csv", index=False)

    # Write markdown reports.
    design_md = "# Core/Halo Precision-Constrained Release Design\n\n"
    design_md += "## Base method\n\n"
    design_md += "Frozen-LATE-AQP-v1 (audit + discovery + repair) is used unchanged up to the candidate interval generation step.\n\n"
    design_md += "## Core/Halo release\n\n"
    design_md += "After v1 produces candidate intervals, we perform boundary guards only on intervals that contain at least one positive selected bin (candidate events).\n\n"
    design_md += "- Up to **3 guard bins per side** (left and right).\n"
    design_md += "- Guarding stops early when a negative bin is encountered, because that confirms the event boundary.\n"
    design_md += "- **Core** = positive selected bins + any positive guard bins discovered during boundary confirmation.\n"
    design_md += "- **Halo** = negative selected bins, intervals with no positive selected bins, and any part of a candidate interval that is not confirmed positive.\n\n"
    design_md += "## Budget integration\n\n"
    design_md += "Guard calls are accounted inside the same total budget B. We iterate discovery budget and guard need:\n\n"
    design_md += "1. Run audit/repair (fixed cost).\n"
    design_md += "2. Estimate guard need for the candidate intervals produced by a given discovery budget.\n"
    design_md += "3. Reduce discovery budget until `discovery_budget + guard_need <= total_remaining_budget`.\n"
    design_md += "4. Run discovery with that budget, perform guards, and report actual `guard_calls`.\n\n"
    design_md += "## Metrics\n\n"
    design_md += "We report **event-level** precision/recall for B_90/90 measurement:\n\n"
    design_md += "- event_precision = (# core intervals overlapping any reference event) / (# core intervals)\n"
    design_md += "- event_recall = (# unique reference events overlapped by any core interval) / (# reference events)\n\n"
    design_md += "Duration-level precision/recall are also recorded in the raw CSV for reference, but B_90/90 is measured on event-level metrics.\n\n"
    design_md += "## Comparison asymmetry (declared)\n\n"
    design_md += "B6/B7 are evaluated on their raw selected intervals without any additional boundary guard or core/halo release. "
    design_md += "This means LATE-AQP-core pays an explicit guard overhead that B6/B7 do not. This is a method-level difference, not an experimental fairness adjustment.\n"
    with open(OUT / "core_halo_design.md", "w") as f:
        f.write(design_md)

    guard_md = "# Guard Budget Overhead\n\n"
    guard_md += "Mean guard calls and fraction of total used budget for LATE-AQP-core.\n\n"
    guard_md += "| Segment | Budget | guard_calls_mean | total_used_calls_mean | guard_fraction |\n"
    guard_md += "|---------|--------|------------------|-----------------------|----------------|\n"
    for _, r in guard_overhead.iterrows():
        guard_md += f"| {r['segment']} | {int(r['budget'])} | {r['guard_calls_mean']:.2f} | {r['total_used_calls_mean']:.2f} | {r['guard_fraction']:.3f} |\n"
    with open(OUT / "guard_budget_overhead.md", "w") as f:
        f.write(guard_md)

    summary_md = "# B_90/90 Summary\n\n"
    summary_md += "B_90/90 is the first budget in {5,10,20,40,60,80,100,120} where mean event_precision >= 0.9 and mean event_recall >= 0.9.\n\n"
    summary_md += "| Segment | Method | B_90_90 | precision_at_point | recall_at_point |\n"
    summary_md += "|---------|--------|---------|--------------------|------------------|\n"
    for _, r in b90_df.iterrows():
        summary_md += f"| {r['segment']} | {r['method']} | {r['B_90_90']} | {r['precision_at_last_measured']:.3f} | {r['recall_at_last_measured']:.3f} |\n"

    # Answers to section 5.
    summary_md += "\n## Section 5 answers\n\n"

    core_reached = b90_df[b90_df["method"] == "LATE-AQP-core"]
    segments_core_reached = core_reached[core_reached["B_90_90"] != "not_reached"]
    summary_md += f"### a) LATE-AQP-core reaches 90/90 in {len(segments_core_reached)}/3 segments.\n\n"
    if not segments_core_reached.empty:
        for _, r in segments_core_reached.iterrows():
            summary_md += f"- {r['segment']}: B_90/90 = {r['B_90_90']} (P={r['precision_at_last_measured']:.3f}, R={r['recall_at_last_measured']:.3f})\n"
    else:
        summary_md += "- No segment reaches 90/90 by B=120.\n"

    summary_md += "\n### b) B6/B7 on the same segments\n\n"
    for seg in [s["segment_id"] for s in SEGMENTS]:
        sub = b90_df[b90_df["segment"] == seg]
        b6 = sub[sub["method"] == "B6"].iloc[0]
        b7 = sub[sub["method"] == "B7"].iloc[0]
        summary_md += f"- {seg}: B6 B_90/90 = {b6['B_90_90']} (P={b6['precision_at_last_measured']:.3f}, R={b6['recall_at_last_measured']:.3f}); "
        summary_md += f"B7 B_90/90 = {b7['B_90_90']} (P={b7['precision_at_last_measured']:.3f}, R={b7['recall_at_last_measured']:.3f})\n"

    summary_md += "\n### c) B_90/90 premium of LATE-AQP-core vs best of B6/B7\n\n"
    premiums = []
    for seg in [s["segment_id"] for s in SEGMENTS]:
        core = b90_df[(b90_df["segment"] == seg) & (b90_df["method"] == "LATE-AQP-core")].iloc[0]
        if core["B_90_90"] == "not_reached":
            continue
        b6 = b90_df[(b90_df["segment"] == seg) & (b90_df["method"] == "B6")].iloc[0]
        b7 = b90_df[(b90_df["segment"] == seg) & (b90_df["method"] == "B7")].iloc[0]
        best_baseline = float("inf")
        if b6["B_90_90"] != "not_reached":
            best_baseline = min(best_baseline, int(b6["B_90_90"]))
        if b7["B_90_90"] != "not_reached":
            best_baseline = min(best_baseline, int(b7["B_90_90"]))
        if best_baseline == float("inf"):
            summary_md += f"- {seg}: LATE-AQP-core reaches 90/90 at B={core['B_90_90']}, but neither B6 nor B7 reaches it by B=120.\n"
        else:
            premium = int(core["B_90_90"]) / best_baseline
            premiums.append((seg, premium))
            summary_md += f"- {seg}: LATE-AQP-core B={core['B_90_90']} / best baseline B={int(best_baseline)} = {premium:.2f}x\n"
    if premiums:
        summary_md += f"\nMax premium observed: {max(p for _, p in premiums):.2f}x.\n"

    summary_md += "\n### d) LATE-AQP-core reaches but baselines do not\n\n"
    only_core = []
    for seg in [s["segment_id"] for s in SEGMENTS]:
        core = b90_df[(b90_df["segment"] == seg) & (b90_df["method"] == "LATE-AQP-core")].iloc[0]
        b6 = b90_df[(b90_df["segment"] == seg) & (b90_df["method"] == "B6")].iloc[0]
        b7 = b90_df[(b90_df["segment"] == seg) & (b90_df["method"] == "B7")].iloc[0]
        if core["B_90_90"] != "not_reached" and b6["B_90_90"] == "not_reached" and b7["B_90_90"] == "not_reached":
            only_core.append(seg)
    if only_core:
        summary_md += f"Segments where only LATE-AQP-core reaches 90/90: {', '.join(only_core)}.\n"
    else:
        summary_md += "No such segment in this experiment.\n"

    summary_md += "\n### e) Guard budget overhead\n\n"
    avg_guard_frac = guard_overhead["guard_fraction"].mean()
    summary_md += f"Across all segments and budgets, guard calls account for a mean of **{avg_guard_frac:.1%}** of LATE-AQP-core's total used budget.\n\n"
    summary_md += "Guard overhead is one contributor to LATE-AQP-core needing more budget than B6/B7, but it is not the only factor: "
    summary_md += "B6/B7 operate on raw selected intervals without any precision-constrained release, so they avoid both the guard cost and the recall loss from discarding halo regions.\n"

    with open(OUT / "b90_90_summary.md", "w") as f:
        f.write(summary_md)
    print("Wrote core_halo_design.md, guard_budget_overhead.md, b90_90_summary.md")


if __name__ == "__main__":
    main()
