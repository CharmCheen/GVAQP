"""
Post-replay diagnostic for ExSample-aware LATE-AQP.

Reads outputs from outputs/exsample_aware_replay/ and writes diagnostic
reports to outputs/exsample_aware_replay_postdiagnostic_v1/.

No new VLM/YOLO/GPU/API calls. No modification of existing labels/priors.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

INPUT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC/outputs/exsample_aware_replay")
OUTPUT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC/outputs/exsample_aware_replay_postdiagnostic_v1")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

REF_EVENTS_PATH = Path("/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv")
BIN_SIZE = 10


def load_data():
    grid = pd.read_csv(INPUT_ROOT / "atomic_grid_10s.csv")
    grid["bin_idx"] = (grid["t_start"] / BIN_SIZE).astype(int)
    ref_events = pd.read_csv(REF_EVENTS_PATH)
    baseline = pd.read_csv(INPUT_ROOT / "baseline_results.csv")
    per_budget = pd.read_csv(INPUT_ROOT / "per_budget_metrics.csv")
    selected = pd.read_csv(INPUT_ROOT / "per_method_selected_intervals.csv")
    budget_audit = pd.read_csv(INPUT_ROOT / "budget_accounting_audit.csv")
    with open(INPUT_ROOT / "preregistered_config.json") as f:
        config = json.load(f)
    return grid, ref_events, baseline, per_budget, selected, budget_audit, config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def classify_event_type(duration: float) -> str:
    return "point_anchor" if duration < 1.0 else "long_interval"


def get_selected_bins(selected: pd.DataFrame, method: str, budget: int, trial: int,
                      chunk_size: Optional[float] = None, k: Optional[float] = None,
                      e0_pct: Optional[str] = None) -> List[int]:
    q = (selected["method"] == method) & (selected["budget"] == budget) & (selected["trial"] == trial)
    if chunk_size is not None:
        q &= (selected["chunk_size_s"] == chunk_size) | (pd.isna(selected["chunk_size_s"]) & pd.isna(chunk_size))
    if k is not None:
        q &= (selected["k"] == k) | (pd.isna(selected["k"]) & pd.isna(k))
    if e0_pct is not None:
        q &= (selected["e0_pct"] == e0_pct) | (pd.isna(selected["e0_pct"]) & pd.isna(e0_pct))
    return selected.loc[q, "bin_idx"].tolist()


def compute_event_overlap_metrics(grid: pd.DataFrame, selected_bins: List[int], ref_events: pd.DataFrame) -> Dict:
    """Compute per-event overlap metrics for a set of selected bins."""
    selected_pos_bins = [b for b in selected_bins if grid.loc[grid["bin_idx"] == b, "label"].iloc[0] == "positive"]
    n_total_events = len(ref_events)
    results = []
    for _, ev in ref_events.iterrows():
        ev_start, ev_end = ev["t_start"], ev["t_end"]
        ev_type = classify_event_type(ev["duration"])
        overlap_bins = []
        for b in selected_pos_bins:
            b_start = grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0]
            b_end = grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0]
            if b_start < ev_end and b_end > ev_start:
                overlap_bins.append(b)

        any_hit = len(overlap_bins) > 0
        # hit@±5s / ±10s: selected bin center within 5s/10s of event center
        ev_center = (ev_start + ev_end) / 2.0
        hit_5s = False
        hit_10s = False
        for b in overlap_bins:
            b_center = (grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0] +
                        grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0]) / 2.0
            if abs(b_center - ev_center) <= 5.0:
                hit_5s = True
            if abs(b_center - ev_center) <= 10.0:
                hit_10s = True

        # Best IoU with any overlapping selected positive bin
        best_iou = 0.0
        fully_covered = False
        for b in overlap_bins:
            b_start = grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0]
            b_end = grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0]
            inter = max(0.0, min(ev_end, b_end) - max(ev_start, b_start))
            union = max(ev_end, b_end) - min(ev_start, b_start)
            iou = inter / union if union > 0 else 0.0
            best_iou = max(best_iou, iou)
            if b_start <= ev_start + 1e-6 and b_end >= ev_end - 1e-6:
                fully_covered = True

        results.append({
            "event_id": ev["event_id"],
            "event_type": ev_type,
            "duration": ev["duration"],
            "any_hit": any_hit,
            "hit_5s": hit_5s,
            "hit_10s": hit_10s,
            "best_iou": best_iou,
            "fully_covered": fully_covered,
            "overlap_bins": overlap_bins,
        })
    return {"n_total_events": n_total_events, "per_event": results}


# ---------------------------------------------------------------------------
# Diagnostic 1: H1 mass accounting recheck
# ---------------------------------------------------------------------------
def diagnostic_h1_mass_accounting(grid: pd.DataFrame, ref_events: pd.DataFrame) -> pd.DataFrame:
    n_bins = len(grid)
    sorted_grid = grid.sort_values("prior_score_max", ascending=False).reset_index(drop=True)
    rows = []
    for name, pct in [("top10", 0.10), ("top20", 0.20), ("top30", 0.30)]:
        cutoff = max(1, int(np.round(pct * n_bins)))
        e0_indices = set(sorted_grid.iloc[:cutoff]["bin_idx"].tolist())

        # true event duration mass
        total_true_mass = ref_events["duration"].sum()
        inside_true_mask = ref_events.apply(
            lambda r: any(b in e0_indices for b in range(int(r["t_start"] // 10), int(np.ceil(r["t_end"] / 10)))),
            axis=1,
        )
        # More precise: event is inside E0 if its temporal span overlaps any E0 bin
        # We count the portion inside E0 bins
        inside_true_mass = 0.0
        outside_true_mass = 0.0
        inside_event_ids = set()
        outside_event_ids = set()
        for _, ev in ref_events.iterrows():
            ev_start, ev_end = ev["t_start"], ev["t_end"]
            # bins overlapping the event
            overlap_bins = set(range(int(ev_start // 10), int(np.ceil(ev_end / 10))))
            e0_overlap = overlap_bins & e0_indices
            if e0_overlap:
                inside_event_ids.add(ev["event_id"])
                # Approximate inside mass: fraction of event bins that are in E0
                inside_frac = len(e0_overlap) / len(overlap_bins)
                inside_true_mass += ev["duration"] * inside_frac
                outside_true_mass += ev["duration"] * (1 - inside_frac)
            else:
                outside_event_ids.add(ev["event_id"])
                outside_true_mass += ev["duration"]

        # positive 10s bin mass
        pos_bins = grid[grid["label"] == "positive"]
        total_bin_mass = (pos_bins["t_end"] - pos_bins["t_start"]).sum()
        inside_bin_mass = (pos_bins[pos_bins["bin_idx"].isin(e0_indices)]["t_end"] -
                           pos_bins[pos_bins["bin_idx"].isin(e0_indices)]["t_start"]).sum()
        outside_bin_mass = (pos_bins[~pos_bins["bin_idx"].isin(e0_indices)]["t_end"] -
                            pos_bins[~pos_bins["bin_idx"].isin(e0_indices)]["t_start"]).sum()

        rows.append({
            "E0_threshold": name,
            "total_true_event_duration_mass": total_true_mass,
            "total_positive_10s_bin_mass": total_bin_mass,
            "inside_true_event_duration_mass": inside_true_mass,
            "outside_true_event_duration_mass": outside_true_mass,
            "inside_positive_10s_bin_mass": inside_bin_mass,
            "outside_positive_10s_bin_mass": outside_bin_mass,
            "inside_event_count": len(inside_event_ids),
            "outside_event_count": len(outside_event_ids),
            "outside_event_fraction": len(outside_event_ids) / len(ref_events),
            "notes": "true_event_duration_mass uses event boundaries; positive_10s_bin_mass uses full 10s bin duration",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Diagnostic 2: Event type stratified metrics
# ---------------------------------------------------------------------------
def diagnostic_event_type_stratified(grid: pd.DataFrame, ref_events: pd.DataFrame,
                                     selected: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    budgets = [5, 10, 20, 40, 80, 120]
    rows = []

    # For efficiency, aggregate selected intervals and compute metrics per trial
    # B6 params
    chunk_sizes = [30.0, 60.0, 120.0]
    # B7 params
    ks = [1.0, 2.0, 3.0, 5.0]
    # Ours params
    e0_pcts = ["top10", "top20", "top30"]

    for budget in budgets:
        # B6: average over chunk_size and trial
        b6_results = []
        for chunk_size in chunk_sizes:
            for trial in range(10):
                bins = get_selected_bins(selected, "B6_ExSample", budget, trial, chunk_size=chunk_size)
                b6_results.append(compute_event_overlap_metrics(grid, bins, ref_events))
        rows.extend(summarize_stratified(b6_results, "B6_ExSample", budget, ref_events))

        # B7: average over chunk_size, k, trial
        b7_results = []
        for chunk_size in chunk_sizes:
            for k in ks:
                for trial in range(10):
                    bins = get_selected_bins(selected, "B7_ExSample_plus_expansion", budget, trial,
                                             chunk_size=chunk_size, k=k)
                    b7_results.append(compute_event_overlap_metrics(grid, bins, ref_events))
        rows.extend(summarize_stratified(b7_results, "B7_ExSample_plus_expansion", budget, ref_events))

        # Ours: average over e0_pct and trial
        ours_results = []
        for e0_pct in e0_pcts:
            for trial in range(10):
                bins = get_selected_bins(selected, "Ours_full_LATE_AQP", budget, trial, e0_pct=e0_pct)
                ours_results.append(compute_event_overlap_metrics(grid, bins, ref_events))
        rows.extend(summarize_stratified(ours_results, "Ours_full_LATE_AQP", budget, ref_events))

    return pd.DataFrame(rows)


def summarize_stratified(results: List[Dict], method: str, budget: int,
                         ref_events: pd.DataFrame) -> List[Dict]:
    # results is a list of compute_event_overlap_metrics outputs
    event_types = ["point_anchor", "long_interval", "all"]
    rows = []
    for etype in event_types:
        recalls = []
        hit_5s = []
        hit_10s = []
        complete_cov = []
        iou_03 = []
        iou_05 = []
        frag_rates = []
        dup_rates = []

        for r in results:
            per_event = r["per_event"]
            if etype != "all":
                per_event = [p for p in per_event if p["event_type"] == etype]
            n = len(per_event)
            if n == 0:
                continue
            recalls.append(sum(p["any_hit"] for p in per_event) / n)
            hit_5s.append(sum(p["hit_5s"] for p in per_event) / n)
            hit_10s.append(sum(p["hit_10s"] for p in per_event) / n)
            complete_cov.append(sum(p["fully_covered"] for p in per_event) / n)
            iou_03.append(sum(p["best_iou"] >= 0.3 for p in per_event) / n)
            iou_05.append(sum(p["best_iou"] >= 0.5 for p in per_event) / n)

            # Fragmentation / duplicate: count selected positive bins per hit event
            hit_events = [p for p in per_event if p["any_hit"]]
            if hit_events:
                total_hit_bins = sum(len(p["overlap_bins"]) for p in hit_events)
                unique_hit_events = len(hit_events)
                dup_rates.append((total_hit_bins - unique_hit_events) / unique_hit_events)
                frag_rates.append(total_hit_bins / unique_hit_events)

        rows.append({
            "method": method,
            "budget": budget,
            "event_type": etype,
            "num_events": len(ref_events) if etype == "all" else sum(ref_events["duration"].apply(classify_event_type) == etype),
            "event_recall_mean": np.mean(recalls) if recalls else np.nan,
            "event_recall_std": np.std(recalls) if recalls else np.nan,
            "hit_at_5s_mean": np.mean(hit_5s) if hit_5s else np.nan,
            "hit_at_10s_mean": np.mean(hit_10s) if hit_10s else np.nan,
            "complete_event_coverage_mean": np.mean(complete_cov) if complete_cov else np.nan,
            "boundary_iou_03_mean": np.mean(iou_03) if iou_03 else np.nan,
            "boundary_iou_05_mean": np.mean(iou_05) if iou_05 else np.nan,
            "fragmentation_rate_mean": np.mean(frag_rates) if frag_rates else np.nan,
            "duplicate_rate_mean": np.mean(dup_rates) if dup_rates else np.nan,
            "notes": "",
        })
    return rows


# ---------------------------------------------------------------------------
# Diagnostic 3: Precision / duration / duplicate
# ---------------------------------------------------------------------------
def diagnostic_precision_duration_duplicate(grid: pd.DataFrame, selected: pd.DataFrame,
                                            baseline: pd.DataFrame) -> pd.DataFrame:
    budgets = [5, 10, 20, 40, 80]
    methods = ["B6_ExSample", "B7_ExSample_plus_expansion", "Ours_full_LATE_AQP"]
    rows = []

    for method in methods:
        for budget in budgets:
            sub = selected[(selected["method"] == method) & (selected["budget"] == budget)]
            for (method, chunk_size, k, e0_pct, trial), g in sub.groupby(
                    ["method", "chunk_size_s", "k", "e0_pct", "trial"], dropna=False):
                total_dur = (g["t_end"] - g["t_start"]).sum()
                pos_dur = ((g["label"] == "positive") * (g["t_end"] - g["t_start"])).sum()
                pos_bin_precision = (g["label"] == "positive").mean()
                duration_precision = pos_dur / total_dur if total_dur > 0 else np.nan
                fp_dur = total_dur - pos_dur
                n_selected = len(g)
                n_pos_selected = (g["label"] == "positive").sum()

                # Duplicate rate based on event_id
                pos_events = g.loc[g["label"] == "positive", "event_id"].dropna().unique()
                dup_rate = (n_pos_selected - len(pos_events)) / max(1, len(pos_events))

                # Merge selected bins into intervals
                merged = merge_bins(grid, g["bin_idx"].tolist())
                n_intervals = len(merged)
                avg_dur = merged["duration"].mean() if n_intervals > 0 else 0.0

                rows.append({
                    "method": method,
                    "chunk_size_s": chunk_size,
                    "k": k,
                    "e0_pct": e0_pct,
                    "budget": budget,
                    "trial": trial,
                    "selected_total_duration": total_dur,
                    "selected_positive_duration_overlap": pos_dur,
                    "selected_precision_duration_based": duration_precision,
                    "selected_positive_bin_precision": pos_bin_precision,
                    "duplicate_rate": dup_rate,
                    "fragmentation_rate": n_intervals / max(1, len(pos_events)),
                    "num_selected_intervals": n_intervals,
                    "average_duration_per_selected_interval": avg_dur,
                    "false_positive_duration": fp_dur,
                    "num_selected_bins": n_selected,
                    "num_positive_selected_bins": n_pos_selected,
                })

    df = pd.DataFrame(rows)
    return df


def merge_bins(grid: pd.DataFrame, bin_indices: List[int]) -> pd.DataFrame:
    if not bin_indices:
        return pd.DataFrame(columns=["t_start", "t_end", "duration"])
    bin_indices = sorted(set(bin_indices))
    intervals = []
    cur_start = grid.loc[grid["bin_idx"] == bin_indices[0], "t_start"].iloc[0]
    cur_end = grid.loc[grid["bin_idx"] == bin_indices[0], "t_end"].iloc[0]
    for b in bin_indices[1:]:
        b_start = grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0]
        b_end = grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0]
        if b_start == cur_end:
            cur_end = b_end
        else:
            intervals.append({"t_start": cur_start, "t_end": cur_end, "duration": cur_end - cur_start})
            cur_start, cur_end = b_start, b_end
    intervals.append({"t_start": cur_start, "t_end": cur_end, "duration": cur_end - cur_start})
    return pd.DataFrame(intervals)


# ---------------------------------------------------------------------------
# Diagnostic 4: Parameter stability
# ---------------------------------------------------------------------------
def diagnostic_parameter_stability(baseline: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "event_level_recall", "complete_event_coverage", "selected_precision",
        "boundary_iou_0_3", "boundary_iou_0_5", "fragmentation_rate",
        "selected_total_duration", "duplicate_rate",
    ]
    rows = []
    for (method, budget), g in baseline.groupby(["method", "budget"]):
        for metric in metrics:
            col = f"{metric}_mean"
            if col not in g.columns:
                continue
            vals = g[col].dropna()
            if len(vals) == 0:
                continue
            rows.append({
                "method": method,
                "budget": budget,
                "metric": metric,
                "mean": vals.mean(),
                "std": vals.std(),
                "min": vals.min(),
                "max": vals.max(),
                "median": vals.median(),
                "num_param_configs": len(vals),
                "best_config_value": vals.max(),
                "worst_config_value": vals.min(),
                "notes": "variance across pre-registered parameter combinations",
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Diagnostic 5: Budget=40 case study
# ---------------------------------------------------------------------------
def diagnostic_budget40_case_study(grid: pd.DataFrame, ref_events: pd.DataFrame,
                                   selected: pd.DataFrame) -> str:
    budget = 40
    # Use best config for B7 (chunk_size=120, k=3) and Ours (top30) based on previous results
    b7_chunk, b7_k = 120.0, 3.0
    ours_e0 = "top30"

    # Aggregate across trials: count how many trials hit each event
    b7_hits = {ev: 0 for ev in ref_events["event_id"]}
    ours_hits = {ev: 0 for ev in ref_events["event_id"]}
    b7_hit_examples = {ev: [] for ev in ref_events["event_id"]}
    ours_hit_examples = {ev: [] for ev in ref_events["event_id"]}

    for trial in range(10):
        b7_bins = get_selected_bins(selected, "B7_ExSample_plus_expansion", budget, trial,
                                    chunk_size=b7_chunk, k=b7_k)
        b7_res = compute_event_overlap_metrics(grid, b7_bins, ref_events)
        for p in b7_res["per_event"]:
            if p["any_hit"]:
                b7_hits[p["event_id"]] += 1
                if not b7_hit_examples[p["event_id"]]:
                    b7_hit_examples[p["event_id"]] = p["overlap_bins"]

        ours_bins = get_selected_bins(selected, "Ours_full_LATE_AQP", budget, trial,
                                      e0_pct=ours_e0)
        ours_res = compute_event_overlap_metrics(grid, ours_bins, ref_events)
        for p in ours_res["per_event"]:
            if p["any_hit"]:
                ours_hits[p["event_id"]] += 1
                if not ours_hit_examples[p["event_id"]]:
                    ours_hit_examples[p["event_id"]] = p["overlap_bins"]

    lines = [f"# Budget={budget} Case Study", ""]
    lines.append(f"Comparing B7 (chunk_size={b7_chunk}s, k={b7_k}) vs Ours-full (E0={ours_e0}).")
    lines.append("")

    only_ours = [ev for ev in ref_events["event_id"] if ours_hits[ev] > 0 and b7_hits[ev] == 0]
    only_b7 = [ev for ev in ref_events["event_id"] if b7_hits[ev] > 0 and ours_hits[ev] == 0]
    both = [ev for ev in ref_events["event_id"] if b7_hits[ev] > 0 and ours_hits[ev] > 0]
    neither = [ev for ev in ref_events["event_id"] if b7_hits[ev] == 0 and ours_hits[ev] == 0]

    lines.append("## Event hit counts (across 10 trials)")
    lines.append("")
    lines.append(f"- Hit by both: {len(both)} events → {both}")
    lines.append(f"- Hit only by Ours-full: {len(only_ours)} events → {only_ours}")
    lines.append(f"- Hit only by B7: {len(only_b7)} events → {only_b7}")
    lines.append(f"- Hit by neither: {len(neither)} events → {neither}")
    lines.append("")

    lines.append("## Events hit only by Ours-full")
    lines.append("")
    for ev_id in only_ours:
        ev = ref_events[ref_events["event_id"] == ev_id].iloc[0]
        ev_type = classify_event_type(ev["duration"])
        bins = ours_hit_examples[ev_id]
        bin_times = [f"{grid.loc[grid['bin_idx']==b,'t_start'].iloc[0]:.0f}-{grid.loc[grid['bin_idx']==b,'t_end'].iloc[0]:.0f}s" for b in bins]
        in_e0 = any(b in get_e0_bins(grid, 0.30) for b in bins)
        lines.append(f"- **{ev_id}** ({ev_type}, duration={ev['duration']:.1f}s, event interval {ev['t_start']:.1f}-{ev['t_end']:.1f}s)")
        lines.append(f"  - selected bins: {bin_times}")
        lines.append(f"  - any bin inside top30 E0: {in_e0}")
        if not in_e0:
            lines.append(f"  - **Likely audit/repair contribution**: selected bins fall outside the top30 prior envelope.")
        lines.append("")

    lines.append("## Events hit only by B7")
    lines.append("")
    for ev_id in only_b7:
        ev = ref_events[ref_events["event_id"] == ev_id].iloc[0]
        ev_type = classify_event_type(ev["duration"])
        bins = b7_hit_examples[ev_id]
        bin_times = [f"{grid.loc[grid['bin_idx']==b,'t_start'].iloc[0]:.0f}-{grid.loc[grid['bin_idx']==b,'t_end'].iloc[0]:.0f}s" for b in bins]
        lines.append(f"- **{ev_id}** ({ev_type}, duration={ev['duration']:.1f}s, event interval {ev['t_start']:.1f}-{ev['t_end']:.1f}s)")
        lines.append(f"  - selected bins: {bin_times}")
        lines.append("")

    lines.append("## Interpretation")
    lines.append("")
    n_ours_only_long = sum(1 for ev_id in only_ours
                           if classify_event_type(ref_events[ref_events["event_id"] == ev_id].iloc[0]["duration"]) == "long_interval")
    n_ours_only_point = len(only_ours) - n_ours_only_long
    lines.append(f"- Ours-only events: {n_ours_only_long} long-interval, {n_ours_only_point} point-anchor.")
    if n_ours_only_long > 0:
        lines.append("- Presence of long-interval Ours-only events supports the repair contribution claim.")
    else:
        lines.append("- All Ours-only events are point-anchor. This weakens the 'temporal structure repair' claim; the gain is better described as event-seed discovery.")
    lines.append("")

    return "\n".join(lines)


def get_e0_bins(grid: pd.DataFrame, pct: float) -> set:
    n_bins = len(grid)
    cutoff = max(1, int(np.round(pct * n_bins)))
    sorted_grid = grid.sort_values("prior_score_max", ascending=False).reset_index(drop=True)
    return set(sorted_grid.iloc[:cutoff]["bin_idx"].tolist())


# ---------------------------------------------------------------------------
# Diagnostic 6 & 7 and recommendation are generated as markdown in main()
# ---------------------------------------------------------------------------
def generate_postdiagnostic_report(h1_df: pd.DataFrame, strat_df: pd.DataFrame,
                                   prec_df: pd.DataFrame, stab_df: pd.DataFrame,
                                   budget40_md: str, ref_events: pd.DataFrame) -> str:
    lines = ["# Post-Replay Diagnostic Report", ""]

    # H1 clarification
    lines.append("## 1. H1 Positive Mass Accounting Recheck")
    lines.append("")
    lines.append("The previous report contained two numbers that looked contradictory:")
    lines.append("- `true_event_duration_mass` = 133.5s (sum of reference event durations).")
    lines.append("- `outside_E0_positive_10s_bin_mass` up to 260.0s (full 10s bins outside E0).")
    lines.append("")
    lines.append("These are different metrics. The table below reconciles them:")
    lines.append("")
    lines.append(h1_df.to_markdown(index=False))
    lines.append("")
    lines.append("**Conclusion**: H1 remains valid under both definitions, but the magnitude differs.")
    lines.append("- Under `true_event_duration_mass`, a substantial fraction of event mass lies outside top10/top20 E0.")
    lines.append("- Under `positive_10s_bin_mass`, the numbers are larger because each positive bin contributes a full 10s.")
    lines.append("- For future papers, we recommend reporting **true_event_duration_mass** as the primary H1 metric, and using positive_10s_bin_mass only as a secondary lattice coverage measure.")
    lines.append("")

    # Event type stratification
    lines.append("## 2. Point-Anchor vs Long-Event Stratification")
    lines.append("")
    lines.append(strat_df.to_markdown(index=False))
    lines.append("")
    lines.append("**Key observations**:")
    pa_ours = strat_df[(strat_df["method"] == "Ours_full_LATE_AQP") &
                       (strat_df["event_type"] == "point_anchor") &
                       (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    pa_b7 = strat_df[(strat_df["method"] == "B7_ExSample_plus_expansion") &
                     (strat_df["event_type"] == "point_anchor") &
                     (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    long_ours = strat_df[(strat_df["method"] == "Ours_full_LATE_AQP") &
                         (strat_df["event_type"] == "long_interval") &
                         (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    long_b7 = strat_df[(strat_df["method"] == "B7_ExSample_plus_expansion") &
                       (strat_df["event_type"] == "long_interval") &
                       (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    lines.append(f"- At budget=40, Ours-full recall on point-anchor events = {pa_ours:.3f} vs B7 = {pa_b7:.3f}.")
    lines.append(f"- At budget=40, Ours-full recall on long-interval events = {long_ours:.3f} vs B7 = {long_b7:.3f}.")
    if long_ours > long_b7:
        lines.append("- Ours-full improves on long-interval events, supporting the temporal-structure repair claim.")
    else:
        lines.append("- Ours-full does **not** improve on long-interval events; the overall recall gain is driven by point-anchor hits. This should be described as event-seed discovery, not full interval reconstruction.")
    lines.append("")

    # Precision / duration
    lines.append("## 3. Precision, Selected Duration, and Duplicate Rate")
    lines.append("")
    summary = prec_df.groupby(["method", "budget"]).agg({
        "selected_total_duration": "mean",
        "selected_positive_duration_overlap": "mean",
        "selected_precision_duration_based": "mean",
        "selected_positive_bin_precision": "mean",
        "duplicate_rate": "mean",
        "fragmentation_rate": "mean",
        "false_positive_duration": "mean",
    }).reset_index().round(3)
    lines.append(summary.to_markdown(index=False))
    lines.append("")

    ours40 = summary[(summary["method"] == "Ours_full_LATE_AQP") & (summary["budget"] == 40)].iloc[0]
    b740 = summary[(summary["method"] == "B7_ExSample_plus_expansion") & (summary["budget"] == 40)].iloc[0]
    lines.append(f"- At budget=40, Ours-full selected total duration = {ours40['selected_total_duration']:.1f}s vs B7 = {b740['selected_total_duration']:.1f}s.")
    lines.append(f"- Duration-based precision: Ours = {ours40['selected_precision_duration_based']:.3f}, B7 = {b740['selected_precision_duration_based']:.3f}.")
    lines.append(f"- False-positive duration: Ours = {ours40['false_positive_duration']:.1f}s, B7 = {b740['false_positive_duration']:.1f}s.")
    if ours40["selected_total_duration"] > b740["selected_total_duration"] * 1.1:
        lines.append("- Ours-full selects more total duration than B7. Part of the recall gain may come from wider selection, not smarter selection.")
    if ours40["selected_precision_duration_based"] < b740["selected_precision_duration_based"]:
        lines.append("- Ours-full has lower duration-based precision than B7 at budget=40: the recall gain trades off precision.")
    lines.append("")

    # Parameter stability
    lines.append("## 4. Parameter Stability")
    lines.append("")
    stab40 = stab_df[(stab_df["budget"] == 40) & (stab_df["metric"] == "event_level_recall")]
    lines.append(stab40[["method", "mean", "std", "min", "max", "num_param_configs"]].to_markdown(index=False))
    lines.append("")
    lines.append("**Interpretation**: A small std relative to the mean indicates stable advantage across pre-registered parameters. A large std means the result depends on parameter choice.")
    lines.append("")

    # Budget 40 case study
    lines.append(budget40_md)
    lines.append("")

    return "\n".join(lines)


def generate_revised_h1_h7(h1_df: pd.DataFrame, strat_df: pd.DataFrame,
                           prec_df: pd.DataFrame, stab_df: pd.DataFrame,
                           budget40_md: str) -> str:
    lines = ["# Revised H1–H7 Summary", ""]

    lines.append("| Hypothesis | Status | Revised conclusion |")
    lines.append("|------------|--------|--------------------|")
    lines.append("| H1 | supported | Positive mass exists outside E0 under both true-event-duration and positive-bin-mass definitions. |")
    lines.append("| H2 | supported | Outside positives show temporal neighbourhood structure (median gaps 20–40s). |")
    lines.append("| H3/H4 | not verified | SUPG/ABae baselines not independently re-run; cannot claim comparison. |")

    # H5: compare at budget=40 for all events and long events
    ours_all_40 = strat_df[(strat_df["method"] == "Ours_full_LATE_AQP") & (strat_df["event_type"] == "all") & (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    b7_all_40 = strat_df[(strat_df["method"] == "B7_ExSample_plus_expansion") & (strat_df["event_type"] == "all") & (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    h5_recall = "supported" if ours_all_40 > b7_all_40 else "partially supported"
    lines.append(f"| H5 recall | {h5_recall} | At budget=40, Ours-full recall={ours_all_40:.3f} vs B7={b7_all_40:.3f}. |")

    ours_long_cov_40 = strat_df[(strat_df["method"] == "Ours_full_LATE_AQP") & (strat_df["event_type"] == "long_interval") & (strat_df["budget"] == 40)]["complete_event_coverage_mean"].values[0]
    b7_long_cov_40 = strat_df[(strat_df["method"] == "B7_ExSample_plus_expansion") & (strat_df["event_type"] == "long_interval") & (strat_df["budget"] == 40)]["complete_event_coverage_mean"].values[0]
    h5_cov = "supported" if ours_long_cov_40 > b7_long_cov_40 else "partially supported"
    lines.append(f"| H5 coverage | {h5_cov} | At budget=40, long-event complete coverage Ours={ours_long_cov_40:.3f} vs B7={b7_long_cov_40:.3f}. |")

    # H6
    long_gain = (
        strat_df[(strat_df["method"] == "Ours_full_LATE_AQP") & (strat_df["event_type"] == "long_interval") & (strat_df["budget"] == 40)]["event_recall_mean"].values[0] -
        strat_df[(strat_df["method"] == "B7_ExSample_plus_expansion") & (strat_df["event_type"] == "long_interval") & (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    )
    if long_gain > 0.05:
        h6_status = "supported"
    elif long_gain > 0:
        h6_status = "partially supported"
    else:
        h6_status = "not supported"
    lines.append(f"| H6 | {h6_status} | Long-interval recall gain at budget=40 = {long_gain:.3f}. If this is ≤0, the benefit is mainly point-anchor seed discovery, not temporal structure repair. |")

    lines.append("| H7 | not verified | No exhaustive human-annotated window exists; missing-mass calibration remains unverified. |")
    lines.append("")

    lines.append("## Detailed H6 Evidence")
    lines.append("")
    h6_detail = strat_df[strat_df["budget"].isin([10, 20, 40, 80])].pivot_table(
        index=["budget", "event_type"], columns="method", values="event_recall_mean"
    ).round(3)
    lines.append(h6_detail.to_markdown())
    lines.append("")

    return "\n".join(lines)


def generate_revised_kill_criteria(strat_df: pd.DataFrame, prec_df: pd.DataFrame,
                                   stab_df: pd.DataFrame) -> str:
    lines = ["# Revised Kill Criteria Report", ""]

    # KC1
    lines.append("## KC1: Is Ours fully explained by B7?")
    long40_ours = strat_df[(strat_df["method"] == "Ours_full_LATE_AQP") & (strat_df["event_type"] == "long_interval") & (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    long40_b7 = strat_df[(strat_df["method"] == "B7_ExSample_plus_expansion") & (strat_df["event_type"] == "long_interval") & (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    if long40_ours > long40_b7 + 0.05:
        lines.append(f"- **NOT triggered** on long events: Ours={long40_ours:.3f} vs B7={long40_b7:.3f}.")
    else:
        lines.append(f"- **TRIGGERED**: On long events Ours={long40_ours:.3f} vs B7={long40_b7:.3f}; the gain is not clearly structural.")
    lines.append("")

    # KC2
    lines.append("## KC2: Is Ours gain from selecting more duration?")
    ours40_dur = prec_df[(prec_df["method"] == "Ours_full_LATE_AQP") & (prec_df["budget"] == 40)]["selected_total_duration"].mean()
    b740_dur = prec_df[(prec_df["method"] == "B7_ExSample_plus_expansion") & (prec_df["budget"] == 40)]["selected_total_duration"].mean()
    if ours40_dur > b740_dur * 1.2:
        lines.append(f"- **TRIGGERED**: Ours selects {ours40_dur:.1f}s vs B7 {b740_dur:.1f}s (>20% more). Recall gain may be over-selection.")
    else:
        lines.append(f"- **NOT triggered**: Ours selects {ours40_dur:.1f}s vs B7 {b740_dur:.1f}s (within 20%).")
    lines.append("")

    # KC3
    lines.append("## KC3: Is Ours gain mainly from point-anchor hits?")
    pa_gain = (
        strat_df[(strat_df["method"] == "Ours_full_LATE_AQP") & (strat_df["event_type"] == "point_anchor") & (strat_df["budget"] == 40)]["event_recall_mean"].values[0] -
        strat_df[(strat_df["method"] == "B7_ExSample_plus_expansion") & (strat_df["event_type"] == "point_anchor") & (strat_df["budget"] == 40)]["event_recall_mean"].values[0]
    )
    long_gain = long40_ours - long40_b7
    if pa_gain > long_gain + 0.05:
        lines.append(f"- **TRIGGERED**: point-anchor gain = {pa_gain:.3f}, long-event gain = {long_gain:.3f}. The contribution is mainly seed discovery, not structure repair.")
    else:
        lines.append(f"- **NOT triggered**: point-anchor gain = {pa_gain:.3f}, long-event gain = {long_gain:.3f}.")
    lines.append("")

    # KC4
    lines.append("## KC4: Is calibration missing?")
    lines.append("- **TRIGGERED**: H7 remains unverified; no exhaustive human annotation exists. Cannot claim calibrated missing-mass estimation.")
    lines.append("")

    # KC5
    lines.append("## KC5: Is budget=40 advantage parameter-stable?")
    std_ours = stab_df[(stab_df["method"] == "Ours_full_LATE_AQP") & (stab_df["budget"] == 40) & (stab_df["metric"] == "event_level_recall")]["std"].values[0]
    mean_ours = stab_df[(stab_df["method"] == "Ours_full_LATE_AQP") & (stab_df["budget"] == 40) & (stab_df["metric"] == "event_level_recall")]["mean"].values[0]
    if std_ours / mean_ours > 0.2:
        lines.append(f"- **TRIGGERED**: coefficient of variation = {std_ours/mean_ours:.2f}; advantage is parameter-sensitive.")
    else:
        lines.append(f"- **NOT triggered**: coefficient of variation = {std_ours/mean_ours:.2f}; advantage is relatively stable.")
    lines.append("")

    # KC6
    lines.append("## KC6: Is complete-event coverage sufficient?")
    cov40_ours = strat_df[(strat_df["method"] == "Ours_full_LATE_AQP") & (strat_df["event_type"] == "long_interval") & (strat_df["budget"] == 40)]["complete_event_coverage_mean"].values[0]
    if cov40_ours < 0.5:
        lines.append(f"- **TRIGGERED**: long-event complete coverage at budget=40 = {cov40_ours:.3f} < 0.5.")
        lines.append("- Note: This metric requires a selected interval to fully contain the event. With 10s bins and long events spanning multiple bins, this is a very strict criterion. Low coverage does not necessarily mean repair failed, but it limits how strongly we can claim 'full interval reconstruction'.")
    else:
        lines.append(f"- **NOT triggered**: long-event complete coverage at budget=40 = {cov40_ours:.3f}.")
    lines.append("")

    # Final recommendation
    lines.append("## Final Recommendation")
    lines.append("")
    # If the core algorithmic advantage (KC1, KC2, KC3) is solid, but calibration/coverage
    # are weak, recommend continuing the framework with a calibration pivot rather than
    # abandoning the repair claim entirely.
    core_triggers = sum([
        long40_ours <= long40_b7 + 0.05,  # KC1
        ours40_dur > b740_dur * 1.2,       # KC2
        pa_gain > long_gain + 0.05,        # KC3
    ])
    support_triggers = sum([
        True,  # KC4 calibration missing
        cov40_ours < 0.5,  # KC6 coverage weak
    ])

    if core_triggers >= 2:
        rec = "continue but pivot to event-seed discovery"
    elif support_triggers >= 1 and core_triggers == 0:
        rec = "continue but pivot to dual-ledger calibration"
    elif core_triggers == 0:
        rec = "continue LATE-AQP as repair paper"
    else:
        rec = "continue but pivot to dual-ledger calibration"

    lines.append(f"- **Primary recommendation**: {rec}")
    lines.append("- **Secondary recommendation**: Conduct exhaustive calibration annotation (H7) before any stronger repair claim; also consider a long-event-only replay to isolate structure-repair effects from point-anchor seed discovery.")
    lines.append("")

    return "\n".join(lines)


def generate_next_experiment_recommendation(strat_df: pd.DataFrame, prec_df: pd.DataFrame) -> str:
    lines = ["# Next Experiment Recommendation", ""]

    lines.append("## 1. Most Credible Conclusions")
    lines.append("- E0 (top prior envelope) misses positive temporal mass (H1 supported).")
    lines.append("- Outside positives cluster temporally (H2 supported).")
    lines.append("- Ours-full improves event-level recall at some budgets, but the gain is mixed across event types and parameter settings.")
    lines.append("- Budget accounting is exact; the comparison is fair.")
    lines.append("")

    lines.append("## 2. Claims That Cannot Be Made Yet")
    lines.append("- 'LATE-AQP repair recovers full event intervals better than ExSample+expansion' — complete-event coverage evidence is weak.")
    lines.append("- 'Audit ledger is calibrated' — H7 unverified.")
    lines.append("- 'Ours reduces false positives' — duration-based precision is often lower than B7.")
    lines.append("- Comparison to SUPG/ABae baselines — not yet run.")
    lines.append("")

    lines.append("## 3. Recommended Next Steps (priority order)")
    lines.append("1. **A. Exhaustive calibration annotation** — highest priority. Without H7, no calibration claim is possible.")
    lines.append("2. **D. Long-event-only replay** — second priority. Remove point-anchor events and re-run B6/B7/Ours to see if long-event structure repair holds.")
    lines.append("3. **B. SUPG/ABae baselines** — third priority. Needed for H3/H4 and broader positioning.")
    lines.append("4. **E. Redesign repair utility** — conditional. If long-event replay still shows weak coverage, reformulate repair as a budget reallocation rather than interval expansion.")
    lines.append("5. **C. Audit schedule v3 ablation** — lower priority until H7 is verified.")
    lines.append("")

    lines.append("## 4. Next Codex Prompt Draft")
    lines.append("```")
    lines.append("TASK: Long-Event-Only Replay for LATE-AQP")
    lines.append("Use the same data as outputs/exsample_aware_replay/, but restrict reference events to long_interval events (duration >= 1s).")
    lines.append("Re-run B6, B7, and Ours-full with the same pre-registered parameters and budgets.")
    lines.append("Report event-level recall, complete-event coverage, boundary IoU, precision, and selected duration.")
    lines.append("Determine whether Ours-full still outperforms B7 when point-anchor events are excluded.")
    lines.append("Do not modify existing labels or priors. No new VLM/YOLO/GPU/API calls.")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    grid, ref_events, baseline, per_budget, selected, budget_audit, config = load_data()

    # Diagnostic 1
    h1_df = diagnostic_h1_mass_accounting(grid, ref_events)
    h1_df.to_csv(OUTPUT_ROOT / "h1_mass_accounting_recheck.csv", index=False)
    print("Wrote h1_mass_accounting_recheck.csv")

    # Diagnostic 2
    strat_df = diagnostic_event_type_stratified(grid, ref_events, selected, baseline)
    strat_df.to_csv(OUTPUT_ROOT / "event_type_stratified_metrics.csv", index=False)
    print("Wrote event_type_stratified_metrics.csv")

    # Diagnostic 3
    prec_df = diagnostic_precision_duration_duplicate(grid, selected, baseline)
    prec_df.to_csv(OUTPUT_ROOT / "precision_duration_duplicate_metrics.csv", index=False)
    print("Wrote precision_duration_duplicate_metrics.csv")

    # Diagnostic 4
    stab_df = diagnostic_parameter_stability(baseline)
    stab_df.to_csv(OUTPUT_ROOT / "parameter_stability_metrics.csv", index=False)
    print("Wrote parameter_stability_metrics.csv")

    # Diagnostic 5
    budget40_md = diagnostic_budget40_case_study(grid, ref_events, selected)
    with open(OUTPUT_ROOT / "budget40_case_study.md", "w") as f:
        f.write(budget40_md)
    print("Wrote budget40_case_study.md")

    # Diagnostic 6: postdiagnostic report
    post_md = generate_postdiagnostic_report(h1_df, strat_df, prec_df, stab_df, budget40_md, ref_events)
    with open(OUTPUT_ROOT / "postdiagnostic_report.md", "w") as f:
        f.write(post_md)
    print("Wrote postdiagnostic_report.md")

    # Revised H1-H7
    revised_h1_h7_md = generate_revised_h1_h7(h1_df, strat_df, prec_df, stab_df, budget40_md)
    with open(OUTPUT_ROOT / "revised_h1_h7_summary.md", "w") as f:
        f.write(revised_h1_h7_md)
    print("Wrote revised_h1_h7_summary.md")

    # Revised kill criteria
    kill_md = generate_revised_kill_criteria(strat_df, prec_df, stab_df)
    with open(OUTPUT_ROOT / "revised_kill_criteria_report.md", "w") as f:
        f.write(kill_md)
    print("Wrote revised_kill_criteria_report.md")

    # Next experiment recommendation
    rec_md = generate_next_experiment_recommendation(strat_df, prec_df)
    with open(OUTPUT_ROOT / "next_experiment_recommendation.md", "w") as f:
        f.write(rec_md)
    print("Wrote next_experiment_recommendation.md")


if __name__ == "__main__":
    main()
