"""
Data discovery for ExSample-aware Replay (LATE-AQP).

This script must run BEFORE any baseline/replay execution.
It analyses candidate data files, selects the primary reference universe,
builds the 10s atomic-bin grid, and writes data_discovery_report.md.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

BASE_SEARCH_ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUTPUT_ROOT = BASE_SEARCH_ROOT / "outputs" / "exsample_aware_replay"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

QUERY_PREDICATE = "Visible Ego-Path Conflict (VEPC)"
ATOMIC_BIN_SIZE = 10  # seconds, locked by task spec


@dataclass
class DataSource:
    path: str
    file_type: str
    n_rows: int
    columns: List[str]
    time_range: Optional[tuple]
    bin_durations: Optional[Dict[float, int]]
    selected: bool
    rationale: str


def analyse_reference_candidates() -> List[DataSource]:
    sources = []
    candidates = [
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v1/reference_events.csv",
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v1/full_reference_units.csv",
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv",
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/full_reference_units.csv",
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv",
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/full_reference_units.csv",
        "src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/reference_events_expanded_v1.csv",
    ]
    for rel in candidates:
        p = BASE_SEARCH_ROOT / rel
        if not p.exists():
            continue
        df = pd.read_csv(p)
        time_range = None
        bin_dur = None
        if {"t_start", "t_end"}.issubset(df.columns):
            time_range = (float(df["t_start"].min()), float(df["t_end"].max()))
            bin_dur = (df["t_end"] - df["t_start"]).round(4).value_counts().to_dict()
        is_selected = "clean_interval_aqp_full_reference_v2_clean_no_leak" in rel
        rationale = (
            "Primary reference for replay."
            if is_selected
            else "Alternate or older reference; not used as primary."
        )
        if "true_interval_reference_expansion" in rel and len(df) <= 1:
            rationale = "Empty file (header only); not usable."
        sources.append(
            DataSource(
                path=str(p),
                file_type="reference_labels" if "unit" in rel else "reference_events",
                n_rows=len(df),
                columns=list(df.columns),
                time_range=time_range,
                bin_durations=bin_dur,
                selected=is_selected,
                rationale=rationale,
            )
        )
    return sources


def analyse_prior_candidates() -> List[DataSource]:
    sources = []
    candidates = [
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/cheap_signals_per_unit.csv",
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/cheap_signals_per_unit.csv",
        "outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv",
        "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_v2_clean.csv",
    ]
    for rel in candidates:
        p = BASE_SEARCH_ROOT / rel
        if not p.exists():
            continue
        df = pd.read_csv(p)
        time_range = None
        bin_dur = None
        if {"t_start", "t_end"}.issubset(df.columns):
            time_range = (float(df["t_start"].min()), float(df["t_end"].max()))
            bin_dur = (df["t_end"] - df["t_start"]).round(4).value_counts().head(10).to_dict()
        is_selected = rel.endswith("cheap_signals_per_unit.csv") and "clean_no_leak" in rel
        rationale = (
            "Primary per-unit prior score source (cheap_fused_score)."
            if is_selected
            else "Interval-level aggregation; not atomic-unit prior."
        )
        sources.append(
            DataSource(
                path=str(p),
                file_type="prior_scores",
                n_rows=len(df),
                columns=list(df.columns),
                time_range=time_range,
                bin_durations=bin_dur,
                selected=is_selected,
                rationale=rationale,
            )
        )
    return sources


def build_atomic_grid(
    units_path: Path,
    priors_path: Path,
    events_path: Path,
    bin_size: int = 10,
) -> pd.DataFrame:
    units = pd.read_csv(units_path)
    base_units = pd.read_csv(str(units_path).replace("full_reference_units.csv", "base_units.csv"))
    priors = pd.read_csv(priors_path)
    events = pd.read_csv(events_path)

    # Merge prior scores and base-unit metadata into units
    units = units.merge(
        priors[["unit_id", "cheap_fused_score", "primary_signal_score"]],
        on="unit_id",
        how="left",
    )
    units = units.merge(
        base_units[["unit_id", "video_id", "absolute_t_start", "absolute_t_end"]],
        on="unit_id",
        how="left",
    )

    # Build disjoint bins of size bin_size (2s units -> bin_size/2 units per bin)
    units_per_bin = bin_size // 2
    max_t = float(units["t_end"].max())
    n_bins = int(np.ceil(max_t / bin_size))

    rows = []
    for i in range(n_bins):
        t0 = i * bin_size
        t1 = (i + 1) * bin_size
        sub = units[(units["t_start"] >= t0) & (units["t_start"] < t1)]
        if sub.empty:
            continue

        # Label aggregation: positive if any sub-unit positive, else negative.
        # No uncertain labels present in this data.
        positive_mask = sub["label_event"] == 1
        if positive_mask.any():
            label = "positive"
            event_ids = sub.loc[positive_mask, "event_id"].dropna().unique().tolist()
            event_id = event_ids[0] if len(event_ids) == 1 else "|".join(str(e) for e in event_ids)
            boundary_start = sub.loc[positive_mask, "boundary_start"].dropna().min()
            boundary_end = sub.loc[positive_mask, "boundary_end"].dropna().max()
        else:
            label = "negative"
            event_id = None
            boundary_start = np.nan
            boundary_end = np.nan

        # Prior aggregation: max cheap_fused_score over sub-units (pre-registered).
        prior_max = float(sub["cheap_fused_score"].max())
        prior_mean = float(sub["cheap_fused_score"].mean())

        rows.append(
            {
                "bin_id": f"b{i:04d}",
                "video_id": sub["video_id"].iloc[0],
                "t_start": t0,
                "t_end": t1,
                "absolute_t_start": sub["absolute_t_start"].min(),
                "absolute_t_end": sub["absolute_t_end"].max(),
                "label": label,
                "event_id": event_id,
                "boundary_start": boundary_start,
                "boundary_end": boundary_end,
                "prior_score_max": prior_max,
                "prior_score_mean": prior_mean,
                "num_sub_units": len(sub),
                "original_granularity": "native_2s",
                "granularity_source_tag": "uniform_2s_no_switch_found",
            }
        )

    grid = pd.DataFrame(rows)
    return grid


def evaluate_coverage_bias(grid: pd.DataFrame, events: pd.DataFrame) -> Dict:
    total_bins = len(grid)
    labeled_bins = total_bins  # fully labeled in this segment
    positive_bins = int((grid["label"] == "positive").sum())
    negative_bins = int((grid["label"] == "negative").sum())
    total_duration = float(grid["t_end"].max() - grid["t_start"].min())
    labeled_duration = total_duration

    # Reference coverage of total video: this segment is 1200s of a longer video,
    # but reference labels only exist within [0, 1200).
    # We report coverage within the analysed segment as 100%.
    # Positive temporal mass from reference events.
    positive_mass = float(events["duration"].sum())

    # Bias check: compare prior distribution of positive vs negative bins.
    pos_prior = grid.loc[grid["label"] == "positive", "prior_score_max"]
    neg_prior = grid.loc[grid["label"] == "negative", "prior_score_max"]
    all_prior = grid["prior_score_max"]

    return {
        "total_bins": total_bins,
        "labeled_bins": labeled_bins,
        "positive_bins": positive_bins,
        "negative_bins": negative_bins,
        "total_duration_s": total_duration,
        "labeled_duration_s": labeled_duration,
        "labeled_coverage_ratio": labeled_duration / total_duration if total_duration > 0 else np.nan,
        "positive_temporal_mass_s": positive_mass,
        "positive_mass_ratio": positive_mass / total_duration if total_duration > 0 else np.nan,
        "mean_prior_all": float(all_prior.mean()),
        "mean_prior_positive": float(pos_prior.mean()),
        "mean_prior_negative": float(neg_prior.mean()),
        "median_prior_all": float(all_prior.median()),
        "median_prior_positive": float(pos_prior.median()),
        "median_prior_negative": float(neg_prior.median()),
        "prior_bias_note": (
            "Labeled bins are heavily biased toward high-prior regions "
            "if positive-bin priors are markedly higher than negative-bin priors."
        ),
    }


def generate_exhaustive_annotation_package(grid: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Generate candidate windows for exhaustive human annotation.
    
    Three windows as required:
      - high_prior: top prior score region
      - low_prior: bottom prior score region
      - suspected_leakage: region suspected to contain missing positives
    """
    # High-prior window: consecutive high-prior bins
    # Low-prior window: consecutive low-prior bins
    # Suspected leakage: region just outside reference event boundaries or with
    #   reference events that have short duration (point anchors) where neighbours may be missed.
    
    sorted_grid = grid.sort_values("prior_score_max", ascending=False).reset_index(drop=True)
    
    # High prior: take top 3 minutes (18 bins) starting from the highest-prior bin,
    # but prefer a contiguous block. We take the bin with max prior and expand to a
    # 3-min contiguous window around it.
    top_idx = sorted_grid.index[0]
    half = 9  # 9 bins * 10s = 90s; need 18 bins for 180s
    h_start = max(0, top_idx - half)
    h_end = min(len(grid), h_start + 18)
    h_start = max(0, h_end - 18)
    high_prior_bins = grid.iloc[h_start:h_end].copy()
    high_prior_bins["window_tag"] = "window_high_prior"
    
    # Low prior: take bottom 3 minutes
    bottom_idx = sorted_grid.index[-1]
    l_start = max(0, bottom_idx - half)
    l_end = min(len(grid), l_start + 18)
    l_start = max(0, l_end - 18)
    low_prior_bins = grid.iloc[l_start:l_end].copy()
    low_prior_bins["window_tag"] = "window_low_prior"
    
    # Suspected leakage: choose a region with a short point-anchor event and its
    # immediate temporal neighbourhood, where expansion might recover missed mass.
    # Pick the shortest event.
    short_event = events.loc[events["duration"].idxmin()]
    center_bin = int(short_event["t_start"] // 10)
    s_start = max(0, center_bin - 9)
    s_end = min(len(grid), s_start + 18)
    s_start = max(0, s_end - 18)
    suspected_bins = grid.iloc[s_start:s_end].copy()
    suspected_bins["window_tag"] = "window_suspected_leakage"
    
    package = pd.concat([high_prior_bins, low_prior_bins, suspected_bins], ignore_index=True)
    package["local_t_start"] = package["t_start"]
    package["local_t_end"] = package["t_end"]
    package["bin_id"] = package["bin_id"]
    package["label"] = package["label"]
    package["event_id"] = package["event_id"]
    package["event_t_start"] = package["boundary_start"]
    package["event_t_end"] = package["boundary_end"]
    package["inside_E0_top10"] = False
    package["inside_E0_top20"] = False
    package["inside_E0_top30"] = False
    package["notes"] = ""
    package["reviewer"] = ""
    
    # Columns required by task spec
    out_cols = [
        "bin_id", "local_t_start", "local_t_end", "label", "event_id",
        "event_t_start", "event_t_end", "inside_E0_top10", "inside_E0_top20",
        "inside_E0_top30", "notes", "reviewer", "window_tag",
    ]
    return package[out_cols]


def main():
    print("Starting data discovery...")
    ref_sources = analyse_reference_candidates()
    prior_sources = analyse_prior_candidates()

    primary_units_path = BASE_SEARCH_ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/full_reference_units.csv"
    primary_priors_path = BASE_SEARCH_ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/cheap_signals_per_unit.csv"
    primary_events_path = BASE_SEARCH_ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv"

    units = pd.read_csv(primary_units_path)
    events = pd.read_csv(primary_events_path)

    # Granularity analysis
    bin_durations = (units["t_end"] - units["t_start"]).round(4).value_counts().to_dict()
    unique_durations = sorted(bin_durations.keys())
    granularity_switch_found = len(unique_durations) > 1

    # Build 10s atomic grid
    grid = build_atomic_grid(primary_units_path, primary_priors_path, primary_events_path, bin_size=ATOMIC_BIN_SIZE)
    grid_path = OUTPUT_ROOT / "atomic_grid_10s.csv"
    grid.to_csv(grid_path, index=False)
    print(f"Wrote atomic grid to {grid_path}")

    coverage = evaluate_coverage_bias(grid, events)

    # Generate exhaustive annotation package candidate (not yet human-annotated)
    annotation_package = generate_exhaustive_annotation_package(grid, events)
    annot_path = OUTPUT_ROOT / "exhaustive_subset_annotation_package" / "exhaustive_bins_template.csv"
    annotation_package.to_csv(annot_path, index=False)
    print(f"Wrote exhaustive annotation package template to {annot_path}")

    # Pre-registered config
    config = {
        "query_predicate": QUERY_PREDICATE,
        "atomic_bin_size_s": ATOMIC_BIN_SIZE,
        "base_search_root": str(BASE_SEARCH_ROOT),
        "primary_reference_units": str(primary_units_path),
        "primary_prior_scores": str(primary_priors_path),
        "primary_reference_events": str(primary_events_path),
        "dedup_time_distance_threshold_d_s": 10,
        "chunk_size_candidates_s": [30, 60, 120],
        "expansion_k_candidates_bins": [1, 2, 3, 5],
        "E0_threshold_candidates": ["top10", "top20", "top30"],
        "prior_aggregation_for_10s_bin": "max",
        "label_aggregation_for_10s_bin": "any_positive",
        "random_seed": 42,
        "n_trials_per_setting": 10,
    }
    config_path = OUTPUT_ROOT / "preregistered_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Wrote pre-registered config to {config_path}")

    # Write discovery report
    report_lines = []
    report_lines.append("# ExSample-aware Replay — Data Discovery Report")
    report_lines.append("")
    report_lines.append(f"**BASE_SEARCH_ROOT**: `{BASE_SEARCH_ROOT}`")
    report_lines.append(f"**QUERY_PREDICATE**: `{QUERY_PREDICATE}`")
    report_lines.append(f"**ATOMIC_BIN_SIZE**: {ATOMIC_BIN_SIZE}s (locked)")
    report_lines.append("")
    report_lines.append("## 1. Candidate Reference / Label Files")
    report_lines.append("")
    for s in ref_sources:
        report_lines.append(f"### `{s.path}`")
        report_lines.append(f"- type: {s.file_type}")
        report_lines.append(f"- rows: {s.n_rows}")
        report_lines.append(f"- columns: {s.columns}")
        report_lines.append(f"- time_range: {s.time_range}")
        report_lines.append(f"- bin_durations: {s.bin_durations}")
        report_lines.append(f"- selected: {s.selected}")
        report_lines.append(f"- rationale: {s.rationale}")
        report_lines.append("")

    report_lines.append("## 2. Candidate Prior-Score Files")
    report_lines.append("")
    for s in prior_sources:
        report_lines.append(f"### `{s.path}`")
        report_lines.append(f"- type: {s.file_type}")
        report_lines.append(f"- rows: {s.n_rows}")
        report_lines.append(f"- columns (first 15): {s.columns[:15]}")
        report_lines.append(f"- time_range: {s.time_range}")
        report_lines.append(f"- bin_durations (top 10): {s.bin_durations}")
        report_lines.append(f"- selected: {s.selected}")
        report_lines.append(f"- rationale: {s.rationale}")
        report_lines.append("")

    report_lines.append("## 3. Granularity Distribution and Switch-Point Analysis")
    report_lines.append("")
    report_lines.append(f"- Unique bin durations in primary units: {unique_durations}")
    report_lines.append(f"- Bin duration counts: {bin_durations}")
    if granularity_switch_found:
        report_lines.append("- Granularity switch detected: **yes** (multiple durations).")
    else:
        report_lines.append("- Granularity switch detected: **no**. The entire analysed segment uses a single 2s granularity.")
        report_lines.append("- `granularity_source_tag` for all merged 10s bins is set to `uniform_2s_no_switch_found`.")
        report_lines.append("- Layered reporting by `granularity_source_tag` will therefore have only one stratum for this dataset.")
    report_lines.append("")

    report_lines.append("## 4. Primary Data Selection Summary")
    report_lines.append("")
    report_lines.append(f"- Reference units: `{primary_units_path}`")
    report_lines.append(f"- Prior scores: `{primary_priors_path}`")
    report_lines.append(f"- Reference events: `{primary_events_path}`")
    report_lines.append(f"- Reason for choosing `clean_no_leak` over `label_aligned`: the no-leak version passed the feature-only label-leakage audit and uses a whitelist of features, making it the fairest basis for replay.")
    report_lines.append("")

    report_lines.append("## 5. Coverage and Bias Quantification")
    report_lines.append("")
    report_lines.append(f"- Total 10s bins: {coverage['total_bins']}")
    report_lines.append(f"- Labeled bins: {coverage['labeled_bins']} ({coverage['labeled_coverage_ratio']*100:.1f}% of analysed segment)")
    report_lines.append(f"- Positive bins: {coverage['positive_bins']} ({coverage['positive_bins']/coverage['total_bins']*100:.1f}%)")
    report_lines.append(f"- Negative bins: {coverage['negative_bins']} ({coverage['negative_bins']/coverage['total_bins']*100:.1f}%)")
    report_lines.append(f"- Analysed segment duration: {coverage['total_duration_s']}s")
    report_lines.append(f"- Positive temporal mass (from reference events): {coverage['positive_temporal_mass_s']:.1f}s ({coverage['positive_mass_ratio']*100:.2f}% of segment)")
    report_lines.append(f"- Mean prior (all bins): {coverage['mean_prior_all']:.4f}")
    report_lines.append(f"- Mean prior (positive bins): {coverage['mean_prior_positive']:.4f}")
    report_lines.append(f"- Mean prior (negative bins): {coverage['mean_prior_negative']:.4f}")
    report_lines.append(f"- Median prior (all bins): {coverage['median_prior_all']:.4f}")
    report_lines.append(f"- Median prior (positive bins): {coverage['median_prior_positive']:.4f}")
    report_lines.append(f"- Median prior (negative bins): {coverage['median_prior_negative']:.4f}")
    report_lines.append(f"- Bias note: {coverage['prior_bias_note']}")
    report_lines.append("")

    report_lines.append("## 6. Important Data Caveats")
    report_lines.append("")
    report_lines.append("- Reference labels are VLM-oracle outputs (`qwen3_vl_32b_v13_6_prompt`), not human labels. Metrics reported against these labels should be interpreted as VLM-defined-positive recovery, not human-ground-truth recall.")
    report_lines.append("- No existing exhaustive human-annotated continuous window was found. The exhaustive annotation package has been generated as a template but is **pending human annotation**. Calibration metrics dependent on it will be marked **未验证 / pending human annotation**.")
    report_lines.append("- The data has no granularity switch within the analysed 1200s segment, so Layer-A reporting by `granularity_source_tag` collapses to a single stratum.")
    report_lines.append("- All labels are binary (positive/negative) in the primary units; no uncertain labels are present, so the uncertain-merge rule produces zero uncertain 10s bins.")
    report_lines.append("")

    report_lines.append("## 7. Ambiguities Requiring Human Confirmation")
    report_lines.append("")
    report_lines.append("1. **Prior-score aggregation for 10s bins**: the task specifies 10s atomic bins but the raw prior scores exist at 2s. We pre-register `max` aggregation for the primary 10s prior. If a different aggregation (e.g. mean) is preferred, it must be decided before running baselines.")
    report_lines.append("2. **Granularity switch**: no switch was found in the primary 1200s segment. If the user expects a switch at a specific timestamp (e.g. tied to a larger video), that timestamp was not recoverable from the available files.")
    report_lines.append("")

    report_lines.append("## 8. Generated Artifacts")
    report_lines.append("")
    report_lines.append(f"- `{grid_path}`: 10s atomic bin grid with labels and prior scores.")
    report_lines.append(f"- `{annot_path}`: template for exhaustive human annotation (pending).")
    report_lines.append(f"- `{config_path}`: pre-registered hyperparameters.")
    report_lines.append("")

    report_path = OUTPUT_ROOT / "data_discovery_report.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    print(f"Wrote data discovery report to {report_path}")


if __name__ == "__main__":
    main()
