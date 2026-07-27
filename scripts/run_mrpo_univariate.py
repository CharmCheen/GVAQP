#!/usr/bin/env python3
"""MRPO Phase 2: legal univariate rankings and mandatory static controls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/macro_region_proxy_optimization_v1"
LENGTH = 40
BUDGETS = (0.10, 0.20, 0.30)
SEEDS = tuple(range(100))
FEATURE_FAMILIES = {
    "brightness_contrast": ["luma_mean", "luma_std"],
    "entropy_texture": ["entropy"],
    "edge_structure": ["edge_density"],
    "color_saturation": ["saturation_mean"],
    "frame_difference": ["frame_diff_mean"],
    "histogram_change": ["histogram_l1_change"],
    "spatial_center_border": ["center_border_contrast"],
    "sampling_support": ["preview_support_fraction", "preview_sample_count"],
}


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    tmp.replace(path)


def feature_family(column: str) -> str:
    for family, stems in FEATURE_FAMILIES.items():
        if any(column == stem or column.startswith(stem + "__") for stem in stems):
            return family
    raise KeyError(column)


def selected_indices(frame: pd.DataFrame, scores: np.ndarray, q: float) -> list[int]:
    budget = q * float(frame.full_scan_cost_sec.sum())
    order = np.argsort(-np.asarray(scores, dtype=float), kind="stable")
    chosen, spent = [], 0.0
    for position in order:
        cost = float(frame.iloc[position].full_scan_cost_sec)
        if spent + cost > budget + 1e-12:
            break
        chosen.append(int(position)); spent += cost
    return chosen


def recall(frame: pd.DataFrame, scores: np.ndarray, q: float) -> tuple[float, float, list[int]]:
    chosen = selected_indices(frame, scores, q)
    denominator = float(frame.residual_event_count.sum())
    numerator = float(frame.iloc[chosen].residual_event_count.sum()) if chosen else 0.0
    spent = float(frame.iloc[chosen].full_scan_cost_sec.sum()) if chosen else 0.0
    return numerator / denominator if denominator else 0.0, spent / float(frame.full_scan_cost_sec.sum()), chosen


def ranking_auc(frame: pd.DataFrame, scores: np.ndarray) -> float:
    grid = np.linspace(0.0, 1.0, 101)
    curve = [recall(frame, scores, float(q))[0] for q in grid]
    return float(np.trapezoid(curve, grid))


def score_metrics(frame: pd.DataFrame, scores: np.ndarray) -> dict:
    scores = np.nan_to_num(np.asarray(scores, dtype=float), nan=0.0, posinf=1e12, neginf=-1e12)
    output = {}
    for q in BUDGETS:
        value, spent, chosen = recall(frame, scores, q)
        output[f"recall_at_{int(q*100)}"] = value
        output[f"used_cost_fraction_at_{int(q*100)}"] = spent
        if q == 0.20:
            selected_counts = frame.iloc[chosen].residual_event_count.to_numpy(dtype=float) if chosen else np.array([])
            output["best_region_contribution_ratio_at_20"] = (
                float(selected_counts.max() / selected_counts.sum()) if selected_counts.sum() > 0 else 0.0
            )
    output["ranking_event_recall_auc"] = ranking_auc(frame, scores)
    output["spearman_count"] = float(pd.Series(scores).corr(frame.residual_event_count.reset_index(drop=True), method="spearman") or 0.0)
    binary = frame.binary_positive.astype(int).to_numpy()
    output["binary_auprc"] = float(average_precision_score(binary, scores)) if len(np.unique(binary)) > 1 else float(binary.mean())
    return output


def geometry_order_scores(frame: pd.DataFrame) -> np.ndarray:
    n = len(frame)
    remaining = set(range(n)); selected: list[int] = []
    # Pure geometry: recursively fill the largest uncovered interval, beginning
    # with both ends. This never observes preview features or labels.
    for anchor in (0, n - 1):
        if anchor in remaining:
            selected.append(anchor); remaining.remove(anchor)
    while remaining:
        candidate = max(
            remaining,
            key=lambda i: (min(abs(i - j) for j in selected), -i),
        )
        selected.append(candidate); remaining.remove(candidate)
    scores = np.empty(n, dtype=float)
    for rank, index in enumerate(selected):
        scores[index] = n - rank
    return scores


def evaluate_per_video(data: pd.DataFrame, scores: np.ndarray) -> dict:
    return {
        video_id: score_metrics(group.reset_index(drop=True), scores[group.index.to_numpy()])
        for video_id, group in data.groupby("video_id", sort=True)
    }


def main() -> None:
    features = pd.read_parquet(OUT / "preview/region_features/SELECTED.parquet")
    labels = pd.read_parquet(OUT / f"labels/candidates/region_labels_L{LENGTH:03d}.parquet")
    data = labels.merge(features, on=["video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec"], validate="one_to_one")
    data = data.sort_values(["video_id", "region_index"]).reset_index(drop=True)
    feature_columns = [
        c for c in features.columns
        if c not in {"operator_id", "video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec", "preview_expected_sample_count"}
    ]

    random_rows = []
    random_by_video: dict[str, dict] = {}
    for video_id, group in data.groupby("video_id", sort=True):
        group = group.reset_index(drop=True)
        seed_metrics = []
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            permutation = rng.permutation(len(group))
            scores = np.empty(len(group)); scores[permutation] = np.arange(len(group), 0, -1)
            metrics = score_metrics(group, scores)
            seed_metrics.append(metrics)
            random_rows.append({"video_id": video_id, "seed": seed, **metrics})
        random_by_video[video_id] = {
            key: float(np.mean([row[key] for row in seed_metrics])) for key in seed_metrics[0]
        }
        random_by_video[video_id].update({
            f"{key}_std": float(np.std([row[key] for row in seed_metrics], ddof=1)) for key in seed_metrics[0]
        })
    pd.DataFrame(random_rows).to_csv(OUT / "experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv", index=False)

    univariate_rows = []
    for column in feature_columns:
        raw = data[column].to_numpy(dtype=float)
        correlation = pd.Series(raw).corr(data.residual_event_count, method="spearman")
        orientation = 1 if pd.isna(correlation) or correlation >= 0 else -1
        oriented = orientation * raw
        for video_id, group in data.groupby("video_id", sort=True):
            metrics = score_metrics(group.reset_index(drop=True), oriented[group.index.to_numpy()])
            random20 = random_by_video[video_id]["recall_at_20"]
            univariate_rows.append({
                "feature": column, "feature_family": feature_family(column),
                "pooled_orientation": orientation, "video_id": video_id,
                "enrichment_at_20": metrics["recall_at_20"] / random20 if random20 else 0.0,
                **metrics,
            })
    univariate = pd.DataFrame(univariate_rows)
    summary = univariate.groupby(["feature", "feature_family", "pooled_orientation"], as_index=False).agg(
        macro_recall_at_20=("recall_at_20", "mean"),
        min_video_recall_at_20=("recall_at_20", "min"),
        macro_enrichment_at_20=("enrichment_at_20", "mean"),
        min_video_enrichment_at_20=("enrichment_at_20", "min"),
        macro_auc=("ranking_event_recall_auc", "mean"),
        min_video_spearman=("spearman_count", "min"),
    ).sort_values(["min_video_recall_at_20", "macro_recall_at_20", "macro_auc"], ascending=False)
    univariate.to_csv(OUT / "experiments/univariate/per_video_feature_metrics.csv", index=False)
    summary.to_csv(OUT / "experiments/univariate/feature_ranking.csv", index=False)

    controls = []
    control_scores = {
        "B1_CONSTANT_GLOBAL_RATE": np.ones(len(data)),
        "B2_REGION_COST_ONLY_LOW_FIRST": -data.full_scan_cost_sec.to_numpy(),
        "B3_TIME_INDEX_ONLY_EARLY_FIRST": -data.region_index.to_numpy(dtype=float),
        "B3_TIME_INDEX_ONLY_LATE_FIRST": data.region_index.to_numpy(dtype=float),
        "B8_OFFLINE_FULL_INFORMATION_DENSITY": data.residual_event_count.to_numpy() / data.full_scan_cost_sec.to_numpy(),
    }
    # Geometry is constructed independently inside each video.
    geometry = np.empty(len(data))
    for _, group in data.groupby("video_id", sort=True):
        geometry[group.index.to_numpy()] = geometry_order_scores(group.reset_index(drop=True))
    control_scores["B5_STRONGEST_GEOMETRIC_COVERAGE_REGION_ORDER"] = geometry
    for name, scores in control_scores.items():
        per_video = evaluate_per_video(data, scores)
        for video_id, metrics in per_video.items():
            controls.append({"control": name, "video_id": video_id, **metrics})
    controls_frame = pd.DataFrame(controls)
    controls_frame.to_csv(OUT / "experiments/controls/static_control_metrics.csv", index=False)

    chosen = summary.iloc[0].to_dict()
    best_rows = univariate[univariate.feature.eq(chosen["feature"])]
    phase = {
        "status": "PASS",
        "selected_macro_region_length_sec_for_stage_a": LENGTH,
        "selection_reason": "40s has the least saturated binary labels and greatest region sample size among frozen candidates",
        "partition_hash": hashlib.sha256("\n".join(labels.sort_values(["video_id", "region_index"]).region_id).encode()).hexdigest(),
        "feature_count": len(feature_columns), "feature_family_count": len(FEATURE_FAMILIES),
        "best_univariate_feature": chosen,
        "best_univariate_per_video": best_rows.to_dict("records"),
        "random_cost_matched_mean_per_video": random_by_video,
        "phase2_weak_signal_rule_triggered": bool(
            all((g.recall_at_20.max() < 0.30 and g.enrichment_at_20.max() < 1.5) for _, g in univariate.groupby("video_id"))
        ),
        "interpretation_scope": "DESIGN_VIDEO_EXPLORATION_ONLY",
    }
    dump_json(OUT / "metrics/phase2_univariate_summary.json", phase)
    print(json.dumps(phase, indent=2))


if __name__ == "__main__":
    main()
