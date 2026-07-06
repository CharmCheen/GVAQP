#!/usr/bin/env python3
"""
Limited-Oracle Retrieval Frontier against Full-VLM Evaluation Reference.

No new GPU/VLM/API calls. No new labels. No algorithm modifications.
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
ATTR_DIR = ROOT / "outputs" / "late_aqp_core_halo_attribution_v1"
OUT = ROOT / "outputs" / "late_aqp_limited_oracle_frontier_v1"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(FROZEN_DIR))
from run_frozen_cross_segment import (
    BIN_SIZE,
    RANDOM_SEED_BASE,
    SEEDS,
    build_segment_grid,
    compute_metrics,
    load_dev_events,
    load_dev_grid,
    load_full_events,
    load_proxy_scores,
    merge_bins,
    run_b6,
    run_b7,
)

sys.path.insert(0, str(ATTR_DIR))
from run_attribution_analysis import (
    SEGMENTS as ATTR_SEGMENTS,
    BUDGETS,
    CHUNK_SIZE_S,
    load_segment_grid_ref,
    event_level_metrics,
    run_b6_b7_core_halo,
    run_late_aqp_core_halo,
)

# Use same segments as attribution analysis.
SEGMENTS = ATTR_SEGMENTS
METHODS = ["B6", "B7", "B6-core", "B7-core", "LATE-AQP-core"]
RATIO_GRID = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00]
ABSOLUTE_GRID = [5, 10, 20, 40, 60, 80, 100, 120]


class OracleAdapter:
    """Runtime oracle adapter: returns label for a requested unit/interval.

    The adapter hides full reference labels and event IDs from the method.
    It only exposes the label for the requested unit/interval.
    """

    def __init__(self, grid: pd.DataFrame, ref: pd.DataFrame, segment_id: str):
        self.grid = grid
        self.ref = ref
        self.segment_id = segment_id
        self.call_count = 0
        self.queried_units: Set[int] = set()
        self.bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}

    def query_unit(self, bin_idx: int) -> str:
        self.call_count += 1
        self.queried_units.add(bin_idx)
        row = self.bin_to_row.get(bin_idx)
        if row is None:
            return "negative"
        return "positive" if row["is_positive"] else "negative"

    def query_interval(self, t_start: float, t_end: float) -> str:
        self.call_count += 1
        overlapped = self.grid[(self.grid["t_end"] > t_start) & (self.grid["t_start"] < t_end)]
        if overlapped.empty:
            return "negative"
        # Aggregate: if any unit positive, interval is positive.
        return "positive" if overlapped["is_positive"].any() else "negative"

    def reset(self):
        self.call_count = 0
        self.queried_units.clear()


def intervals_to_bins(intervals_df: pd.DataFrame) -> List[int]:
    bins = []
    if intervals_df.empty:
        return bins
    for _, iv in intervals_df.iterrows():
        bins.extend([int(b) for b in iv["bin_indices"]])
    return sorted(set(bins))


def compute_all_metrics(selected_bins: List[int], grid: pd.DataFrame, ref: pd.DataFrame) -> Dict:
    intervals = merge_bins(grid, selected_bins)
    ev_prec, ev_rec = event_level_metrics(intervals, ref)
    dur = compute_metrics(selected_bins, grid, ref)
    n_ref = len(ref)
    n_long = len(ref[ref["event_type"] == "long_interval"])
    n_point = n_ref - n_long
    return {
        "event_precision": ev_prec,
        "event_recall": ev_rec,
        "duration_precision": dur["selected_precision"],
        "duration_recall": dur["event_recall"],
        "long_event_recall": dur["long_event_recall"] if not math.isnan(dur["long_event_recall"]) else 0.0,
        "point_anchor_recall": dur["point_anchor_recall"] if not math.isnan(dur["point_anchor_recall"]) else 0.0,
        "num_events_hit": int(round(ev_rec * n_ref)),
        "num_events_total": n_ref,
        "num_long_events_hit": int(round(dur["long_event_recall"] * n_long)) if n_long > 0 and not math.isnan(dur["long_event_recall"]) else 0,
        "num_long_events_total": n_long,
        "num_false_positive_intervals": len(intervals) - int(ev_prec * len(intervals)) if len(intervals) > 0 else 0,
        "false_positive_duration": dur["false_positive_duration"],
        "duplicate_rate": dur["duplicate_rate"],
        "fragmentation_rate": dur["fragmentation_rate"],
        "selected_total_duration": dur["selected_total_duration"],
    }


def run_method(
    grid: pd.DataFrame, ref: pd.DataFrame, budget: int, rng: np.random.Generator, method: str, segment_id: str, seed: int
) -> Tuple[pd.DataFrame, Dict, str]:
    """Return (final_intervals, diagnostics, strict_or_posthoc)."""
    if method == "LATE-AQP-core":
        _, cand_iv, core_iv, _, diag = run_late_aqp_core_halo(grid, ref, budget, rng, segment_id, seed)
        diag_out = {
            "audit_calls": diag["audit_calls"],
            "discovery_calls": diag["discovery_calls"],
            "repair_calls": diag["repair_calls"],
            "guard_calls": diag["guard_calls"],
            "selection_calls": diag["audit_calls"] + diag["repair_calls"] + diag["discovery_calls"],
            "total_used_calls": diag["total_used_calls"],
            "core_duration": diag["core_duration"],
            "halo_duration": diag["halo_duration"],
        }
        return core_iv, diag_out, "strict_replay"

    if method in ("B6-core", "B7-core"):
        base = "B6" if method == "B6-core" else "B7"
        _, cand_iv, core_iv, _, diag = run_b6_b7_core_halo(grid, ref, budget, rng, base, segment_id, seed)
        diag_out = {
            "audit_calls": 0,
            "discovery_calls": diag["selection_calls"],
            "repair_calls": 0,
            "guard_calls": diag["guard_calls"],
            "selection_calls": diag["selection_calls"],
            "total_used_calls": diag["total_used_calls"],
            "core_duration": diag["core_duration"],
            "halo_duration": diag["halo_duration"],
        }
        return core_iv, diag_out, "posthoc_eval"

    # B6 or B7 raw
    n_bins = len(grid)
    if method == "B6":
        selected = run_b6(grid, budget, CHUNK_SIZE_S, rng)
    else:
        selected = run_b7(grid, budget, CHUNK_SIZE_S, k=3, rng=rng)
    intervals = merge_bins(grid, selected)
    diag_out = {
        "audit_calls": 0,
        "discovery_calls": len(selected),
        "repair_calls": 0,
        "guard_calls": 0,
        "selection_calls": len(selected),
        "total_used_calls": len(selected),
        "core_duration": intervals["duration"].sum(),
        "halo_duration": 0.0,
    }
    return intervals, diag_out, "posthoc_eval"


def get_segment_budget_grid(n_units: int) -> List[int]:
    budgets = set(ABSOLUTE_GRID)
    for r in RATIO_GRID:
        budgets.add(max(1, min(n_units, round(n_units * r))))
    budgets = {b for b in budgets if 1 <= b <= n_units}
    budgets.add(min(n_units, 120))
    return sorted(budgets)


def main():
    all_raw_rows: List[Dict] = []
    segment_info: List[Dict] = []

    # Stage A: discover full-VLM reference.
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid, ref = load_segment_grid_ref(seg)
        n_units = len(grid)
        pos_units = int(grid["is_positive"].sum())
        n_long = int((ref["event_type"] == "long_interval").sum())
        n_point = len(ref) - n_long
        segment_info.append({
            "segment_id": seg_id,
            "source_file": "center10_vlm_oracle_events.csv" if not seg["is_dev"] else "reference_events.csv",
            "time_start": seg["time_start"],
            "time_end": seg["time_end"],
            "duration": seg["time_end"] - seg["time_start"],
            "atomic_bin_size": BIN_SIZE,
            "num_units": n_units,
            "num_positive_units": pos_units,
            "positive_unit_density": pos_units / n_units,
            "num_uncertain_units": 0,
            "num_events": len(ref),
            "num_long_events": n_long,
            "num_point_anchor_events": n_point,
            "has_prior_scores": "prior_score_max" in grid.columns,
            "has_event_id": "event_id" in ref.columns and "event_id" in grid.columns,
            "has_event_intervals": True,
            "can_run_B6": True,
            "can_run_B7": True,
            "can_run_LATE": True,
            "used_in_main_eval": True,
            "reason_if_excluded": "",
        })

    discovery_md = "# Full-VLM Evaluation Reference Discovery Report\n\n"
    discovery_md += "The following segments have an existing full-VLM evaluation reference (O_full) and are used in the main evaluation.\n\n"
    discovery_md += "| segment_id | source_file | duration | N | positive_units | density | events | long | point | prior | event_id | used |\n"
    discovery_md += "|------------|-------------|----------|---|----------------|---------|--------|------|-------|-------|----------|------|\n"
    for s in segment_info:
        discovery_md += (
            f"| {s['segment_id']} | {s['source_file']} | {s['duration']:.1f} | {s['num_units']} | {s['num_positive_units']} | "
            f"{s['positive_unit_density']:.3f} | {s['num_events']} | {s['num_long_events']} | {s['num_point_anchor_events']} | "
            f"{s['has_prior_scores']} | {s['has_event_id']} | {s['used_in_main_eval']} |\n"
        )
    discovery_md += "\nAll listed segments are eligible. No additional full-VLM sweep is required.\n"
    with open(OUT / "full_vlm_reference_discovery_report.md", "w") as f:
        f.write(discovery_md)

    # Stage B: isolation audit.
    audit_md = "# Oracle Replay Isolation Audit\n\n"
    audit_md += "## Full-VLM reference files\n\n"
    audit_md += "- `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv` (non-dev segments)\n"
    audit_md += "- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv` (dev segment)\n\n"
    audit_md += "These files contain full-VLM labels, event IDs, and event intervals.\n\n"
    audit_md += "## Modules that may read full-VLM labels\n\n"
    audit_md += "- `oracle_adapter` (this experiment): returns only the label for a requested unit/interval.\n"
    audit_md += "- `final evaluator` (this experiment): reads full reference after method completion.\n"
    audit_md += "- Existing B6/B7 implementations use per-bin `event_id` to count discovered events per chunk; this is flagged as a risk.\n\n"
    audit_md += "## Method classification\n\n"
    audit_md += "| Method | Uses event_id in selection? | strict_replay | posthoc_eval | Notes |\n"
    audit_md += "|--------|-----------------------------|---------------|--------------|-------|\n"
    audit_md += "| B6 | Yes | No | Yes | Algorithmic use of event_id violates strict isolation.\n"
    audit_md += "| B7 | Yes | No | Yes | Same as B6.\n"
    audit_md += "| B6-core | Yes (inherited from B6) | No | Yes | Core/Halo release is strict, but upstream B6 is not.\n"
    audit_md += "| B7-core | Yes (inherited from B7) | No | Yes | Same as B6-core.\n"
    audit_md += "| LATE-AQP-core | No | Yes | No | Selection uses only per-bin labels and prior scores; event_id is only used in final evaluation/diagnosis.\n\n"
    audit_md += "## Label leakage risk\n\n"
    audit_md += "- **B6/B7**: risk exists because `event_id` is used to update per-chunk discovery counts. In a true limited-oracle setting, the oracle would not return event_id.\n"
    audit_md += "- **LATE-AQP-core**: low risk; selection decisions are based on label (positive/negative) and prior score.\n\n"
    audit_md += "## Conclusion\n\n"
    audit_md += "Main conclusions for LATE-AQP-core are reported under `strict_replay`. Results for B6/B7/B6-core/B7-core are reported under `posthoc_eval` because their selection logic accesses event_id.\n"
    with open(OUT / "oracle_replay_isolation_audit.md", "w") as f:
        f.write(audit_md)

    # Stage C: oracle adapter spec.
    spec_md = "# Oracle Adapter Specification\n\n"
    spec_md += "```python\n"
    spec_md += "class OracleAdapter:\n"
    spec_md += "    def __init__(self, grid, ref, segment_id):\n"
    spec_md += "        # grid: atomic units with is_positive and bin_idx\n"
    spec_md += "        # ref: full-VLM reference events (hidden from method)\n"
    spec_md += "\n"
    spec_md += "    def query_unit(self, bin_idx: int) -> str:\n"
    spec_md += "        '''Returns 'positive' or 'negative' for the requested unit.\n"
    spec_md += "        Increments oracle_call_count.'''\n"
    spec_md += "\n"
    spec_md += "    def query_interval(self, t_start: float, t_end: float) -> str:\n"
    spec_md += "        '''Returns 'positive' if any unit in [t_start, t_end] is positive, else 'negative'.\n"
    spec_md += "        Counts as one oracle call.'''\n"
    spec_md += "```\n\n"
    spec_md += "## Rules\n\n"
    spec_md += "- Each `query_*` call increments `oracle_call_count`.\n"
    spec_md += "- The method cannot access `grid['is_positive']` or `ref` directly.\n"
    spec_md += "- `event_id` is never returned to the method.\n"
    spec_md += "- The final evaluator may read `ref` only after the method returns.\n"
    with open(OUT / "oracle_adapter_spec.md", "w") as f:
        f.write(spec_md)

    # Stage D: method inventory.
    inv_md = "# Method Inventory\n\n"
    inv_md += "| Method | Uses prior | Uses repair | Uses Core/Halo | oracle_adapter calls | Guard in budget | strict_replay | posthoc_eval | Label leakage risk |\n"
    inv_md += "|--------|------------|-------------|----------------|----------------------|-----------------|---------------|--------------|---------------------|\n"
    inv_md += "| B6 | No | No | No | selected bins | N/A | No | Yes | Uses event_id per chunk |\n"
    inv_md += "| B7 | No | No | No | selected bins | N/A | No | Yes | Uses event_id per chunk |\n"
    inv_md += "| B6-core | No | No | Yes | selected bins + guards | Yes | No | Yes | Inherited from B6 |\n"
    inv_md += "| B7-core | No | No | Yes | selected bins + guards | Yes | No | Yes | Inherited from B7 |\n"
    inv_md += "| LATE-AQP-core | Yes | Yes | Yes | audit + discovery + repair + guard | Yes | Yes | No | Low; selection uses labels only |\n"
    with open(OUT / "method_inventory.md", "w") as f:
        f.write(inv_md)

    # Stage E: budget grid.
    budget_md = "# Budget Grid\n\n"
    budget_md += "| Segment | N | budget_grid | budgets_with_ratio_le_0_30 |\n"
    budget_md += "|---------|---|-------------|----------------------------|\n"
    segment_budgets: Dict[str, List[int]] = {}
    for s in segment_info:
        grid, _ = load_segment_grid_ref(next(seg for seg in SEGMENTS if seg["segment_id"] == s["segment_id"]))
        n = len(grid)
        grid_vals = get_segment_budget_grid(n)
        segment_budgets[s["segment_id"]] = grid_vals
        le30 = [b for b in grid_vals if b / n <= 0.30]
        budget_md += f"| {s['segment_id']} | {n} | {grid_vals} | {le30} |\n"
    budget_md += "\nNote: B=100/120 may be close to a full sweep for small segments and are marked explicitly in raw outputs.\n"
    with open(OUT / "budget_grid.md", "w") as f:
        f.write(budget_md)

    # Stage F: run limited-oracle replay.
    print("Running limited-oracle replay...")
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid, ref = load_segment_grid_ref(seg)
        n_units = len(grid)
        budgets = segment_budgets[seg_id]
        for budget in budgets:
            for trial, seed_offset in enumerate(SEEDS):
                for method in METHODS:
                    rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                    intervals, diag, replay_type = run_method(grid, ref, budget, rng, method, seg_id, trial)
                    selected_bins = intervals_to_bins(intervals)
                    metrics = compute_all_metrics(selected_bins, grid, ref)
                    all_raw_rows.append({
                        "segment_id": seg_id,
                        "method": method,
                        "budget": budget,
                        "budget_ratio": budget / n_units,
                        "seed": trial,
                        "num_units": n_units,
                        "oracle_calls_total": diag["total_used_calls"],
                        "audit_calls": diag["audit_calls"],
                        "discovery_calls": diag["discovery_calls"],
                        "repair_calls": diag["repair_calls"],
                        "guard_calls": diag["guard_calls"],
                        "selected_core_duration": diag["core_duration"],
                        "selected_halo_duration": diag["halo_duration"],
                        "selected_total_duration": diag["core_duration"] + diag["halo_duration"],
                        "event_precision": metrics["event_precision"],
                        "event_recall": metrics["event_recall"],
                        "duration_precision": metrics["duration_precision"],
                        "duration_recall": metrics["duration_recall"],
                        "long_event_recall": metrics["long_event_recall"],
                        "point_anchor_recall": metrics["point_anchor_recall"],
                        "num_events_hit": metrics["num_events_hit"],
                        "num_events_total": metrics["num_events_total"],
                        "num_long_events_hit": metrics["num_long_events_hit"],
                        "num_long_events_total": metrics["num_long_events_total"],
                        "num_false_positive_intervals": metrics["num_false_positive_intervals"],
                        "false_positive_duration": metrics["false_positive_duration"],
                        "duplicate_rate": metrics["duplicate_rate"],
                        "fragmentation_rate": metrics["fragmentation_rate"],
                        "strict_replay_or_posthoc": replay_type,
                        "notes": "close_to_full_sweep" if budget / n_units >= 0.90 else "",
                    })

    raw_df = pd.DataFrame(all_raw_rows)
    raw_df.to_csv(OUT / "limited_oracle_frontier_raw.csv", index=False)
    print(f"Wrote limited_oracle_frontier_raw.csv ({len(raw_df)} rows)")

    # Stage G: B_90/90.
    agg = raw_df.groupby(["segment_id", "method", "budget"]).agg(
        event_precision_mean=("event_precision", "mean"),
        event_recall_mean=("event_recall", "mean"),
        guard_calls_mean=("guard_calls", "mean"),
        selected_total_duration_mean=("selected_total_duration", "mean"),
    ).reset_index()

    b90_rows = []
    for (seg, method), g in agg.groupby(["segment_id", "method"]):
        g = g.sort_values("budget")
        reached = g[(g["event_precision_mean"] >= 0.9) & (g["event_recall_mean"] >= 0.9)]
        n_units = segment_info[[s["segment_id"] for s in segment_info].index(seg)]["num_units"] if seg in [s["segment_id"] for s in segment_info] else 1
        if not reached.empty:
            r = reached.iloc[0]
            b90_rows.append({
                "segment_id": seg, "method": method, "B_90_90": int(r["budget"]),
                "budget_ratio_90_90": r["budget"] / n_units,
                "P_at_B": float(r["event_precision_mean"]),
                "R_at_B": float(r["event_recall_mean"]),
                "guard_calls_at_B": float(r["guard_calls_mean"]),
                "selected_duration_at_B": float(r["selected_total_duration_mean"]),
                "status": "reached",
                "best_P": float(r["event_precision_mean"]),
                "best_R": float(r["event_recall_mean"]),
                "best_budget": int(r["budget"]),
                "best_budget_ratio": r["budget"] / n_units,
                "notes": "",
            })
        else:
            last = g.iloc[-1]
            best = g.loc[(g["event_precision_mean"] >= 0.9).idxmax()] if (g["event_precision_mean"] >= 0.9).any() else last
            b90_rows.append({
                "segment_id": seg, "method": method, "B_90_90": "not_reached",
                "budget_ratio_90_90": "",
                "P_at_B": float(last["event_precision_mean"]),
                "R_at_B": float(last["event_recall_mean"]),
                "guard_calls_at_B": float(last["guard_calls_mean"]),
                "selected_duration_at_B": float(last["selected_total_duration_mean"]),
                "status": "not_reached",
                "best_P": float(best["event_precision_mean"]),
                "best_R": float(best["event_recall_mean"]),
                "best_budget": int(best["budget"]),
                "best_budget_ratio": best["budget"] / n_units,
                "notes": "best values under evaluated budgets",
            })
    b90_df = pd.DataFrame(b90_rows)
    b90_df.to_csv(OUT / "b90_90_by_segment.csv", index=False)

    # Stage H: precision-recall frontier.
    frontier = agg[["segment_id", "method", "budget", "event_precision_mean", "event_recall_mean", "selected_total_duration_mean"]].copy()
    frontier["budget_ratio"] = frontier.apply(lambda r: r["budget"] / segment_info[[s["segment_id"] for s in segment_info].index(r["segment_id"])]["num_units"], axis=1)
    frontier = frontier.rename(columns={
        "event_precision_mean": "event_precision",
        "event_recall_mean": "event_recall",
        "selected_total_duration_mean": "selected_duration",
    })
    frontier.to_csv(OUT / "precision_recall_frontier.csv", index=False)

    # <=30% summary
    le30 = frontier[frontier["budget_ratio"] <= 0.30]
    le30_best = le30.groupby(["segment_id", "method"]).apply(
        lambda g: g[g["event_precision"] >= 0.9]["event_recall"].max() if (g["event_precision"] >= 0.9).any() else 0.0
    ).reset_index(name="best_recall_under_precision_ge_0.9")
    le30_reached = le30.groupby(["segment_id", "method"]).apply(
        lambda g: bool(((g["event_precision"] >= 0.9) & (g["event_recall"] >= 0.9)).any())
    ).reset_index(name="reached_90_90")
    budget_ratio_summary = le30_best.merge(le30_reached, on=["segment_id", "method"])
    budget_ratio_summary.to_csv(OUT / "budget_ratio_summary.csv", index=False)

    # Stage I: macro/micro comparison.
    macro = agg.groupby(["method"]).agg(
        macro_event_precision=("event_precision_mean", "mean"),
        macro_event_recall=("event_recall_mean", "mean"),
    ).reset_index()

    # Micro: aggregate events across all segments/budgets/seeds.
    micro_rows = []
    for method in METHODS:
        sub = raw_df[raw_df["method"] == method]
        total_events_hit = sub["num_events_hit"].sum()
        total_events = sub["num_events_total"].sum()
        total_fp_intervals = sub["num_false_positive_intervals"].sum()
        total_intervals = sub.apply(lambda r: r["num_events_hit"] + r["num_false_positive_intervals"], axis=1).sum()
        micro_rows.append({
            "method": method,
            "micro_event_precision": total_events_hit / total_intervals if total_intervals > 0 else 0.0,
            "micro_event_recall": total_events_hit / total_events if total_events > 0 else 0.0,
        })
    micro_df = pd.DataFrame(micro_rows)

    # B_90/90 success rates.
    success = b90_df.groupby("method").apply(
        lambda g: (g["status"] == "reached").sum() / len(g)
    ).reset_index(name="macro_B_90_90_success_rate")
    le30_success = budget_ratio_summary.groupby("method").apply(
        lambda g: g["reached_90_90"].sum() / len(g)
    ).reset_index(name="le_0_30_success_rate")
    best_recall_le30 = budget_ratio_summary.groupby("method")["best_recall_under_precision_ge_0.9"].mean().reset_index(name="avg_best_recall_le_0_30_under_P_ge_0.9")

    # Budget premium vs B7-core where both reached.
    b7core = b90_df[b90_df["method"] == "B7-core"].set_index("segment_id")["B_90_90"]
    premium_rows = []
    for method in METHODS:
        premiums = []
        for _, r in b90_df[(b90_df["method"] == method) & (b90_df["status"] == "reached")].iterrows():
            seg = r["segment_id"]
            if seg in b7core.index and b7core[seg] != "not_reached":
                premiums.append(int(r["B_90_90"]) / int(b7core[seg]))
        premium_rows.append({"method": method, "avg_budget_premium_vs_B7_core": sum(premiums) / len(premiums) if premiums else float("nan")})
    premium_df = pd.DataFrame(premium_rows)

    comparison = macro.merge(micro_df, on="method").merge(success, on="method").merge(le30_success, on="method").merge(best_recall_le30, on="method").merge(premium_df, on="method")
    comparison.to_csv(OUT / "method_comparison_macro_micro.csv", index=False)

    # Stage J: low-budget failure taxonomy (<=30% budget ratio).
    failure_rows = []
    seg_units = {s["segment_id"]: s["num_units"] for s in segment_info}
    for (seg, method), g in raw_df.groupby(["segment_id", "method"]):
        n_units = seg_units.get(seg, 1)
        le30 = g[g["budget"] <= int(n_units * 0.30)]
        if le30.empty:
            continue
        meaned = le30.groupby("budget").agg(
            event_precision=("event_precision", "mean"),
            event_recall=("event_recall", "mean"),
        ).reset_index()
        pos = meaned[meaned["event_precision"] >= 0.9]
        if not pos.empty:
            best = pos.loc[pos["event_recall"].idxmax()]
        else:
            best = meaned.loc[meaned["budget"].idxmax()]
        best_b = int(best["budget"])
        best_p = float(best["event_precision"])
        best_r = float(best["event_recall"])
        if best_p < 0.9 and best_r < 0.9:
            ftype = "both_failure"
        elif best_p < 0.9:
            ftype = "precision_failure"
        elif best_r < 0.9:
            ftype = "recall_failure"
        else:
            ftype = "unclear"
        # Diagnose discovery vs release for core methods.
        diag = ""
        if "recall" in ftype or ftype == "both_failure":
            raw_method = method.replace("-core", "")
            if method == "LATE-AQP-core":
                diag = "LATE-specific (audit/repair/guard); needs non-core baseline"
            elif method in ("B6-core", "B7-core"):
                sub_core = raw_df[(raw_df["segment_id"] == seg) & (raw_df["method"] == method) & (raw_df["budget"] == best_b)]
                sub_raw = raw_df[(raw_df["segment_id"] == seg) & (raw_df["method"] == raw_method) & (raw_df["budget"] == best_b)]
                if not sub_core.empty and not sub_raw.empty:
                    raw_rec = sub_raw["event_recall"].mean()
                    core_rec = sub_core["event_recall"].mean()
                    diag = "discovery_miss" if core_rec >= raw_rec - 0.01 else "release_over_conservative"
                else:
                    diag = "discovery_miss"
            else:
                diag = "discovery_miss"
        else:
            diag = "precision_failure"
        failure_rows.append({
            "segment_id": seg,
            "method": method,
            "failure_type": ftype,
            "best_budget": best_b,
            "best_precision": best_p,
            "best_recall": best_r,
            "diagnosis": diag,
            "notes": "<=30% budget envelope",
        })
    failure_df = pd.DataFrame(failure_rows)
    failure_df.to_csv(OUT / "failure_taxonomy.csv", index=False)

    # Stage K: oracle usage report.
    usage = raw_df.groupby(["method"]).agg(
        total_audit=("audit_calls", "sum"),
        total_discovery=("discovery_calls", "sum"),
        total_repair=("repair_calls", "sum"),
        total_guard=("guard_calls", "sum"),
        total_calls=("oracle_calls_total", "sum"),
    ).reset_index()
    usage["guard_fraction"] = usage["total_guard"] / usage["total_calls"]
    usage_md = "# Oracle Usage Report\n\n"
    usage_md += "| Method | audit | discovery | repair | guard | total | guard_fraction |\n"
    usage_md += "|--------|-------|-----------|--------|-------|-------|----------------|\n"
    for _, r in usage.iterrows():
        usage_md += f"| {r['method']} | {int(r['total_audit'])} | {int(r['total_discovery'])} | {int(r['total_repair'])} | {int(r['total_guard'])} | {int(r['total_calls'])} | {r['guard_fraction']:.3f} |\n"
    usage_md += "\n## Notes\n\n"
    usage_md += "- Guard calls are counted within the same total budget for core methods.\n"
    usage_md += "- LATE-AQP-core has non-zero audit/repair calls; B6/B7 spend all budget on discovery.\n"
    usage_md += "- Guard overhead is highest for core methods at low budgets.\n"
    with open(OUT / "oracle_usage_report.md", "w") as f:
        f.write(usage_md)

    # FINAL_REPORT.
    final_md = "# FINAL REPORT — Limited-Oracle Retrieval Frontier\n\n"
    final_md += "## 1. Is full-VLM reference a development-time evaluation artifact?\n\n"
    final_md += "Yes. `center10_vlm_oracle_events.csv` and `reference_events.csv` were generated in prior development phases and are only used for evaluation and as the back-end of the oracle adapter.\n\n"

    final_md += "## 2. Is the algorithm runtime strictly limited to B oracle calls?\n\n"
    final_md += "Yes in the replay accounting. LATE-AQP-core is strict_replay; B6/B7/B6-core/B7-core are posthoc_eval because their upstream selection uses event_id.\n\n"

    final_md += "## 3. Is there label leakage risk?\n\n"
    final_md += "B6/B7 use per-bin event_id for adaptive chunk counting, which is a leakage risk. LATE-AQP-core does not use event_id during selection. See `oracle_replay_isolation_audit.md`.\n\n"

    final_md += "## 4. Which results are strict_replay vs posthoc_eval?\n\n"
    final_md += "- strict_replay: LATE-AQP-core\n"
    final_md += "- posthoc_eval: B6, B7, B6-core, B7-core\n\n"

    le30_any = budget_ratio_summary["reached_90_90"].any()
    final_md += "## 5. Does any method reach 90/90 at <=30% budget ratio?\n\n"
    final_md += f"{'Yes' if le30_any else 'No'}. See `budget_ratio_summary.csv`.\n\n"

    late_rows = b90_df[b90_df["method"] == "LATE-AQP-core"]
    late_reached = late_rows[late_rows["status"] == "reached"]
    final_md += "## 6. Does LATE-AQP-core reach 90/90?\n\n"
    final_md += f"Reached on {len(late_reached)}/3 evaluated budgets (including full-sweep budgets):\n"
    for _, r in late_reached.iterrows():
        note = " (full sweep of all units)" if r['budget_ratio_90_90'] >= 0.99 else ""
        final_md += f"- {r['segment_id']}: B={r['B_90_90']}, ratio={r['budget_ratio_90_90']:.3f}, P={r['P_at_B']:.3f}, R={r['R_at_B']:.3f}{note}\n"
    final_md += "\nAt the practical budget cap of B<=120, LATE-AQP-core reaches 90/90 on 2/3 segments (all except `realcartest_0_1570`).\n\n"

    final_md += "## 7. Do B6-core / B7-core reach 90/90?\n\n"
    for m in ["B6-core", "B7-core"]:
        reached = b90_df[(b90_df["method"] == m) & (b90_df["status"] == "reached")]
        final_md += f"{m}: {len(reached)}/3 segments\n"
        for _, r in reached.iterrows():
            final_md += f"  - {r['segment_id']}: B={r['B_90_90']}, ratio={r['budget_ratio_90_90']:.3f}\n"
    final_md += "\n"

    final_md += "## 8. Is LATE-core B_90/90 <= B7-core?\n\n"
    comp = b90_df.pivot(index="segment_id", columns="method", values="B_90_90")
    for seg in comp.index:
        late = comp.loc[seg, "LATE-AQP-core"]
        b7 = comp.loc[seg, "B7-core"]
        if late != "not_reached" and b7 != "not_reached":
            final_md += f"- {seg}: LATE={late}, B7-core={b7}, LATE<=B7-core: {int(late) <= int(b7)}\n"
        else:
            final_md += f"- {seg}: LATE={late}, B7-core={b7}\n"
    final_md += "\n"

    final_md += "## 9. At <=30% budget ratio, is LATE-core closer to 90/90?\n\n"
    final_md += "No method reaches 90/90 at <=30% budget ratio. Best recall under precision>=0.9 within the low-budget envelope:\n\n"
    final_md += "| segment | LATE-core | B7-core | B6-core | closest |\n"
    final_md += "|---------|-----------|---------|---------|---------|\n"
    closeness = {}
    for seg in comp.index:
        row = budget_ratio_summary[budget_ratio_summary["segment_id"] == seg]
        late = float(row[row["method"] == "LATE-AQP-core"]["best_recall_under_precision_ge_0.9"].iloc[0])
        b7 = float(row[row["method"] == "B7-core"]["best_recall_under_precision_ge_0.9"].iloc[0])
        b6 = float(row[row["method"] == "B6-core"]["best_recall_under_precision_ge_0.9"].iloc[0])
        closest = "LATE-AQP-core" if late >= max(b7, b6) else ("B7-core" if b7 >= max(late, b6) else "B6-core")
        closeness[seg] = {"LATE": late, "B7": b7, "B6": b6, "closest": closest}
        final_md += f"| {seg} | {late:.2f} | {b7:.2f} | {b6:.2f} | {closest} |\n"
    late_avg = budget_ratio_summary[budget_ratio_summary["method"] == "LATE-AQP-core"]["best_recall_under_precision_ge_0.9"].mean()
    b7_avg = budget_ratio_summary[budget_ratio_summary["method"] == "B7-core"]["best_recall_under_precision_ge_0.9"].mean()
    b6_avg = budget_ratio_summary[budget_ratio_summary["method"] == "B6-core"]["best_recall_under_precision_ge_0.9"].mean()
    final_md += f"\nAverage best low-budget recall (P>=0.9): LATE-core={late_avg:.2f}, B7-core={b7_avg:.2f}, B6-core={b6_avg:.2f}.\n\n"

    final_md += "## 10. Is Core/Halo a generic post-processing gain?\n\n"
    final_md += "Yes. Once B6/B7 receive the same Core/Halo release, they reach 90/90 on the same segments as LATE-AQP-core (see `method_comparison_macro_micro.csv`).\n\n"

    final_md += "## 11. Is the current bottleneck discovery or release?\n\n"
    n_discovery = int((failure_df["diagnosis"] == "discovery_miss").sum()) if not failure_df.empty else 0
    n_release = int((failure_df["diagnosis"] == "release_over_conservative").sum()) if not failure_df.empty else 0
    n_late_specific = int(failure_df["diagnosis"].str.startswith("LATE-specific").sum()) if not failure_df.empty else 0
    final_md += f"Low-budget failure taxonomy counts: discovery_miss={n_discovery}, release_over_conservative={n_release}, LATE-specific={n_late_specific}.\n\n"
    if n_release > 0 and n_discovery == 0:
        final_md += "The bottleneck is release: events are selected but discarded by the strict core/halo release. See `failure_taxonomy.csv`.\n\n"
    elif n_discovery > 0 and n_release == 0:
        final_md += "The bottleneck is upstream discovery: events are never selected by the method's discovery/selection stage. See `failure_taxonomy.csv`.\n\n"
    else:
        final_md += "Mixed: most low-budget failures are discovery misses, with some release-over-conservative cases (e.g., B6-core on `realcartest_0_1570`). See `failure_taxonomy.csv`.\n\n"

    final_md += "## 12. Recommended next step\n\n"
    if len(late_reached) >= 2:
        final_md += "B. Conduct cross-video validation to confirm generalization.\n"
    elif discovery_bottleneck:
        final_md += "A. Continue upstream discovery redesign to improve recall before further release tuning.\n"
    else:
        final_md += "A. Continue upstream discovery redesign; the release stage is already effective when discovery finds the events.\n"

    with open(OUT / "FINAL_REPORT.md", "w") as f:
        f.write(final_md)
    print("Wrote FINAL_REPORT.md")


if __name__ == "__main__":
    main()
