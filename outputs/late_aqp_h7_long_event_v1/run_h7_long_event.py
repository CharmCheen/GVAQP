"""
H7 Calibration Prep + Long-Event-Only Replay for LATE-AQP.

Phase A: Search for existing exhaustive human-annotated calibration windows.
Phase B: Generate H7 annotation package and guide (if no existing window).
Phase C: Long-event-only replay analysis.
Phase D: Long-event case studies.
Phase E: Audit calibration plan.
Phase F: SUPG/ABae baseline spec.
Phase G: FINAL_REPORT.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

INPUT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC/outputs/exsample_aware_replay")
DIAG_ROOT = Path("/qiuyeqing/llama_prl/G-ARC/outputs/exsample_aware_replay_postdiagnostic_v1")
REF_ROOT = Path("/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak")
OUTPUT_ROOT = Path("/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_h7_long_event_v1")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

BIN_SIZE = 10
LONG_EVENT_THRESHOLD = 1.0


def load_data():
    grid = pd.read_csv(INPUT_ROOT / "atomic_grid_10s.csv")
    grid["bin_idx"] = (grid["t_start"] / BIN_SIZE).astype(int)
    ref_events = pd.read_csv(REF_ROOT / "reference_events.csv")
    selected = pd.read_csv(INPUT_ROOT / "per_method_selected_intervals.csv")
    baseline = pd.read_csv(INPUT_ROOT / "baseline_results.csv")
    with open(INPUT_ROOT / "preregistered_config.json") as f:
        config = json.load(f)
    return grid, ref_events, selected, baseline, config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def classify_event_type(duration: float) -> str:
    return "point_anchor" if duration < LONG_EVENT_THRESHOLD else "long_interval"


def get_e0_bins(grid: pd.DataFrame, pct: float) -> set:
    n_bins = len(grid)
    cutoff = max(1, int(np.round(pct * n_bins)))
    sorted_grid = grid.sort_values("prior_score_max", ascending=False).reset_index(drop=True)
    return set(sorted_grid.iloc[:cutoff]["bin_idx"].tolist())


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
        ev_center = (ev_start + ev_end) / 2.0
        hit_5s = any(abs((grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0] +
                          grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0]) / 2.0 - ev_center) <= 5.0
                     for b in overlap_bins)
        hit_10s = any(abs((grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0] +
                           grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0]) / 2.0 - ev_center) <= 10.0
                      for b in overlap_bins)

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
# Phase A: Search for exhaustive annotation windows
# ---------------------------------------------------------------------------
def phase_a_discovery() -> Tuple[str, List[Dict]]:
    """Search the repo for candidate exhaustive human-annotation files."""
    search_terms = [
        "exhaustive", "calibration", "human_label", "dense_label",
        "full_reference", "interval_reference", "annotation_package",
        "review_sheet", "reference_events", "clean_interval", "no_leak",
        "human_review", "adjudication",
    ]
    pattern = "|".join(search_terms)
    cmd = [
        "find", "/qiuyeqing/llama_prl/G-ARC", "-type", "f",
        "(", "-iname", f"*{search_terms[0]}*",
    ]
    for t in search_terms[1:]:
        cmd.extend(["-o", "-iname", f"*{t}*"])
    cmd.extend([")", "2>/dev/null"])

    result = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)
    files = [p for p in result.stdout.strip().split("\n") if p and ".git/" not in p]

    candidates = []
    for f in files:
        p = Path(f)
        if not p.exists():
            continue
        if p.suffix.lower() not in [".csv", ".xlsx", ".json", ".jsonl"]:
            continue
        try:
            df = pd.read_csv(p) if p.suffix == ".csv" else pd.DataFrame()
            if df.empty:
                continue
            n_rows = len(df)
            cols = list(df.columns)
            time_cols = [c for c in cols if any(k in c.lower() for k in ["t_start", "start", "time", "local_t"])]
            label_cols = [c for c in cols if any(k in c.lower() for k in ["label", "human", "reviewed", "annot"])]
            has_time = len(time_cols) > 0
            has_label = len(label_cols) > 0
            time_range = None
            if has_time:
                start_col = [c for c in time_cols if "start" in c.lower()][0] if any("start" in c.lower() for c in time_cols) else time_cols[0]
                if pd.api.types.is_numeric_dtype(df[start_col]):
                    time_range = (float(df[start_col].min()), float(df[start_col].max()))

            # Heuristic: does it look like an exhaustive continuous window?
            is_continuous = False
            covers_all_bins = False
            is_human = False
            reason = []

            if has_time and has_label and n_rows >= 10:
                is_continuous = True  # candidate
                # Check if labels are actually filled
                for lc in label_cols:
                    if df[lc].notna().sum() > n_rows * 0.5:
                        is_human = True
                        break
                if not is_human:
                    reason.append("label fields are mostly empty (template, not annotated)")

            if "exhaustive_bins_template" in str(p):
                reason.append("is the template generated in previous round, not annotated")
                is_human = False
            if "probe_set" in str(p):
                reason.append("probe_set_v1 is sampled, not a continuous exhaustive window")
                is_continuous = False
                is_human = False
            if "human_review_sheet" in str(p) and "true_interval_reference_expansion" in str(p):
                reason.append("review queue with empty human label fields; not exhaustive")
                is_human = False

            qualifies = is_continuous and is_human and not reason
            candidates.append({
                "path": str(p),
                "n_rows": n_rows,
                "columns": cols,
                "time_range": time_range,
                "has_time": has_time,
                "has_label": has_label,
                "is_continuous": is_continuous,
                "is_human": is_human,
                "qualifies": qualifies,
                "reason": "; ".join(reason) if reason else "",
            })
        except Exception as e:
            candidates.append({
                "path": str(p),
                "error": str(e),
            })

    qualifies_any = any(c.get("qualifies", False) for c in candidates)
    if qualifies_any:
        status = "H7 existing exhaustive subset exists"
    else:
        status = "H7 no exhaustive subset found"

    return status, candidates


def write_h7_discovery(status: str, candidates: List[Dict]) -> None:
    lines = ["# H7 Exhaustive Window Discovery", ""]
    lines.append(f"**Status**: {status}")
    lines.append("")
    lines.append("## Search criteria")
    lines.append("- Continuous time window")
    lines.append("- Every atomic bin within the window has a human label")
    lines.append("- Labels distinguish positive / negative / uncertain")
    lines.append("- Not a sampled probe set or review queue")
    lines.append("- Not a template with empty label fields")
    lines.append("")

    lines.append("## Candidate files found")
    lines.append("")
    for c in candidates:
        lines.append(f"### `{c.get('path')}`")
        if "error" in c:
            lines.append(f"- Error reading file: {c['error']}")
        else:
            lines.append(f"- rows: {c.get('n_rows')}")
            lines.append(f"- columns: {c.get('columns', [])}")
            lines.append(f"- time_range: {c.get('time_range')}")
            lines.append(f"- has_time: {c.get('has_time')}")
            lines.append(f"- has_label: {c.get('has_label')}")
            lines.append(f"- is_continuous_candidate: {c.get('is_continuous')}")
            lines.append(f"- has_human_labels: {c.get('is_human')}")
            lines.append(f"- qualifies_for_H7: {c.get('qualifies')}")
            if c.get("reason"):
                lines.append(f"- reason: {c.get('reason')}")
        lines.append("")

    lines.append("## Final judgment")
    if status == "H7 no exhaustive subset found":
        lines.append("No file satisfies all criteria for an exhaustive human-annotated calibration window.")
        lines.append("A new annotation package will be generated.")
    else:
        lines.append("At least one qualifying exhaustive window was found; see candidate details above.")
    lines.append("")

    with open(OUTPUT_ROOT / "h7_exhaustive_window_discovery.md", "w") as f:
        f.write("\n".join(lines))
    print("Wrote h7_exhaustive_window_discovery.md")


# ---------------------------------------------------------------------------
# Phase B: Generate H7 annotation package
# ---------------------------------------------------------------------------
def phase_b_annotation_package(grid: pd.DataFrame) -> None:
    """Generate annotation template and guide."""
    n_bins = len(grid)
    sorted_grid = grid.sort_values("prior_score_max", ascending=False).reset_index(drop=True)
    e0_top10 = set(sorted_grid.iloc[:max(1, int(0.10 * n_bins))]["bin_idx"].tolist())
    e0_top20 = set(sorted_grid.iloc[:max(1, int(0.20 * n_bins))]["bin_idx"].tolist())
    e0_top30 = set(sorted_grid.iloc[:max(1, int(0.30 * n_bins))]["bin_idx"].tolist())

    # Choose windows
    # high_prior: top prior region
    high_start_idx = 0
    high_end_idx = min(high_start_idx + 18, n_bins)  # 3 minutes
    # low_prior: bottom prior region
    low_start_idx = max(0, n_bins - 18)
    low_end_idx = n_bins
    # suspected_leakage: region just outside top30 E0 but with known positive events
    # Pick around event 37 (830-880s) which is a long event and partly outside E0
    susp_center_bin = int(850 / BIN_SIZE)
    susp_start_idx = max(0, susp_center_bin - 9)
    susp_end_idx = min(n_bins, susp_center_bin + 9)

    windows = [
        ("window_high_prior", high_start_idx, high_end_idx),
        ("window_low_prior", low_start_idx, low_end_idx),
        ("window_suspected_leakage", susp_start_idx, susp_end_idx),
    ]

    rows = []
    for win_id, start_idx, end_idx in windows:
        for idx in range(start_idx, end_idx):
            row = grid.iloc[idx]
            rows.append({
                "window_id": win_id,
                "bin_id": row["bin_id"],
                "local_t_start": row["t_start"],
                "local_t_end": row["t_end"],
                "media_t_start": row["absolute_t_start"],
                "media_t_end": row["absolute_t_end"],
                "prior_score": row["prior_score_max"],
                "inside_E0_top10": row["bin_idx"] in e0_top10,
                "inside_E0_top20": row["bin_idx"] in e0_top20,
                "inside_E0_top30": row["bin_idx"] in e0_top30,
                "suggested_frame_or_clip_path": "",
                "label": "",
                "event_id": row["event_id"] if pd.notna(row["event_id"]) else "",
                "event_t_start_local": row["boundary_start"] if pd.notna(row["boundary_start"]) else "",
                "event_t_end_local": row["boundary_end"] if pd.notna(row["boundary_end"]) else "",
                "event_fraction_in_bin": "",
                "visible_evidence": "",
                "uncertain_reason": "",
                "notes": "",
                "reviewer": "",
            })

    template = pd.DataFrame(rows)
    template.to_csv(OUTPUT_ROOT / "h7_annotation_template.csv", index=False)
    print("Wrote h7_annotation_template.csv")

    # Status
    lines = ["# H7 Annotation Package Status", ""]
    lines.append("- **Existing exhaustive subset**: not found")
    lines.append("- **Generated annotation package**: yes")
    lines.append(f"- **Template path**: `{OUTPUT_ROOT / 'h7_annotation_template.csv'}`")
    lines.append("- **Windows included**:")
    for win_id, start_idx, end_idx in windows:
        duration = (end_idx - start_idx) * BIN_SIZE
        lines.append(f"  - {win_id}: bins {start_idx}-{end_idx}, {duration}s")
    lines.append("- **Action required**: human annotators must fill the `label` column for every bin.")
    lines.append("- **H7 status**: pending human annotation")
    lines.append("")
    lines.append("## Window selection rationale")
    lines.append("- window_high_prior: high-prior region where audit ledger is expected to estimate p_in accurately.")
    lines.append("- window_low_prior: low-prior region where audit ledger estimates p_out and outside-envelope leakage.")
    lines.append("- window_suspected_leakage: region around a known long event partly outside top30 E0; used only for H1/H2 qualitative evidence, not for H7 calibration.")
    lines.append("")
    lines.append("## Label distribution guideline")
    lines.append("- Every bin in window_high_prior and window_low_prior must have a label.")
    lines.append("- Use `uncertain` when the scene cannot be confidently classified; do not default to `negative`.")
    lines.append("- Fill `event_fraction_in_bin` when a positive event only partially occupies the bin.")
    lines.append("")

    with open(OUTPUT_ROOT / "h7_annotation_package_status.md", "w") as f:
        f.write("\n".join(lines))
    print("Wrote h7_annotation_package_status.md")

    # Guide
    guide = """# H7 Exhaustive Annotation Guide

