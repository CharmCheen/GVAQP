#!/usr/bin/env python3
"""MFRP Phase 2: all legal univariates and B0-B6/B9 controls."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score

from run_mrpo_univariate import geometry_order_scores


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/multi_fidelity_region_preview_v1"
PREVIEW_BRANCHES = ("P0", "P1_L", "P1_M", "P2")
SEARCH_BRANCHES = ("P1_L", "P1_M", "P2")


def score_metrics(frame: pd.DataFrame, scores: np.ndarray) -> dict:
    """Vectorized frozen complete-region ranking metrics."""
    scores = np.nan_to_num(np.asarray(scores, dtype=float), nan=0.0, posinf=1e12, neginf=-1e12)
    costs = frame.full_scan_cost_sec.to_numpy(dtype=float)
    counts = frame.residual_event_count.to_numpy(dtype=float)
    binary = frame.binary_positive.astype(int).to_numpy()
    order = np.argsort(-scores, kind="stable")
    ordered_cost = costs[order]
    ordered_count = counts[order]
    cumulative_cost = np.cumsum(ordered_cost)
    cumulative_count = np.cumsum(ordered_count)
    total_cost = float(costs.sum()); total_count = float(counts.sum())

    def at(q: float) -> tuple[float, float, np.ndarray]:
        k = int(np.searchsorted(cumulative_cost, q * total_cost + 1e-12, side="right"))
        selected = order[:k]
        value = float(cumulative_count[k - 1] / total_count) if k and total_count else 0.0
        spent = float(cumulative_cost[k - 1] / total_cost) if k and total_cost else 0.0
        return value, spent, selected

    output = {}
    for q in (0.10, 0.20, 0.30):
        value, spent, selected = at(q)
        output[f"recall_at_{int(q*100)}"] = value
        output[f"used_cost_fraction_at_{int(q*100)}"] = spent
        if q == 0.20:
            selected_counts = counts[selected]
            output["best_region_contribution_ratio_at_20"] = float(selected_counts.max() / selected_counts.sum()) if selected_counts.sum() else 0.0
    grid = np.linspace(0.0, 1.0, 101)
    curve = [at(float(q))[0] for q in grid]
    output["ranking_event_recall_auc"] = float(np.trapezoid(curve, grid))
    correlation = spearmanr(scores, counts).statistic
    output["spearman_count"] = float(correlation) if np.isfinite(correlation) else 0.0
    output["binary_auprc"] = float(average_precision_score(binary, scores)) if len(np.unique(binary)) > 1 else float(binary.mean())
    return output


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def source_from_feature(feature: str) -> str:
    return feature.split("__", 1)[0].upper()


def orientation_and_metrics(frame: pd.DataFrame, feature: str) -> tuple[int, dict]:
    correlation = pd.Series(frame[feature]).corr(frame.residual_event_count, method="spearman")
    orientation = 1 if pd.isna(correlation) or correlation >= 0 else -1
    return orientation, score_metrics(frame, orientation * frame[feature].to_numpy(dtype=float))


def nested_best_feature(data: pd.DataFrame, features: list[str], random_means: dict[str, float], branch: str) -> list[dict]:
    rows = []
    branch_features = [feature for feature in features if source_from_feature(feature) == branch]
    for test_video in sorted(data.video_id.unique()):
        train = data[~data.video_id.eq(test_video)].sort_values("region_index").reset_index(drop=True)
        test = data[data.video_id.eq(test_video)].sort_values("region_index").reset_index(drop=True)
        candidates = []
        for feature in branch_features:
            orientation, metrics = orientation_and_metrics(train, feature)
            candidates.append({
                "feature": feature, "orientation": orientation,
                "train_recall_at_20": metrics["recall_at_20"],
                "train_auc": metrics["ranking_event_recall_auc"],
            })
        selected = max(candidates, key=lambda row: (
            row["train_recall_at_20"], row["train_auc"], row["feature"]
        ))
        test_metrics = score_metrics(test, selected["orientation"] * test[selected["feature"]].to_numpy(dtype=float))
        rows.append({
            "preview": branch, "train_video_id": str(train.video_id.iloc[0]),
            "test_video_id": test_video, "selected_feature": selected["feature"],
            "selected_orientation": selected["orientation"],
            "train_recall_at_20": selected["train_recall_at_20"],
            "test_recall_at_10": test_metrics["recall_at_10"],
            "test_recall_at_20": test_metrics["recall_at_20"],
            "test_recall_at_30": test_metrics["recall_at_30"],
            "test_auc": test_metrics["ranking_event_recall_auc"],
            "test_spearman": test_metrics["spearman_count"],
            "test_random_recall_at_20": random_means[test_video],
            "test_enrichment_at_20": test_metrics["recall_at_20"] / random_means[test_video],
            "test_delta_vs_random": test_metrics["recall_at_20"] - random_means[test_video],
        })
    return rows


def main() -> None:
    regions = pd.read_parquet(OUT / "labels/region_table.parquet")
    features = pd.read_parquet(OUT / "features/region_features.parquet")
    schema = pd.read_csv(OUT / "audits/feature_legality_audit.csv")
    legal_features = list(schema.loc[schema.legality_status.eq("LEGAL"), "feature_name"])
    data = regions.merge(features, on=[
        "video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec",
    ], validate="one_to_one").sort_values(["video_id", "region_index"]).reset_index(drop=True)

    random_rows = []
    random_means = {}
    for video_id, group in data.groupby("video_id", sort=True):
        group = group.reset_index(drop=True)
        values = []
        for seed in range(100):
            permutation = np.random.default_rng(seed).permutation(len(group))
            scores = np.empty(len(group), dtype=float)
            scores[permutation] = np.arange(len(group), 0, -1)
            metrics = score_metrics(group, scores)
            random_rows.append({"control": "B0_RANDOM_COST_MATCHED", "video_id": video_id, "seed": seed, **metrics})
            values.append(metrics["recall_at_20"])
        random_means[video_id] = float(np.mean(values))
    random_frame = pd.DataFrame(random_rows)
    random_frame.to_csv(OUT / "experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv", index=False)
    write_json(OUT / "metrics/random_baseline_distribution.json", {
        video_id: {
            "seed_count": len(group), "mean_recall_at_20": float(group.recall_at_20.mean()),
            "std_recall_at_20": float(group.recall_at_20.std(ddof=1)),
            "q05": float(group.recall_at_20.quantile(0.05)),
            "median": float(group.recall_at_20.median()),
            "q95": float(group.recall_at_20.quantile(0.95)),
        } for video_id, group in random_frame.groupby("video_id")
    })

    univariate_rows = []
    for feature in legal_features:
        source = source_from_feature(feature)
        cost_ratio = float(schema.loc[schema.feature_name.eq(feature), "cost"].iloc[0])
        pooled_correlation = pd.Series(data[feature]).corr(data.residual_event_count, method="spearman")
        pooled_orientation = 1 if pd.isna(pooled_correlation) or pooled_correlation >= 0 else -1
        for video_id, group in data.groupby("video_id", sort=True):
            group = group.reset_index(drop=True)
            metrics = score_metrics(group, pooled_orientation * group[feature].to_numpy(dtype=float))
            univariate_rows.append({
                "feature": feature, "source_preview": source,
                "feature_family": schema.loc[schema.feature_name.eq(feature), "feature_family"].iloc[0],
                "pooled_orientation": pooled_orientation, "video_id": video_id,
                "preview_cost_ratio": cost_ratio,
                "enrichment_at_20": metrics["recall_at_20"] / random_means[video_id],
                "delta_vs_random_at_20": metrics["recall_at_20"] - random_means[video_id],
                **metrics,
            })
    univariate = pd.DataFrame(univariate_rows)
    univariate.to_parquet(OUT / "experiments/univariate/all_feature_per_video_metrics.parquet", index=False)
    summary = univariate.groupby(
        ["feature", "source_preview", "feature_family", "pooled_orientation", "preview_cost_ratio"], as_index=False
    ).agg(
        min_video_recall_at_20=("recall_at_20", "min"),
        macro_recall_at_20=("recall_at_20", "mean"),
        min_video_enrichment_at_20=("enrichment_at_20", "min"),
        macro_enrichment_at_20=("enrichment_at_20", "mean"),
        macro_auc=("ranking_event_recall_auc", "mean"),
        min_video_auc=("ranking_event_recall_auc", "min"),
        min_video_spearman=("spearman_count", "min"),
    ).sort_values(["min_video_recall_at_20", "macro_recall_at_20", "macro_auc"], ascending=False)
    summary.to_csv(OUT / "experiments/univariate/feature_ranking.csv", index=False)

    nested_rows = []
    for branch in SEARCH_BRANCHES:
        nested_rows.extend(nested_best_feature(data, legal_features, random_means, branch))
    nested = pd.DataFrame(nested_rows)
    nested.to_csv(OUT / "experiments/univariate/nested_lovo_best_univariate.csv", index=False)

    # Nested macro-length selection uses only the training video and the frozen
    # non-saturation rule. Both folds independently select 40 s.
    sensitivity = pd.read_csv(OUT / "experiments/macro_region_sensitivity/label_sensitivity.csv")
    nested_lengths = []
    for test_video in sorted(data.video_id.unique()):
        train_video = str(data.loc[~data.video_id.eq(test_video), "video_id"].iloc[0])
        local = sensitivity[sensitivity.video_id.eq(train_video)].sort_values(
            ["binary_positive_region_rate", "region_count"], ascending=[True, False]
        )
        nested_lengths.append({
            "train_video_id": train_video, "test_video_id": test_video,
            "selected_macro_region_length_sec": int(local.iloc[0].macro_region_length_sec),
        })
    write_json(OUT / "experiments/macro_region_sensitivity/nested_length_selection.json", {
        "rule": "TRAIN_VIDEO_LEAST_LABEL_SATURATION_THEN_MAX_REGION_COUNT",
        "folds": nested_lengths,
        "all_folds_match_frozen_40s": all(row["selected_macro_region_length_sec"] == 40 for row in nested_lengths),
    })

    # Mandatory controls whose scores do not depend on a trained model.
    best_preview = summary[summary.source_preview.isin(SEARCH_BRANCHES)].iloc[0]
    best_preview_score = int(best_preview.pooled_orientation) * data[best_preview.feature].to_numpy(dtype=float)
    control_scores = {
        "B1_CONSTANT_GLOBAL_RATE": np.ones(len(data)),
        "B2_REGION_COST_ONLY": -data.full_scan_cost_sec.to_numpy(dtype=float),
        "B3_TIME_INDEX_ONLY_EARLY": -data.region_index.to_numpy(dtype=float),
        "B3_TIME_INDEX_ONLY_LATE": data.region_index.to_numpy(dtype=float),
        "B4_BEST_P0_FRAMESTAT": -data["p0__luma_std__std"].to_numpy(dtype=float),
        "B5_BEST_UNIVARIATE_PREVIEW_FEATURE": best_preview_score,
        "B9_OFFLINE_FULL_INFORMATION_REGION_ORDER": data.residual_event_count.to_numpy(dtype=float) / data.full_scan_cost_sec.to_numpy(dtype=float),
    }
    geometry = np.empty(len(data), dtype=float)
    for _, group in data.groupby("video_id", sort=True):
        geometry[group.index.to_numpy()] = geometry_order_scores(group.reset_index(drop=True))
    control_scores["B6_STRONGEST_GEOMETRIC_COVERAGE_REGION_ORDER"] = geometry
    control_rows = []
    for control, scores in control_scores.items():
        for video_id, group in data.groupby("video_id", sort=True):
            metrics = score_metrics(group.reset_index(drop=True), scores[group.index.to_numpy()])
            control_rows.append({"control": control, "video_id": video_id, **metrics})
    pd.DataFrame(control_rows).to_csv(OUT / "experiments/controls/static_control_metrics.csv", index=False)
    write_json(OUT / "experiments/univariate/phase2_summary.json", {
        "feature_count": len(legal_features), "p0_features_evaluated_for_reproducibility_not_retuned": True,
        "best_non_p0_design_univariate": best_preview.to_dict(),
        "nested_best_per_branch": nested.to_dict("records"),
        "all_non_p0_single_features_below_recall_0_40_on_at_least_one_video": bool(
            summary[summary.source_preview.isin(SEARCH_BRANCHES)].min_video_recall_at_20.lt(0.40).all()
        ),
        "simple_combination_still_allowed": True,
    })
    top = summary.groupby("source_preview", sort=True).head(1)[
        ["source_preview", "feature", "min_video_recall_at_20", "macro_recall_at_20", "macro_auc"]
    ]
    report = "# Univariate Headroom Report\n\n" + top.to_markdown(index=False) + "\n\nNested train-video-only selections are in `nested_lovo_best_univariate.csv`. P0 metrics are reproduced only as a frozen baseline and are not used to reopen P0 tuning.\n"
    (OUT / "reports/UNIVARIATE_HEADROOM_REPORT.md").write_text(report)
    print(json.dumps({
        "status": "PASS", "feature_count": len(legal_features),
        "top_by_source": top.to_dict("records"),
        "nested": nested.to_dict("records"),
    }, indent=2))


if __name__ == "__main__":
    main()
