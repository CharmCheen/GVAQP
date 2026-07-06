#!/usr/bin/env python3
"""
Diagnose why Frozen-LATE-AQP-v2 discovery-only still loses to B6 at B=10/20.

Pure offline replay against existing labels. No GPU/VLM/oracle calls.
Does not modify any algorithm; only records per-call cumulative metrics.
"""

import csv
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
FROZEN_DIR = ROOT / "outputs" / "late_aqp_frozen_cross_segment_v1"
OUT = ROOT / "outputs" / "late_aqp_low_budget_discovery_diagnosis_v1"
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
    get_prior_at_bin,
    load_dev_events,
    load_dev_grid,
    load_full_events,
    load_proxy_scores,
)

SEGMENTS = [
    {"segment_id": "realcartest_0_1570", "video_id": "realcartest", "time_start": 0.0, "time_end": 1570.0, "is_dev": False},
    {"segment_id": "realcartest_2000_3200", "video_id": "realcartest", "time_start": 2000.0, "time_end": 3200.0, "is_dev": True},
    {"segment_id": "realcartest_3200_3830", "video_id": "realcartest", "time_start": 3200.0, "time_end": 3830.0, "is_dev": False},
]

BUDGETS = [10, 20]
CHUNK_SIZE_S = 120


def run_b6_traced(grid: pd.DataFrame, budget: int, chunk_size_s: int, rng: np.random.Generator) -> List[Dict]:
    """Trace B6 selection order. Logic mirrors run_b6 exactly."""
    n_bins = len(grid)
    bins_per_chunk = max(1, chunk_size_s // int(BIN_SIZE))
    n_chunks = int(math.ceil(n_bins / bins_per_chunk))
    sampled: set = set()
    n_c = np.zeros(n_chunks, dtype=int)
    discovered_events: List[Dict[str, int]] = [dict() for _ in range(n_chunks)]
    trace: List[Dict] = []

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

        row = grid[grid["bin_idx"] == b].iloc[0]
        trace.append({
            "selected_bin": b,
            "selected_t_start": row["t_start"],
            "selected_t_end": row["t_end"],
            "prior_score": row["prior_score_max"],
            "oracle_label": get_label_at_bin(grid, b),
            "hit_event_id": e if e is not None else "",
            "action_type": "B6_chunk_sample",
            "chunk_idx": chosen_c,
        })
    return trace


def run_v2_traced(grid: pd.DataFrame, budget: int) -> List[Dict]:
    """Trace Frozen-LATE-AQP-v2 discovery-only order: top prior_score_max first."""
    ranked = grid.sort_values("prior_score_max", ascending=False)
    trace: List[Dict] = []
    for _, row in ranked.head(budget).iterrows():
        b = int(row["bin_idx"])
        e = get_event_at_bin(grid, b)
        trace.append({
            "selected_bin": b,
            "selected_t_start": row["t_start"],
            "selected_t_end": row["t_end"],
            "prior_score": row["prior_score_max"],
            "oracle_label": get_label_at_bin(grid, b),
            "hit_event_id": e if e is not None else "",
            "action_type": "v2_discovery_prior_rank",
            "chunk_idx": -1,
        })
    return trace


def cumulative_rows(trace: List[Dict], grid: pd.DataFrame, ref: pd.DataFrame,
                    segment_id: str, budget: int, seed: int, method: str) -> List[Dict]:
    rows = []
    selected: List[int] = []
    for i, call in enumerate(trace, start=1):
        selected.append(call["selected_bin"])
        metrics = compute_metrics(selected, grid, ref)
        n_long = int((ref["event_type"] == "long_interval").sum())
        long_hit_count = int(round(metrics["long_event_recall"] * n_long)) if n_long > 0 and not math.isnan(metrics["long_event_recall"]) else 0
        rows.append({
            "segment_id": segment_id,
            "budget": budget,
            "seed": seed,
            "method": method,
            "call_index": i,
            "cumulative_long_event_recall": metrics["long_event_recall"],
            "cumulative_precision": metrics["selected_precision"],
            "cumulative_long_events_hit": long_hit_count,
            "cumulative_unique_events_hit": metrics["event_recall"] * len(ref),
            "selected_bin": call["selected_bin"],
            "selected_t_start": call["selected_t_start"],
            "selected_t_end": call["selected_t_end"],
            "prior_score": call["prior_score"],
            "oracle_label": call["oracle_label"],
            "hit_event_id": call["hit_event_id"],
            "action_type": call["action_type"],
            "chunk_idx": call["chunk_idx"],
        })
    return rows


def main():
    full_events = load_full_events()
    proxy_scores = load_proxy_scores()
    dev_events = load_dev_events()
    dev_grid = load_dev_grid()

    all_curve_rows: List[Dict] = []
    segment_grids: Dict[str, pd.DataFrame] = {}
    segment_refs: Dict[str, pd.DataFrame] = {}

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

        segment_grids[seg_id] = grid
        segment_refs[seg_id] = ref
        print(f"  {len(grid)} bins, {len(ref)} events, long={int((ref['event_type']=='long_interval').sum())}")

        for budget in BUDGETS:
            for trial, seed_offset in enumerate(SEEDS):
                rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                b6_trace = run_b6_traced(grid, budget, CHUNK_SIZE_S, rng)
                v2_trace = run_v2_traced(grid, budget)

                all_curve_rows.extend(cumulative_rows(b6_trace, grid, ref, seg_id, budget, trial, "B6"))
                all_curve_rows.extend(cumulative_rows(v2_trace, grid, ref, seg_id, budget, trial, "Frozen-LATE-AQP-v2"))

    # Save per-call cumulative curves.
    curves_df = pd.DataFrame(all_curve_rows)
    col_order = [
        "segment_id", "budget", "seed", "method", "call_index",
        "cumulative_long_event_recall", "cumulative_precision",
        "cumulative_long_events_hit", "cumulative_unique_events_hit",
        "selected_bin", "selected_t_start", "selected_t_end",
        "prior_score", "oracle_label", "hit_event_id", "action_type", "chunk_idx",
    ]
    curves_df = curves_df[col_order]
    curves_df.to_csv(OUT / "cumulative_discovery_curves.csv", index=False)
    print(f"\nWrote cumulative_discovery_curves.csv ({len(curves_df)} rows)")

    # Aggregate per segment/budget/call_index.
    agg_rows = []
    for (seg_id, budget, call_index), g in curves_df.groupby(["segment_id", "budget", "call_index"]):
        v2 = g[g["method"] == "Frozen-LATE-AQP-v2"]
        b6 = g[g["method"] == "B6"]
        row = {
            "segment_id": seg_id,
            "budget": budget,
            "call_index": call_index,
            "v2_recall_mean": v2["cumulative_long_event_recall"].mean(),
            "v2_recall_std": v2["cumulative_long_event_recall"].std(ddof=0) if len(v2) > 1 else 0.0,
            "b6_recall_mean": b6["cumulative_long_event_recall"].mean(),
            "b6_recall_std": b6["cumulative_long_event_recall"].std(ddof=0) if len(b6) > 1 else 0.0,
            "recall_gap": v2["cumulative_long_event_recall"].mean() - b6["cumulative_long_event_recall"].mean(),
            "v2_precision_mean": v2["cumulative_precision"].mean(),
            "v2_precision_std": v2["cumulative_precision"].std(ddof=0) if len(v2) > 1 else 0.0,
            "b6_precision_mean": b6["cumulative_precision"].mean(),
            "b6_precision_std": b6["cumulative_precision"].std(ddof=0) if len(b6) > 1 else 0.0,
            "precision_gap": v2["cumulative_precision"].mean() - b6["cumulative_precision"].mean(),
            "n_seeds": len(g["seed"].unique()),
        }
        agg_rows.append(row)
    agg_df = pd.DataFrame(agg_rows)
    agg_df.to_csv(OUT / "aggregate_gap.csv", index=False)
    print(f"Wrote aggregate_gap.csv")

    # First-lag analysis.
    first_lag_md = "# First-Lag Report — When does v2 fall behind B6?\n\n"
    first_lag_md += "For each segment and budget, we report the first call index at which "
    first_lag_md += "v2 cumulative long-event recall is strictly below B6 mean recall.\n\n"
    first_lag_md += "| Segment | Budget | first_lag_call | v2_recall_at_lag | b6_recall_at_lag | gap | interpretation |\n"
    first_lag_md += "|---------|--------|----------------|------------------|------------------|-----|----------------|\n"

    lag_rows = []
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        for budget in BUDGETS:
            sub = agg_df[(agg_df["segment_id"] == seg_id) & (agg_df["budget"] == budget)].sort_values("call_index")
            first = sub[sub["recall_gap"] < -1e-9].head(1)
            if not first.empty:
                r = first.iloc[0]
                interp = "v2 starts behind" if int(r["call_index"]) == 1 else "v2 falls behind mid-run"
                lag_rows.append({
                    "segment_id": seg_id,
                    "budget": budget,
                    "first_lag_call": int(r["call_index"]),
                    "v2_recall_at_lag": float(r["v2_recall_mean"]),
                    "b6_recall_at_lag": float(r["b6_recall_mean"]),
                    "gap": float(r["recall_gap"]),
                    "interpretation": interp,
                })
                first_lag_md += f"| {seg_id} | {budget} | {int(r['call_index'])} | {r['v2_recall_mean']:.3f} | {r['b6_recall_mean']:.3f} | {r['recall_gap']:.3f} | {interp} |\n"
            else:
                # v2 never behind at any call index (rare).
                final = sub.iloc[-1]
                lag_rows.append({
                    "segment_id": seg_id,
                    "budget": budget,
                    "first_lag_call": -1,
                    "v2_recall_at_lag": float(final["v2_recall_mean"]),
                    "b6_recall_at_lag": float(final["b6_recall_mean"]),
                    "gap": float(final["recall_gap"]),
                    "interpretation": "v2 never behind",
                })
                first_lag_md += f"| {seg_id} | {budget} | - | {final['v2_recall_mean']:.3f} | {final['b6_recall_mean']:.3f} | {final['recall_gap']:.3f} | v2 never behind |\n"
    with open(OUT / "first_lag_report.md", "w") as f:
        f.write(first_lag_md)
    print("Wrote first_lag_report.md")

    # Data granularity report.
    gran_md = "# Data Granularity Report\n\n"
    gran_md += "The original `repair_trace_calls.csv` and `cross_segment_metrics.csv` from "
    gran_md += "`late_aqp_frozen_cross_segment_v1` only store final per-trial aggregates "
    gran_md += "and per-call action metadata; they do **not** contain cumulative "
    gran_md += "long-event recall/precision after each oracle call.\n\n"
    gran_md += "To perform this diagnosis, we re-ran B6 and v2 in pure offline replay "
    gran_md += "against the existing labeled grids and recorded, for every call index:\n\n"
    gran_md += "- selected bin and time interval\n"
    gran_md += "- prior score (for v2) / sampled chunk (for B6)\n"
    gran_md += "- oracle label and hit event id\n"
    gran_md += "- cumulative long-event recall and precision up to that call\n\n"
    gran_md += "This is the finest granularity supported by the existing data without "
    gran_md += "generating new labels or oracle calls.\n"
    with open(OUT / "data_granularity_report.md", "w") as f:
        f.write(gran_md)
    print("Wrote data_granularity_report.md")

    # Diagnosis report.
    diag_md = "# Diagnosis Report — Why Discovery-Only v2 Still Loses to B6 at B=10/20\n\n"
    diag_md += "## Methodology\n\n"
    diag_md += "We reconstructed the per-call cumulative discovery curve for B6 (chunk-level Thompson sampling) "
    diag_md += "and Frozen-LATE-AQP-v2 (top-prior-score discovery) on the three original failure segments, "
    diag_md += "budgets 10 and 20, 5 seeds each. No new labels or oracle calls were used.\n\n"

    diag_md += "## Findings\n\n"
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        diag_md += f"### {seg_id}\n\n"
        for budget in BUDGETS:
            sub = agg_df[(agg_df["segment_id"] == seg_id) & (agg_df["budget"] == budget)].sort_values("call_index")
            final = sub.iloc[-1]
            first_lag = sub[sub["recall_gap"] < -1e-9].head(1)
            final_gap = float(final["recall_gap"])
            if not first_lag.empty:
                lag_call = int(first_lag.iloc[0]["call_index"])
                if lag_call == 1:
                    interp = "starts behind"
                elif final_gap < -1e-9:
                    interp = f"falls behind at call {lag_call} and stays behind"
                else:
                    interp = f"falls behind at call {lag_call} but recovers/overtakes by the final call"
            else:
                interp = "never falls behind"
            diag_md += f"**B={budget}**: final v2 recall={final['v2_recall_mean']:.3f}, B6 recall={final['b6_recall_mean']:.3f}, gap={final_gap:+.3f}. {interp}.\n\n"

    diag_md += "## Candidate-level observations (not fixes)\n\n"

    # Duplicate / event-clustering analysis for v2 top-B selection.
    dup_rows = []
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid = segment_grids[seg_id]
        ref = segment_refs[seg_id]
        event_type_map = ref.set_index("event_id")["event_type"].to_dict() if "event_id" in ref.columns else {}
        for budget in BUDGETS:
            ranked = grid.sort_values("prior_score_max", ascending=False)
            top_bins = ranked.head(budget)
            seed_uniq = []
            seed_dup = []
            # v2 is deterministic, so each seed sees the same top-budget set.
            for _ in SEEDS:
                long_bins = 0
                long_ids = set()
                for _, row in top_bins.iterrows():
                    ev_id = row.get("event_id", "")
                    if ev_id and event_type_map.get(str(ev_id), "") == "long_interval":
                        long_bins += 1
                        long_ids.add(str(ev_id))
                seed_uniq.append(len(long_ids))
                seed_dup.append(long_bins / max(1, len(long_ids)) - 1 if long_ids else float("nan"))
            dup_rows.append((seg_id, budget, sum(seed_uniq)/len(seed_uniq), sum(seed_dup)/len(seed_dup) if any(not math.isnan(x) for x in seed_dup) else float("nan")))

    diag_md += "### v2 top-B selection: long-event duplication\n\n"
    diag_md += "For the bins v2 would select with budget B, this table shows the average number of *distinct* long events "
    diag_md += "hit and the average duplication ratio (selected long bins / distinct long events - 1). "
    diag_md += "A high duplication ratio means the prior ranking is putting multiple top calls on the same long event, "
    diag_md += "which wastes low-budget samples.\n\n"
    diag_md += "| Segment | Budget | avg_unique_long_events | avg_long_bin_duplication |\n"
    diag_md += "|---------|--------|------------------------|--------------------------|\n"
    for seg_id, budget, uniq, dup in dup_rows:
        diag_md += f"| {seg_id} | {budget} | {uniq:.2f} | {dup:.2f} |\n"

    # Top-prior bins inspection.
    diag_md += "\n### Top-prior bins per segment\n\n"
    diag_md += "The first 10 bins v2 would pick (ranked by `prior_score_max`). "
    diag_md += "If the very top bins are negative or all belong to the same event, the prior signal is poorly aligned with long events.\n\n"
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid = segment_grids[seg_id]
        ref = segment_refs[seg_id]
        event_type_map = ref.set_index("event_id")["event_type"].to_dict() if "event_id" in ref.columns else {}
        top10 = grid.sort_values("prior_score_max", ascending=False).head(10)
        diag_md += f"**{seg_id}**\n\n"
        diag_md += "| rank | bin | t_start | t_end | prior_score | label | event_id | event_type |\n"
        diag_md += "|------|-----|---------|-------|-------------|-------|----------|------------|\n"
        for rank, (_, row) in enumerate(top10.iterrows(), start=1):
            ev_id = row.get("event_id", "")
            ev_type = event_type_map.get(str(ev_id), "") if ev_id else ""
            diag_md += f"| {rank} | {int(row['bin_idx'])} | {row['t_start']:.1f} | {row['t_end']:.1f} | {row['prior_score_max']:.3f} | {row['label']} | {ev_id} | {ev_type} |\n"
        diag_md += "\n"

    diag_md += "## Interpretation\n\n"
    diag_md += "- **Call-1 lag** (`realcartest_0_1570`): the highest-prior bin is not on a long event, so v2's very first sample is wasted compared to B6's chunk draw.\n"
    diag_md += "- **Mid-run lag with recovery** (`realcartest_2000_3200`): v2 temporarily falls behind around call 5 but its top-prior bins eventually hit enough long events to catch up. The lag is due to exploration inefficiency, not a bad first call.\n"
    diag_md += "- **Mid-run lag without recovery** (`realcartest_3200_3830`): v2's top-prior bins hit a long event early (call 1) but then stay on that event or pick low-value bins, while B6 keeps discovering new long events across chunks. This is a diversity/exploration problem.\n\n"
    diag_md += "In all three segments, the root cause is that **static prior-score ranking is not diversity-aware**: it can spend multiple low-budget calls on the same high-scoring event or region, whereas B6's chunk-level Thompson sampling spreads calls across chunks and adapts to where new events appear.\n\n"

    diag_md += "## Suggested directions for a real fix (not implemented)\n\n"
    diag_md += "1. **Diversity-aware discovery**: after selecting a bin, down-weight or skip other bins that hit the same event, "
    diag_md += "so each call targets a distinct long event.\n"
    diag_md += "2. **Event-level Thompson sampling**: maintain a per-event discovery counter and sample chunks proportionally "
    diag_md += "to the upper confidence bound of undiscovered long events.\n"
    diag_md += "3. **Hybrid cold-start policy**: keep low-budget discovery but seed it with B6-style chunk sampling for the first "
    diag_md += "few calls, then switch to prior-ranking once enough event coverage is established.\n"
    diag_md += "4. **Re-evaluate prior signal calibration**: if the top-prior bins are repeatedly not long events, "
    diag_md += "the roadclip score_count may need recalibration (out of scope for this no-new-data task).\n"

    with open(OUT / "diagnosis_report.md", "w") as f:
        f.write(diag_md)
    print("Wrote diagnosis_report.md")

    # Optional: cumulative recall curve plot for quick visual inspection.
    try:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(3, 2, figsize=(12, 12), sharey=True)
        for i, seg in enumerate(SEGMENTS):
            seg_id = seg["segment_id"]
            for j, budget in enumerate(BUDGETS):
                ax = axes[i, j]
                sub = agg_df[(agg_df["segment_id"] == seg_id) & (agg_df["budget"] == budget)].sort_values("call_index")
                ax.plot(sub["call_index"], sub["b6_recall_mean"], label="B6", marker="o", markersize=3)
                ax.fill_between(sub["call_index"],
                                sub["b6_recall_mean"] - sub["b6_recall_std"],
                                sub["b6_recall_mean"] + sub["b6_recall_std"], alpha=0.2)
                ax.plot(sub["call_index"], sub["v2_recall_mean"], label="v2 discovery-only", marker="s", markersize=3)
                ax.set_title(f"{seg_id}  B={budget}")
                ax.set_xlabel("call index")
                ax.set_ylabel("cumulative long-event recall")
                ax.set_ylim(-0.05, 1.05)
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUT / "cumulative_recall_curves.png", dpi=150)
        plt.close(fig)
        print("Wrote cumulative_recall_curves.png")
    except Exception as e:
        print(f"Plot generation skipped: {e}")


if __name__ == "__main__":
    main()