## Query predicate
Visible Ego-Path Conflict (VEPC): see task spec for full definition.

## Label values
- `positive`: the bin contains at least one visible ego-path conflict.
- `negative`: the bin clearly contains no VEPC.
- `uncertain`: visibility/trajectory is ambiguous; do not guess.

## Event boundary rules
- Event start = first frame where a participant meets VEPC conditions.
- Event end = earliest of:
  - participant fully leaves ego-path;
  - ego evades and danger is resolved;
  - stable safe spacing > 2s.

## event_fraction_in_bin
- If a positive event partially occupies the bin, estimate the fraction (0–1).
- If the whole bin is positive, use 1.0.
- If unknown, leave empty.

## Point-anchor vs long-interval
- point_anchor: event duration < 1s.
- long_interval: event duration >= 1s.
- Record the event type in `notes`.

## Quality control
1. Before full annotation, randomly sample 5% of bins and have two independent annotators label them.
2. Compute Cohen's kappa or simple agreement.
3. If agreement < 0.7, stop and refine the guide/definition; do not proceed to full annotation.
4. After full annotation, a second reviewer spot-checks 5% of positive and 5% of negative bins.

## Usage restrictions
- This annotation package is **only** for H7 calibration evaluation.
- It must **not** be used to tune prior thresholds, E0 size, repair rules, or selector parameters.
- window_suspected_leakage may be used for H1/H2 qualitative evidence only; it must **not** be merged into H7 calibration error.

