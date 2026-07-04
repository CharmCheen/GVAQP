#!/usr/bin/env python3
"""Run a minimal AQP selector/budget smoke test from existing artifacts only.

This script is intentionally diagnostic. It does not run VLM, YOLO, GPU
training, threshold fitting, or probe-label tuning. Selector definitions are
fixed in code and the outputs should be read as a Phase 3 smoke test of the
cheap-signal -> candidate ranking -> overlap-constrained return-set loop.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


REPO = Path(__file__).resolve().parents[2]
DEFAULT_FEATURES = REPO / "outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv"
DEFAULT_REFERENCE = (
    REPO
    / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv"
)
DEFAULT_OUT = REPO / "outputs/agent_loop_v1/phase3_selector_smoke_v1"

BUDGETS = [5, 10, 20, 40]
NMS_IOU_THRESHOLD = 0.5
UNIFORM_SEEDS = list(range(50))


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    direction: str


SELECTOR_SPECS: dict[str, list[FeatureSpec]] = {
    "existing_signal": [FeatureSpec("motion_energy_mean", "asc")],
    "track_interaction": [
        FeatureSpec("track_mean_track_speed_mean", "asc"),
        FeatureSpec("track_mean_relative_speed_mean", "asc"),
    ],
    "inside_outside": [
        FeatureSpec("contrast_optical_flow_burst_z_max", "asc"),
        FeatureSpec("contrast_object_density_change_z_min", "desc"),
        FeatureSpec("contrast_optical_flow_burst_z_mean", "asc"),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--reference-events", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def require_columns(df: pd.DataFrame, columns: Iterable[str], path: Path) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def percentile_oriented_score(series: pd.Series, direction: str) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if direction == "asc":
        values = -values
    elif direction != "desc":
        raise ValueError(f"Unknown ranking direction: {direction}")

    ranks = values.rank(method="average", pct=True, na_option="keep")
    return ranks.astype(float)


def composite_score(df: pd.DataFrame, specs: list[FeatureSpec]) -> pd.Series:
    parts = []
    for spec in specs:
        if spec.name not in df.columns:
            raise ValueError(f"Missing feature for selector: {spec.name}")
        parts.append(percentile_oriented_score(df[spec.name], spec.direction))

    stacked = pd.concat(parts, axis=1)
    return stacked.mean(axis=1, skipna=True)


def add_selector_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for selector, specs in SELECTOR_SPECS.items():
        out[f"score__{selector}"] = composite_score(out, specs)

    fused_parts = [
        out["score__existing_signal"],
        out["score__track_interaction"],
        out["score__inside_outside"],
    ]
    out["score__simple_fused"] = pd.concat(fused_parts, axis=1).mean(axis=1, skipna=True)
    return out


def interval_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    overlap = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return overlap / union


def greedy_nms_select(
    scored: pd.DataFrame,
    budget: int,
    selector: str,
    seed: int | None = None,
    use_overlap_group_cap: bool = False,
) -> pd.DataFrame:
    score_col = f"score__{selector}"
    work = scored.copy()

    if selector == "uniform_random":
        if seed is None:
            raise ValueError("uniform_random requires a seed")
        rng = np.random.default_rng(seed)
        work[score_col] = rng.random(len(work))

    work = work[np.isfinite(work[score_col])].copy()
    work = work.sort_values(
        [score_col, "t_start", "duration", "interval_id"],
        ascending=[False, True, True, True],
        kind="mergesort",
    )

    selected_rows = []
    used_overlap_groups = set()
    for row in work.itertuples(index=False):
        group = getattr(row, "overlap_group_id", None)
        if use_overlap_group_cap and pd.notna(group) and group in used_overlap_groups:
            continue

        overlaps_existing = False
        for kept in selected_rows:
            iou = interval_iou(row.t_start, row.t_end, kept.t_start, kept.t_end)
            if iou > NMS_IOU_THRESHOLD:
                overlaps_existing = True
                break
        if overlaps_existing:
            continue

        selected_rows.append(row)
        if use_overlap_group_cap and pd.notna(group):
            used_overlap_groups.add(group)
        if len(selected_rows) >= budget:
            break

    selected = pd.DataFrame(selected_rows)
    if selected.empty:
        return selected
    selected = selected.copy()
    selected["rank_after_nms"] = np.arange(1, len(selected) + 1)
    selected["selector"] = selector
    selected["budget"] = budget
    selected["seed"] = -1 if seed is None else seed
    selected["selector_score"] = selected[score_col]
    return selected


def event_interval_overlap(row: pd.Series, event: pd.Series) -> dict[str, float | bool]:
    iou = interval_iou(row["t_start"], row["t_end"], event["t_start"], event["t_end"])
    overlap = max(0.0, min(row["t_end"], event["t_end"]) - max(row["t_start"], event["t_start"]))
    event_center = (event["t_start"] + event["t_end"]) / 2.0
    interval_contains_event_center = row["t_start"] <= event_center <= row["t_end"]
    return {
        "event_iou": iou,
        "event_overlap_seconds": overlap,
        "center_hit": interval_contains_event_center,
        "any_overlap": overlap > 0,
    }


def annotate_selected(selected: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return selected

    rows = []
    for _, row in selected.iterrows():
        best = {
            "matched_event_id": "",
            "best_event_iou": 0.0,
            "best_event_overlap_seconds": 0.0,
            "best_event_center_hit": False,
            "best_event_any_overlap": False,
        }
        for _, event in events.iterrows():
            overlap = event_interval_overlap(row, event)
            if overlap["event_iou"] > best["best_event_iou"]:
                best = {
                    "matched_event_id": event["event_id"],
                    "best_event_iou": overlap["event_iou"],
                    "best_event_overlap_seconds": overlap["event_overlap_seconds"],
                    "best_event_center_hit": overlap["center_hit"],
                    "best_event_any_overlap": overlap["any_overlap"],
                }
        merged = row.to_dict()
        merged.update(best)
        merged["interval_positive_iou_0_3"] = best["best_event_iou"] >= 0.3
        merged["interval_positive_iou_0_5"] = best["best_event_iou"] >= 0.5
        rows.append(merged)
    return pd.DataFrame(rows)


def selected_background_duration(selected: pd.DataFrame, events: pd.DataFrame) -> float:
    if selected.empty:
        return 0.0
    background = 0.0
    for _, row in selected.iterrows():
        duration = max(0.0, row["t_end"] - row["t_start"])
        covered = 0.0
        for _, event in events.iterrows():
            covered += max(0.0, min(row["t_end"], event["t_end"]) - max(row["t_start"], event["t_start"]))
        background += max(0.0, duration - min(duration, covered))
    return background


def event_coverage_rows(
    selector: str,
    budget: int,
    seed: int,
    selected: pd.DataFrame,
    events: pd.DataFrame,
) -> list[dict[str, object]]:
    rows = []
    for _, event in events.iterrows():
        best_iou = 0.0
        best_interval_id = ""
        any_overlap = False
        center_hit = False
        for _, row in selected.iterrows():
            overlap = event_interval_overlap(row, event)
            if overlap["any_overlap"]:
                any_overlap = True
            if overlap["center_hit"]:
                center_hit = True
            if overlap["event_iou"] > best_iou:
                best_iou = float(overlap["event_iou"])
                best_interval_id = row["interval_id"]
        rows.append(
            {
                "selector": selector,
                "budget": budget,
                "seed": seed,
                "event_id": event["event_id"],
                "event_t_start": event["t_start"],
                "event_t_end": event["t_end"],
                "best_interval_id": best_interval_id,
                "best_iou": best_iou,
                "covered_iou_0_3": best_iou >= 0.3,
                "covered_iou_0_5": best_iou >= 0.5,
                "any_overlap": any_overlap,
                "center_hit": center_hit,
            }
        )
    return rows


def summarize_run(
    selector: str,
    budget: int,
    seed: int,
    selected: pd.DataFrame,
    annotated: pd.DataFrame,
    events: pd.DataFrame,
) -> dict[str, object]:
    returned = len(selected)
    total_duration = float((selected["t_end"] - selected["t_start"]).sum()) if returned else 0.0
    background = selected_background_duration(selected, events)

    event_rows = event_coverage_rows(selector, budget, seed, selected, events)
    event_df = pd.DataFrame(event_rows)
    matched_positive = annotated[annotated["interval_positive_iou_0_3"]] if not annotated.empty else pd.DataFrame()
    duplicate_fraction = 0.0
    if returned and not matched_positive.empty:
        duplicate_count = int(matched_positive.duplicated("matched_event_id").sum())
        duplicate_fraction = duplicate_count / returned

    return {
        "selector": selector,
        "budget": budget,
        "seed": seed,
        "candidate_count": len(selected) if selected.empty else int(selected.attrs.get("candidate_count", len(selected))),
        "returned_count": returned,
        "budget_utilization": returned / budget if budget else 0.0,
        "event_count": len(events),
        "event_recall_iou_0_3": float(event_df["covered_iou_0_3"].mean()),
        "event_recall_iou_0_5": float(event_df["covered_iou_0_5"].mean()),
        "event_recall_any_overlap": float(event_df["any_overlap"].mean()),
        "event_center_recall": float(event_df["center_hit"].mean()),
        "interval_precision_iou_0_3": float(annotated["interval_positive_iou_0_3"].mean()) if returned else 0.0,
        "interval_precision_iou_0_5": float(annotated["interval_positive_iou_0_5"].mean()) if returned else 0.0,
        "avg_returned_duration": total_duration / returned if returned else 0.0,
        "total_returned_duration": total_duration,
        "background_duration_ratio": background / total_duration if total_duration else 0.0,
        "duplicate_interval_fraction_iou_0_3": duplicate_fraction,
    }


def aggregate_metrics(by_seed: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "returned_count",
        "budget_utilization",
        "event_recall_iou_0_3",
        "event_recall_iou_0_5",
        "event_recall_any_overlap",
        "event_center_recall",
        "interval_precision_iou_0_3",
        "interval_precision_iou_0_5",
        "avg_returned_duration",
        "total_returned_duration",
        "background_duration_ratio",
        "duplicate_interval_fraction_iou_0_3",
    ]

    rows = []
    for (selector, budget), group in by_seed.groupby(["selector", "budget"], sort=True):
        row = {
            "selector": selector,
            "budget": budget,
            "n_seeds": int(group["seed"].nunique()),
            "candidate_count": int(group["candidate_count"].iloc[0]),
            "event_count": int(group["event_count"].iloc[0]),
            "reference_scope": "clean_interval_aqp_full_reference_v2_label_aligned",
            "interpretation": "diagnostic_design_target_smoke",
        }
        for metric in metrics:
            row[f"{metric}_mean"] = float(group[metric].mean())
            row[f"{metric}_std"] = float(group[metric].std(ddof=0))
            row[f"{metric}_min"] = float(group[metric].min())
            row[f"{metric}_max"] = float(group[metric].max())
        rows.append(row)
    return pd.DataFrame(rows)


def write_report(
    out_dir: Path,
    summary: pd.DataFrame,
    selector_defs: dict[str, list[FeatureSpec]],
    feature_path: Path,
    reference_path: Path,
    overlap_group_cap_enabled: bool,
) -> None:
    best_budget40 = summary[summary["budget"] == 40].sort_values(
        "event_recall_iou_0_3_mean", ascending=False
    )
    lines = [
        "# Phase 3 Minimal AQP Selector Smoke",
        "",
        "This is a diagnostic smoke test of the AQP algorithm loop: candidate lattice -> fixed selector scoring -> overlap-constrained return set -> event coverage metrics.",
        "",
        "It used existing CSV artifacts only. It did not run VLM, YOLO, GPU training, API calls, threshold fitting, or probe-label tuning.",
        "",
        "## Inputs",
        "",
        f"- Candidate/features: `{feature_path.relative_to(REPO)}`",
        f"- Reference events: `{reference_path.relative_to(REPO)}`",
        "- Reference interpretation: `diagnostic_design_target_smoke`",
        f"- Budgets: `{BUDGETS}`",
        f"- NMS interval IoU threshold: `{NMS_IOU_THRESHOLD}`",
        f"- Overlap group cap enabled: `{overlap_group_cap_enabled}`",
        "- Uniform baseline seeds: `0..49`; non-random selectors are deterministic.",
        "",
        "## Fixed Selector Definitions",
        "",
        "- `uniform_random`: deterministic random score per seed.",
    ]
    for selector, specs in selector_defs.items():
        spec_text = ", ".join(f"{s.name}:{s.direction}" for s in specs)
        lines.append(f"- `{selector}`: mean percentile rank of `{spec_text}`.")
    lines.append("- `simple_fused`: mean of existing_signal, track_interaction, and inside_outside selector scores.")
    lines.extend(
        [
            "",
            "## Budget 40 Snapshot",
            "",
            "| selector | event_recall_iou_0_3 | event_recall_iou_0_5 | interval_precision_iou_0_3 | returned_count | background_duration_ratio |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in best_budget40.iterrows():
        lines.append(
            "| {selector} | {r03:.3f} | {r05:.3f} | {p03:.3f} | {ret:.1f} | {bg:.3f} |".format(
                selector=row["selector"],
                r03=row["event_recall_iou_0_3_mean"],
                r05=row["event_recall_iou_0_5_mean"],
                p03=row["interval_precision_iou_0_3_mean"],
                ret=row["returned_count_mean"],
                bg=row["background_duration_ratio_mean"],
            )
        )

    deterministic_b40 = best_budget40[best_budget40["selector"] != "uniform_random"]
    best_deterministic = deterministic_b40.iloc[0] if not deterministic_b40.empty else None
    uniform_b40 = best_budget40[best_budget40["selector"] == "uniform_random"]
    uniform_r03 = float(uniform_b40["event_recall_iou_0_3_mean"].iloc[0]) if not uniform_b40.empty else float("nan")
    best_det_r03 = (
        float(best_deterministic["event_recall_iou_0_3_mean"])
        if best_deterministic is not None
        else float("nan")
    )
    lines.extend(
        [
            "",
            "## Observed Smoke Outcome",
            "",
            f"- At B=40, the uniform random baseline mean event recall at IoU@0.3 was `{uniform_r03:.3f}` across 50 seeds.",
            f"- The best deterministic cheap-signal selector event recall at IoU@0.3 was `{best_det_r03:.3f}`.",
            "- In this smoke, the current fixed cheap-signal selectors did not convert signal-level diagnostics into better budgeted return-set coverage.",
            "- This is a negative Phase 3 result and should drive selector/return-set redesign before any stronger AQP claim.",
            "",
            "## Reading Rules",
            "",
            "- These numbers show whether the AQP loop can produce budgeted interval sets from current cheap signals.",
            "- They do not establish selector superiority because the reference scope is small and design-linked.",
            "- Probe_set_v1 remains a separate VLM-oracle-relative signal diagnostic; it was not used to define these selectors.",
            "- A production AQP variant should next replace greedy NMS with a declared weighted interval scheduling objective if the precision/overlap constraints need exact optimization.",
        ]
    )
    (out_dir / "phase3_selector_smoke_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    features = pd.read_csv(args.features)
    events = pd.read_csv(args.reference_events)
    require_columns(
        features,
        ["interval_id", "t_start", "t_end", "duration", "overlap_group_id"],
        args.features,
    )
    require_columns(events, ["event_id", "t_start", "t_end"], args.reference_events)

    scored = add_selector_scores(features)
    selectors = ["uniform_random", "existing_signal", "track_interaction", "inside_outside", "simple_fused"]
    usable_overlap_group_cap = "overlap_group_id" in scored and scored["overlap_group_id"].nunique(dropna=True) > 1

    all_selected = []
    all_coverage = []
    metric_rows = []
    for selector in selectors:
        seeds = UNIFORM_SEEDS if selector == "uniform_random" else [-1]
        for budget in BUDGETS:
            for seed in seeds:
                selected = greedy_nms_select(
                    scored,
                    budget,
                    selector,
                    seed=None if seed == -1 else seed,
                    use_overlap_group_cap=usable_overlap_group_cap,
                )
                selected.attrs["candidate_count"] = int(len(scored))
                annotated = annotate_selected(selected, events)
                if not annotated.empty:
                    all_selected.append(annotated)
                all_coverage.extend(event_coverage_rows(selector, budget, seed, selected, events))
                metric_rows.append(summarize_run(selector, budget, seed, selected, annotated, events))

    by_seed = pd.DataFrame(metric_rows)
    summary = aggregate_metrics(by_seed)
    selected_df = pd.concat(all_selected, ignore_index=True) if all_selected else pd.DataFrame()
    coverage_df = pd.DataFrame(all_coverage)

    by_seed.to_csv(args.out_dir / "selector_budget_metrics_by_seed.csv", index=False)
    summary.to_csv(args.out_dir / "selector_budget_summary.csv", index=False)
    selected_df.to_csv(args.out_dir / "selected_intervals.csv", index=False)
    coverage_df.to_csv(args.out_dir / "event_coverage.csv", index=False)

    config = {
        "features": str(args.features.relative_to(REPO)),
        "reference_events": str(args.reference_events.relative_to(REPO)),
        "budgets": BUDGETS,
        "nms_iou_threshold": NMS_IOU_THRESHOLD,
        "overlap_group_cap_enabled": bool(usable_overlap_group_cap),
        "uniform_seeds": UNIFORM_SEEDS,
        "selector_specs": {
            k: [{"feature": s.name, "direction": s.direction} for s in v]
            for k, v in SELECTOR_SPECS.items()
        },
        "simple_fused": ["existing_signal", "track_interaction", "inside_outside"],
        "interpretation": "diagnostic_design_target_smoke",
    }
    (args.out_dir / "run_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    write_report(
        args.out_dir,
        summary,
        SELECTOR_SPECS,
        args.features,
        args.reference_events,
        usable_overlap_group_cap,
    )

    with (args.out_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["artifact", "description"])
        writer.writeheader()
        writer.writerow({"artifact": "selector_budget_metrics_by_seed.csv", "description": "Per-seed selector/budget metrics."})
        writer.writerow({"artifact": "selector_budget_summary.csv", "description": "Aggregated selector/budget metrics."})
        writer.writerow({"artifact": "selected_intervals.csv", "description": "Returned intervals after greedy NMS."})
        writer.writerow({"artifact": "event_coverage.csv", "description": "Per-event coverage by returned sets."})
        writer.writerow({"artifact": "phase3_selector_smoke_report.md", "description": "Human-readable diagnostic report."})
        writer.writerow({"artifact": "run_config.json", "description": "Fixed selector and run configuration."})

    print(f"Wrote Phase 3 selector smoke outputs to {args.out_dir}")


if __name__ == "__main__":
    main()