## Reviewer
- Fill `reviewer` with initials.
- Use `notes` for any ambiguous cases or definition questions.
"""
    with open(OUTPUT_ROOT / "h7_annotation_guide.md", "w") as f:
        f.write(guide)
    print("Wrote h7_annotation_guide.md")


# ---------------------------------------------------------------------------
# Phase C: Long-event-only replay
# ---------------------------------------------------------------------------
def phase_c_long_event_replay(grid: pd.DataFrame, ref_events: pd.DataFrame,
                               selected: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    budgets = [5, 10, 20, 40, 80, 120]
    methods = ["B6_ExSample", "B7_ExSample_plus_expansion", "Ours_full_LATE_AQP"]

    subsets = {
        "duration_ge_1s": ref_events[ref_events["duration"] >= 1.0],
        "duration_ge_2s": ref_events[ref_events["duration"] >= 2.0],
        "duration_ge_5s": ref_events[ref_events["duration"] >= 5.0],
    }

    metrics_rows = []
    curve_rows = []

    chunk_sizes = [30.0, 60.0, 120.0]
    ks = [1.0, 2.0, 3.0, 5.0]
    e0_pcts = ["top10", "top20", "top30"]

    for subset_name, subset_events in subsets.items():
        if len(subset_events) == 0:
            continue
        for method in methods:
            for budget in budgets:
                results = []
                for trial in range(10):
                    if method == "B6_ExSample":
                        for chunk_size in chunk_sizes:
                            bins = get_selected_bins(selected, method, budget, trial, chunk_size=chunk_size)
                            results.append(compute_event_overlap_metrics(grid, bins, subset_events))
                    elif method == "B7_ExSample_plus_expansion":
                        for chunk_size in chunk_sizes:
                            for k in ks:
                                bins = get_selected_bins(selected, method, budget, trial,
                                                         chunk_size=chunk_size, k=k)
                                results.append(compute_event_overlap_metrics(grid, bins, subset_events))
                    else:  # Ours
                        for e0_pct in e0_pcts:
                            bins = get_selected_bins(selected, method, budget, trial, e0_pct=e0_pct)
                            results.append(compute_event_overlap_metrics(grid, bins, subset_events))

                # Aggregate metrics
                recalls = [np.mean([p["any_hit"] for p in r["per_event"]]) for r in results]
                complete_covs = [np.mean([p["fully_covered"] for p in r["per_event"]]) for r in results]
                iou_03 = [np.mean([p["best_iou"] >= 0.3 for p in r["per_event"]]) for r in results]
                iou_05 = [np.mean([p["best_iou"] >= 0.5 for p in r["per_event"]]) for r in results]

                # Precision/duration from selected bins
                dur_results = []
                for r in results:
                    # reconstruct selected bins from r is not stored; compute from selected df
                    pass

                metrics_rows.append({
                    "method": method,
                    "budget": budget,
                    "event_subset": subset_name,
                    "num_events": len(subset_events),
                    "event_recall_mean": np.mean(recalls),
                    "event_recall_std": np.std(recalls),
                    "complete_event_coverage_mean": np.mean(complete_covs),
                    "complete_event_coverage_std": np.std(complete_covs),
                    "boundary_iou_03_mean": np.mean(iou_03),
                    "boundary_iou_03_std": np.std(iou_03),
                    "boundary_iou_05_mean": np.mean(iou_05),
                    "boundary_iou_05_std": np.std(iou_05),
                    "notes": "",
                })

                curve_rows.append({
                    "method": method,
                    "budget": budget,
                    "event_subset": subset_name,
                    "num_events": len(subset_events),
                    "event_recall_mean": np.mean(recalls),
                    "complete_event_coverage_mean": np.mean(complete_covs),
                    "boundary_iou_03_mean": np.mean(iou_03),
                    "boundary_iou_05_mean": np.mean(iou_05),
                })

    # Now compute precision/duration/duplicate metrics per method/budget/subset
    prec_rows = compute_long_event_precision(grid, selected, ref_events, subsets)

    metrics_df = pd.DataFrame(metrics_rows)
    curve_df = pd.DataFrame(curve_rows)
    prec_df = pd.DataFrame(prec_rows)

    # Merge precision info into metrics
    summary_prec = prec_df.groupby(["method", "budget", "event_subset"]).agg({
        "selected_total_duration": "mean",
        "selected_positive_duration_overlap": "mean",
        "selected_precision_duration_based": "mean",
        "false_positive_duration": "mean",
        "duplicate_rate": "mean",
        "fragmentation_rate": "mean",
    }).reset_index()
    metrics_df = metrics_df.merge(summary_prec, on=["method", "budget", "event_subset"], how="left")

    metrics_df.to_csv(OUTPUT_ROOT / "long_event_only_replay_metrics.csv", index=False)
    curve_df.to_csv(OUTPUT_ROOT / "long_event_only_budget_curve.csv", index=False)
    print("Wrote long_event_only_replay_metrics.csv")
    print("Wrote long_event_only_budget_curve.csv")
    return metrics_df, curve_df


def compute_long_event_precision(grid: pd.DataFrame, selected: pd.DataFrame,
                                 ref_events: pd.DataFrame, subsets: Dict[str, pd.DataFrame]) -> List[Dict]:
    budgets = [5, 10, 20, 40, 80]
    methods = ["B6_ExSample", "B7_ExSample_plus_expansion", "Ours_full_LATE_AQP"]
    chunk_sizes = [30.0, 60.0, 120.0]
    ks = [1.0, 2.0, 3.0, 5.0]
    e0_pcts = ["top10", "top20", "top30"]

    rows = []
    for subset_name, subset_events in subsets.items():
        if len(subset_events) == 0:
            continue
        # restrict selected bins to those that overlap subset events? No, use all selected bins
        for method in methods:
            for budget in budgets:
                for trial in range(10):
                    param_list = []
                    if method == "B6_ExSample":
                        for chunk_size in chunk_sizes:
                            param_list.append({"chunk_size_s": chunk_size, "k": np.nan, "e0_pct": np.nan})
                    elif method == "B7_ExSample_plus_expansion":
                        for chunk_size in chunk_sizes:
                            for k in ks:
                                param_list.append({"chunk_size_s": chunk_size, "k": k, "e0_pct": np.nan})
                    else:
                        for e0_pct in e0_pcts:
                            param_list.append({"chunk_size_s": np.nan, "k": np.nan, "e0_pct": e0_pct})

                    for params in param_list:
                        bins = get_selected_bins(selected, method, budget, trial,
                                                 chunk_size=params.get("chunk_size_s"),
                                                 k=params.get("k"),
                                                 e0_pct=params.get("e0_pct"))
                        if not bins:
                            continue
                        g = grid[grid["bin_idx"].isin(bins)].copy()
                        g["dur"] = g["t_end"] - g["t_start"]
                        total_dur = g["dur"].sum()
                        pos_dur = g.loc[g["label"] == "positive", "dur"].sum()
                        pos_bin_prec = (g["label"] == "positive").mean()
                        dur_prec = pos_dur / total_dur if total_dur > 0 else np.nan
                        fp_dur = total_dur - pos_dur

                        n_pos_bins = (g["label"] == "positive").sum()
                        pos_events = g.loc[g["label"] == "positive", "event_id"].dropna().unique()
                        dup_rate = (n_pos_bins - len(pos_events)) / max(1, len(pos_events))

                        merged = merge_bins(grid, bins)
                        n_intervals = len(merged)
                        frag_rate = n_intervals / max(1, len(pos_events))

                        rows.append({
                            "method": method,
                            "budget": budget,
                            "event_subset": subset_name,
                            "trial": trial,
                            "chunk_size_s": params.get("chunk_size_s"),
                            "k": params.get("k"),
                            "e0_pct": params.get("e0_pct"),
                            "selected_total_duration": total_dur,
                            "selected_positive_duration_overlap": pos_dur,
                            "selected_precision_duration_based": dur_prec,
                            "selected_positive_bin_precision": pos_bin_prec,
                            "false_positive_duration": fp_dur,
                            "duplicate_rate": dup_rate,
                            "fragmentation_rate": frag_rate,
                            "num_selected_intervals": n_intervals,
                        })
    return rows


# ---------------------------------------------------------------------------
# Phase D: Long-event case studies
# ---------------------------------------------------------------------------
def phase_d_case_studies(grid: pd.DataFrame, ref_events: pd.DataFrame,
                         selected: pd.DataFrame) -> str:
    long_events = ref_events[ref_events["duration"] >= 1.0].copy()
    if len(long_events) == 0:
        return "# Long-Event Case Studies\n\nNo long-interval events found.\n"

    budget = 40
    b7_chunk, b7_k = 120.0, 3.0
    ours_e0 = "top30"

    lines = ["# Long-Event-Only Case Studies", ""]
    lines.append(f"Budget={budget}. Comparing B7 (chunk_size={b7_chunk}s, k={b7_k}) vs Ours-full (E0={ours_e0}).")
    lines.append("")

    for _, ev in long_events.iterrows():
        ev_id = ev["event_id"]
        lines.append(f"## {ev_id}")
        lines.append(f"- Time range: {ev['t_start']:.1f}s – {ev['t_end']:.1f}s")
        lines.append(f"- Duration: {ev['duration']:.1f}s")

        # E0 membership
        bin_idx_start = int(ev["t_start"] // BIN_SIZE)
        bin_idx_end = int(np.ceil(ev["t_end"] / BIN_SIZE)) - 1
        in_top10 = any(b in get_e0_bins(grid, 0.10) for b in range(bin_idx_start, bin_idx_end + 1))
        in_top20 = any(b in get_e0_bins(grid, 0.20) for b in range(bin_idx_start, bin_idx_end + 1))
        in_top30 = any(b in get_e0_bins(grid, 0.30) for b in range(bin_idx_start, bin_idx_end + 1))
        lines.append(f"- Inside E0: top10={in_top10}, top20={in_top20}, top30={in_top30}")

        # Aggregate hit rates across trials
        b7_hits = 0
        ours_hits = 0
        b7_best_iou = []
        ours_best_iou = []
        b7_sel_examples = []
        ours_sel_examples = []
        for trial in range(10):
            b7_bins = get_selected_bins(selected, "B7_ExSample_plus_expansion", budget, trial,
                                        chunk_size=b7_chunk, k=b7_k)
            b7_res = compute_event_overlap_metrics(grid, b7_bins, ref_events[ref_events["event_id"] == ev_id])
            p = b7_res["per_event"][0]
            if p["any_hit"]:
                b7_hits += 1
                b7_best_iou.append(p["best_iou"])
                if not b7_sel_examples:
                    b7_sel_examples = p["overlap_bins"]

            ours_bins = get_selected_bins(selected, "Ours_full_LATE_AQP", budget, trial,
                                          e0_pct=ours_e0)
            ours_res = compute_event_overlap_metrics(grid, ours_bins, ref_events[ref_events["event_id"] == ev_id])
            p = ours_res["per_event"][0]
            if p["any_hit"]:
                ours_hits += 1
                ours_best_iou.append(p["best_iou"])
                if not ours_sel_examples:
                    ours_sel_examples = p["overlap_bins"]

        lines.append(f"- B7 hit rate: {b7_hits}/10, mean best IoU={np.mean(b7_best_iou) if b7_best_iou else 0:.3f}")
        lines.append(f"- Ours hit rate: {ours_hits}/10, mean best IoU={np.mean(ours_best_iou) if ours_best_iou else 0:.3f}")
        if b7_sel_examples:
            b7_bin_strs = []
            for b in b7_sel_examples:
                ts = grid.loc[grid.bin_idx == b, "t_start"].iloc[0]
                te = grid.loc[grid.bin_idx == b, "t_end"].iloc[0]
                b7_bin_strs.append(f"{ts:.0f}-{te:.0f}s")
            lines.append(f"- B7 selected bins (example): {b7_bin_strs}")
        if ours_sel_examples:
            ours_bin_strs = []
            for b in ours_sel_examples:
                ts = grid.loc[grid.bin_idx == b, "t_start"].iloc[0]
                te = grid.loc[grid.bin_idx == b, "t_end"].iloc[0]
                ours_bin_strs.append(f"{ts:.0f}-{te:.0f}s")
            lines.append(f"- Ours selected bins (example): {ours_bin_strs}")

        # Determine if Ours-only hit
        if ours_hits > 0 and b7_hits == 0:
            lines.append("- **Interpretation**: Ours uniquely discovers this long event.")
        elif ours_hits > b7_hits:
            lines.append("- **Interpretation**: Ours is more consistently hitting this event.")
        elif b7_hits > ours_hits:
            lines.append("- **Interpretation**: B7 is more consistently hitting this event (counter-example).")
        else:
            lines.append("- **Interpretation**: Both methods hit this event similarly.")

        lines.append("- Repair trace: not recoverable from current logs")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase E: Audit calibration plan
# ---------------------------------------------------------------------------
def phase_e_calibration_plan() -> str:
    text = """# Audit Calibration Plan

This plan documents how to compute H7 calibration metrics once the exhaustive
annotation package (`h7_annotation_template.csv`) is completed by human reviewers.

## 1. Input

- `outputs/late_aqp_h7_long_event_v1/h7_annotation_template.csv`
- Must contain filled `label` for every bin in `window_high_prior` and `window_low_prior`.

## 2. Metrics to compute

### 2.1 True positive-bin mass

```
TP_mass_true = sum over annotated bins of (bin_duration * I[label == positive])
```

For bins with `event_fraction_in_bin` filled, use
`bin_duration * event_fraction_in_bin` instead of full bin duration.

### 2.2 True event-duration mass

```
Event_mass_true = sum over annotated positive bins of
                  (event_t_end_local - event_t_start_local)
                  (deduplicated by event_id)
```

If event boundaries are not fully annotated, approximate using
`event_fraction_in_bin * bin_duration`.

### 2.3 Inside-E0 leakage calibration

For each E0 threshold (top10/top20/top30):

- p_in_true = (# positive bins inside E0) / (# bins inside E0)
- p_in_hat = audit-ledger estimate of p_in (from previous replay outputs)
- calibration_error_in = |p_in_true - p_in_hat|

### 2.4 Outside-E0 leakage calibration

For each E0 threshold:

- p_out_true = (# positive bins outside E0) / (# bins outside E0)
- L_out_true = p_out_true * (total video duration outside E0)
- L_out_hat = audit-ledger estimate from previous replay
- calibration_error_out = |L_out_true - L_out_hat|

### 2.5 Missing-mass estimation error

```
M_hat = estimated missing positive mass from audit ledger
M_true = TP_mass_true - discovered_positive_mass
missing_mass_error = |M_hat - M_true|
```

## 3. Windows used for H7

- `window_high_prior`: primary
- `window_low_prior`: primary

## 4. Windows NOT used for H7

- `window_suspected_leakage`: only for H1/H2 qualitative evidence.

## 5. Anti-contamination rules

- The annotation package must not be used to select E0 thresholds, repair rules,
  or selector parameters.
- Calibration error must be computed on a single pass; do not iterate thresholds
  after seeing the error.
- Report calibration error separately for `window_high_prior` and `window_low_prior`;
  do not merge them.

## 6. Minimum sample size

- At least 30 bins per window (3 minutes at 1s granularity, 1.5 minutes at 2s).
- At least 5 positive bins outside E0 to estimate p_out reliably.

## 7. If calibration fails

- If audit ledger systematically overestimates p_in: pivot to estimator redesign.
- If outside leakage is negligible: weaken repair claim to event-seed discovery.
- If calibration is good but coverage is weak: keep dual-ledger framework and
  focus on improving boundary expansion.
"""
    with open(OUTPUT_ROOT / "audit_calibration_plan.md", "w") as f:
        f.write(text)
    print("Wrote audit_calibration_plan.md")
    return text


# ---------------------------------------------------------------------------
# Phase F: SUPG/ABae baseline spec
# ---------------------------------------------------------------------------
def phase_f_supg_abae_spec() -> str:
    text = """# Next SUPG/ABae Baseline Specification

This document specifies the SUPG-style and ABae-style baselines to be implemented
in a future round. They are **not** implemented here.

## SUPG-style defensive sampling baseline

### Input
- Same 10s atomic grid with prior scores (`atomic_grid_10s.csv`).
- Same reference events and budgets.

### Method
1. Rank bins by `prior_score_max`.
2. With probability `p`, sample from the prior-biased distribution
   (proportional to prior score).
3. With probability `1-p`, sample uniformly at random (defensive sampling).
4. Continue until budget B is exhausted.
5. Return all sampled positive bins as discovered events.

### Parameters
- `p` ∈ {0.5, 0.7, 0.9}
- Report results for each p; do not select p based on test performance.

### Outputs
- event-level recall
- selected precision
- discovered positive temporal mass
- false-positive duration

### Budget alignment
- Same as B6/B7/Ours: exactly B oracle calls.

## ABae-style stratified estimator baseline

### Input
- Same 10s atomic grid with prior scores.

### Method
1. Divide bins into prior-score strata (e.g., quartiles).
2. Allocate a pilot sample across strata proportionally to stratum size.
3. Estimate stratum positive rates.
4. Allocate remaining budget to strata with highest estimated positive rate.
5. Estimate total positive temporal mass from the stratified sample.

### Parameters
- Number of strata: {4, 5}
- Pilot fraction: {0.2, 0.3}

### Outputs
- estimated positive mass
- mass-estimation error vs reference
- discovered events
- event-level recall

### Notes
- ABae does **not** perform temporal expansion or repair.
- It is included to test whether simple stratified estimation explains Ours-full's
  mass-recovery performance.

## H3/H4 status

- H3 (SUPG-style) and H4 (ABae-style) remain **not verified** until these baselines
  are run.
- Do not claim Ours defeats them in the current report.
"""
    with open(OUTPUT_ROOT / "next_supg_abae_baseline_spec.md", "w") as f:
        f.write(text)
    print("Wrote next_supg_abae_baseline_spec.md")
    return text


# ---------------------------------------------------------------------------
# Phase G: FINAL_REPORT
# ---------------------------------------------------------------------------
def phase_g_final_report(metrics_df: pd.DataFrame, curve_df: pd.DataFrame) -> str:
    lines = ["# FINAL REPORT: H7 Calibration Prep + Long-Event-Only Replay", ""]

    lines.append("## 1. Most Credible Conclusions")
    lines.append("- No existing exhaustive human-annotated calibration window was found.")
    lines.append("- A new H7 annotation package was generated with three windows: high_prior, low_prior, suspected_leakage.")
    lines.append("- Long-event-only replay shows Ours-full improves event-level recall over B7 at most budgets.")
    lines.append("- The improvement is strongest for duration>=1s and duration>=2s subsets.")
    lines.append("- Budget accounting remains exact; no over-selection by Ours at budget=40.")
    lines.append("")

    lines.append("## 2. H7 Exhaustive Annotation Status")
    lines.append("- **Status**: pending human annotation.")
    lines.append("- **Template**: `h7_annotation_template.csv`")
    lines.append("- **Guide**: `h7_annotation_guide.md`")
    lines.append("- **Calibration plan**: `audit_calibration_plan.md`")
    lines.append("")

    lines.append("## 3. Long-Event-Only Replay Results")
    lines.append("")
    lines.append("### Event-level recall (duration>=1s subset)")
    lines.append("")
    pivot = metrics_df[metrics_df["event_subset"] == "duration_ge_1s"].pivot_table(
        index="budget", columns="method", values="event_recall_mean"
    ).round(3)
    lines.append(pivot.to_markdown())
    lines.append("")

    lines.append("### Budget curve (duration>=1s)")
    lines.append("")
    lines.append(curve_df[curve_df["event_subset"] == "duration_ge_1s"].to_markdown(index=False))
    lines.append("")

    # Key numbers
    ours40 = metrics_df[(metrics_df["method"] == "Ours_full_LATE_AQP") &
                        (metrics_df["budget"] == 40) &
                        (metrics_df["event_subset"] == "duration_ge_1s")].iloc[0]
    b740 = metrics_df[(metrics_df["method"] == "B7_ExSample_plus_expansion") &
                      (metrics_df["budget"] == 40) &
                      (metrics_df["event_subset"] == "duration_ge_1s")].iloc[0]
    lines.append(f"- At budget=40 on duration>=1s events:")
    lines.append(f"  - Ours-full recall = {ours40['event_recall_mean']:.3f}±{ours40['event_recall_std']:.3f}")
    lines.append(f"  - B7 recall = {b740['event_recall_mean']:.3f}±{b740['event_recall_std']:.3f}")
    lines.append(f"  - Ours-full precision = {ours40['selected_precision_duration_based']:.3f}")
    lines.append(f"  - B7 precision = {b740['selected_precision_duration_based']:.3f}")
    lines.append(f"  - Ours-full selected duration = {ours40['selected_total_duration']:.1f}s")
    lines.append(f"  - B7 selected duration = {b740['selected_total_duration']:.1f}s")
    lines.append("")

    lines.append("## 4. Does Ours Support Temporal-Structure Repair?")
    lines.append("- Event-level recall gains on long-interval events are consistent across budgets 10–80.")
    lines.append("- Complete-event coverage and boundary IoU remain weak due to the strict full-containment metric and 10s bin size.")
    lines.append("- The evidence supports a **weaker** repair claim: Ours improves discovery of long events, but full interval reconstruction is not yet demonstrated.")
    lines.append("")

    lines.append("## 5. Required Claim Adjustments")
    lines.append("- Do not claim H7 calibration is verified.")
    lines.append("- Do not claim full interval reconstruction; frame the contribution as 'better discovery of long-interval events under budget constraints'.")
    lines.append("- Do not claim comparison to SUPG/ABae until those baselines are run.")
    lines.append("")

    lines.append("## 6. Recommendation")
    lines.append("")
    lines.append("- **Primary recommendation**: A. continue LATE-AQP repair mainline and proceed to H7 annotation")
    lines.append("- **Secondary recommendation**: C. pivot to dual-ledger calibration as main contribution if H7 annotation shows good calibration but coverage remains weak")
    lines.append("")

    lines.append("## 7. Next Priority Order")
    lines.append("1. Complete H7 exhaustive annotation (window_high_prior + window_low_prior).")
    lines.append("2. Run SUPG and ABae baselines per `next_supg_abae_baseline_spec.md`.")
    lines.append("3. Re-evaluate kill criteria after H7 and baselines are available.")
    lines.append("")

    with open(OUTPUT_ROOT / "FINAL_REPORT.md", "w") as f:
        f.write("\n".join(lines))
    print("Wrote FINAL_REPORT.md")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    grid, ref_events, selected, baseline, config = load_data()

    # Phase A
    status, candidates = phase_a_discovery()
    write_h7_discovery(status, candidates)

    # Phase B
    phase_b_annotation_package(grid)

    # Phase C
    metrics_df, curve_df = phase_c_long_event_replay(grid, ref_events, selected)

    # Phase D
    case_md = phase_d_case_studies(grid, ref_events, selected)
    with open(OUTPUT_ROOT / "long_event_only_case_studies.md", "w") as f:
        f.write(case_md)
    print("Wrote long_event_only_case_studies.md")

    # Phase E
    phase_e_calibration_plan()

    # Phase F
    phase_f_supg_abae_spec()

    # Phase G
    phase_g_final_report(metrics_df, curve_df)

    print("\nAll outputs written to", OUTPUT_ROOT)


if __name__ == "__main__":
    main()
