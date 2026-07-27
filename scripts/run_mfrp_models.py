#!/usr/bin/env python3
"""MFRP Phase 3: frozen 45-config nested complete-video model search."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error
from sklearn.preprocessing import StandardScaler

from run_mfrp_univariate import score_metrics


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/multi_fidelity_region_preview_v1"
SEARCH_BRANCHES = ("P1_L", "P1_M", "P2")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def branch_features(schema: pd.DataFrame, branch: str) -> list[str]:
    return list(schema[(schema.source_preview.eq(branch)) & schema.legality_status.eq("LEGAL")].feature_name)


def select_train_features(train: pd.DataFrame, schema: pd.DataFrame, branch: str) -> list[str]:
    candidates = []
    for feature in branch_features(schema, branch):
        values = train[feature].to_numpy(dtype=float)
        if np.nanstd(values) <= 1e-12:
            continue
        correlation = spearmanr(values, train.residual_event_count.to_numpy(dtype=float)).statistic
        orientation = 1 if not np.isfinite(correlation) or correlation >= 0 else -1
        metrics = score_metrics(train, orientation * values)
        family = str(schema.loc[schema.feature_name.eq(feature), "feature_family"].iloc[0])
        candidates.append({
            "feature": feature, "family": family,
            "train_recall_at_20": metrics["recall_at_20"],
            "train_auc": metrics["ranking_event_recall_auc"],
        })
    selected = []
    for _, group in pd.DataFrame(candidates).groupby("family", sort=True):
        top = group.sort_values(["train_recall_at_20", "train_auc", "feature"], ascending=[False, False, True]).head(2)
        selected.extend(top.feature)
    return sorted(selected)


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -30, 30)))


def fit_predict(config: dict, train: pd.DataFrame, target: pd.DataFrame,
                columns: list[str], *, shuffled_labels: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_train = train[columns].to_numpy(dtype=float)
    x_target = target[columns].to_numpy(dtype=float)
    scaler = StandardScaler().fit(x_train)
    x_train = scaler.transform(x_train); x_target = scaler.transform(x_target)
    y_count = train.residual_event_count.to_numpy(dtype=float)
    y_binary = train.binary_positive.astype(int).to_numpy()
    if shuffled_labels:
        permutation = np.random.default_rng(7042026).permutation(len(train))
        y_count = y_count[permutation]; y_binary = y_binary[permutation]
    family = config["family"]
    if family == "HEURISTIC_SCORE":
        signs = []
        for index in range(x_train.shape[1]):
            correlation = spearmanr(x_train[:, index], y_count).statistic
            signs.append(1.0 if not np.isfinite(correlation) or correlation >= 0 else -1.0)
        score = x_target @ np.asarray(signs) / max(np.sqrt(len(signs)), 1.0)
        probability = sigmoid(score)
        positive_mean = float(y_count[y_count > 0].mean()) if np.any(y_count > 0) else 0.0
        count_prediction = probability * positive_mean
    elif family == "LOGISTIC_REGRESSION":
        model = LogisticRegression(
            C=config["C"], class_weight=config["class_weight"], penalty="l2",
            solver="lbfgs", max_iter=3000, random_state=20260726,
        )
        model.fit(x_train, y_binary)
        probability = model.predict_proba(x_target)[:, 1]
        score = probability
        positive_mean = float(y_count[y_binary > 0].mean()) if np.any(y_binary > 0) else 0.0
        count_prediction = probability * positive_mean
    elif family == "POISSON_REGRESSION":
        model = PoissonRegressor(alpha=config["alpha"], max_iter=3000)
        model.fit(x_train, y_count)
        count_prediction = np.maximum(model.predict(x_target), 0.0)
        probability = 1.0 - np.exp(-count_prediction)
        score = count_prediction
    elif family == "SHALLOW_LIGHTGBM":
        model = LGBMRegressor(
            objective="poisson", max_depth=config["max_depth"], num_leaves=config["num_leaves"],
            min_child_samples=config["min_child_samples"], n_estimators=config["n_estimators"],
            learning_rate=config["learning_rate"], random_state=20260726,
            n_jobs=1, deterministic=True, force_col_wise=True, verbosity=-1,
        )
        model.fit(x_train, y_count)
        count_prediction = np.maximum(model.predict(x_target), 0.0)
        probability = 1.0 - np.exp(-count_prediction)
        score = count_prediction
    else:
        raise ValueError(family)
    return np.asarray(score), np.clip(np.asarray(probability), 0, 1), np.asarray(count_prediction)


def evaluate(frame: pd.DataFrame, score: np.ndarray, probability: np.ndarray,
             count_prediction: np.ndarray) -> dict:
    metrics = score_metrics(frame, score)
    metrics.update({
        "binary_brier_score": float(brier_score_loss(frame.binary_positive.astype(int), probability)),
        "count_mae": float(mean_absolute_error(frame.residual_event_count, count_prediction)),
    })
    drop_index = int(np.argmax(frame.residual_event_count.to_numpy()))
    reduced = frame.drop(index=drop_index).reset_index(drop=True)
    reduced_score = np.delete(score, drop_index)
    metrics["leave_best_region_out_recall_at_20"] = score_metrics(reduced, reduced_score)["recall_at_20"]
    metrics["dropped_best_region_id"] = str(frame.iloc[drop_index].region_id)
    metrics["dropped_best_region_event_count"] = int(frame.iloc[drop_index].residual_event_count)
    return metrics


def choose_train_config(rows: pd.DataFrame) -> pd.Series:
    ranked = rows.sort_values(["train_recall_at_20", "train_auc", "config_id"], ascending=[False, False, True])
    best = ranked.iloc[0]
    logistic = ranked[ranked.family.eq("LOGISTIC_REGRESSION")]
    if len(logistic):
        best_logistic = logistic.iloc[0]
        if float(best.train_recall_at_20) - float(best_logistic.train_recall_at_20) < 0.02:
            return best_logistic
    return best


def main() -> None:
    manifest = json.loads((OUT / "contracts/model_search_manifest.json").read_text())
    configs = manifest["configs"]
    assert len(configs) == 45
    regions = pd.read_parquet(OUT / "labels/region_table.parquet")
    features = pd.read_parquet(OUT / "features/region_features.parquet")
    schema = pd.read_csv(OUT / "audits/feature_legality_audit.csv")
    data = regions.merge(features, on=[
        "video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec",
    ], validate="one_to_one").sort_values(["video_id", "region_index"]).reset_index(drop=True)

    metric_rows, prediction_rows = [], []
    fold_features = {}
    for test_video in sorted(data.video_id.unique()):
        train = data[~data.video_id.eq(test_video)].sort_values("region_index").reset_index(drop=True)
        test = data[data.video_id.eq(test_video)].sort_values("region_index").reset_index(drop=True)
        for branch in SEARCH_BRANCHES:
            columns = select_train_features(train, schema, branch)
            fold_features[(test_video, branch)] = columns
            for config in [row for row in configs if row["preview"] == branch]:
                train_score, train_probability, train_count = fit_predict(config, train, train, columns)
                test_score, test_probability, test_count = fit_predict(config, train, test, columns)
                train_metrics = evaluate(train, train_score, train_probability, train_count)
                test_metrics = evaluate(test, test_score, test_probability, test_count)
                metric_rows.append({
                    "config_id": config["config_id"], "preview": branch, "family": config["family"],
                    "test_video_id": test_video, "train_video_id": str(train.video_id.iloc[0]),
                    "selected_feature_count": len(columns),
                    "selected_feature_schema_hash": hashlib.sha256("\n".join(columns).encode()).hexdigest(),
                    "train_recall_at_20": train_metrics["recall_at_20"],
                    "train_auc": train_metrics["ranking_event_recall_auc"],
                    **{f"test_{key}": value for key, value in test_metrics.items()},
                })
                for row, score, probability, count_prediction in zip(
                    test.itertuples(index=False), test_score, test_probability, test_count
                ):
                    prediction_rows.append({
                        "config_id": config["config_id"], "preview": branch,
                        "test_video_id": test_video, "region_id": row.region_id,
                        "score": float(score), "binary_probability": float(probability),
                        "count_prediction": float(count_prediction),
                    })
    metrics = pd.DataFrame(metric_rows)
    predictions = pd.DataFrame(prediction_rows)
    metrics.to_parquet(OUT / "experiments/models/all_45_config_nested_metrics.parquet", index=False)
    predictions.to_parquet(OUT / "predictions/all_45_config_nested_predictions.parquet", index=False)
    write_json(OUT / "experiments/models/nested_feature_selections.json", {
        f"test={test_video}|preview={branch}": {
            "features": columns, "feature_count": len(columns),
            "schema_hash": hashlib.sha256("\n".join(columns).encode()).hexdigest(),
        } for (test_video, branch), columns in fold_features.items()
    })

    selected_fold_rows = []
    nested_prediction_parts = []
    for (test_video, branch), group in metrics.groupby(["test_video_id", "preview"], sort=True):
        selected = choose_train_config(group)
        selected_fold_rows.append(selected.to_dict())
        nested_prediction_parts.append(
            predictions[(predictions.test_video_id.eq(test_video)) & predictions.preview.eq(branch) & predictions.config_id.eq(selected.config_id)]
        )
    selected_folds = pd.DataFrame(selected_fold_rows)
    nested_predictions = pd.concat(nested_prediction_parts, ignore_index=True)
    selected_folds.to_csv(OUT / "experiments/models/nested_selected_configs.csv", index=False)
    nested_predictions.to_parquet(OUT / "predictions/nested_lovo_predictions_all_branches.parquet", index=False)

    branch_rows = []
    for branch in SEARCH_BRANCHES:
        for video_id, truth in data.groupby("video_id", sort=True):
            truth = truth.sort_values("region_index").reset_index(drop=True)
            pred = nested_predictions[(nested_predictions.preview.eq(branch)) & nested_predictions.test_video_id.eq(video_id)].set_index("region_id").loc[truth.region_id]
            result = evaluate(
                truth, pred.score.to_numpy(), pred.binary_probability.to_numpy(), pred.count_prediction.to_numpy()
            )
            chosen = selected_folds[(selected_folds.preview.eq(branch)) & selected_folds.test_video_id.eq(video_id)].iloc[0]
            branch_rows.append({
                "preview": branch, "video_id": video_id,
                "fold_selected_config_id": chosen.config_id,
                "fold_selected_family": chosen.family, **result,
            })
    branch_metrics = pd.DataFrame(branch_rows)
    branch_metrics.to_csv(OUT / "metrics/nested_branch_per_video_metrics.csv", index=False)
    branch_summary = branch_metrics.groupby("preview", as_index=False).agg(
        min_video_recall_at_20=("recall_at_20", "min"),
        macro_recall_at_20=("recall_at_20", "mean"),
        min_video_auc=("ranking_event_recall_auc", "min"),
        macro_auc=("ranking_event_recall_auc", "mean"),
        max_brier=("binary_brier_score", "max"),
        macro_count_mae=("count_mae", "mean"),
        max_best_region_contribution=("best_region_contribution_ratio_at_20", "max"),
        min_leave_best_region_out_recall20=("leave_best_region_out_recall_at_20", "min"),
    ).sort_values(["min_video_recall_at_20", "macro_recall_at_20", "min_video_auc"], ascending=False)
    candidate_branch = str(branch_summary.iloc[0].preview)
    branch_summary["selected_exploratory_branch"] = branch_summary.preview.eq(candidate_branch)
    branch_summary.to_csv(OUT / "experiments/models/nested_branch_summary.csv", index=False)

    candidate_predictions = nested_predictions[nested_predictions.preview.eq(candidate_branch)].copy()
    candidate_predictions.to_parquet(OUT / "predictions/nested_lovo_predictions.parquet", index=False)
    candidate_predictions.to_parquet(OUT / "predictions/region_scores.parquet", index=False)

    # Mandatory B7 shuffled-label and B8 shuffled-score controls for the
    # strongest nested branch.  Config/schema remain the train-fold selections.
    shuffled_label_rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        train = data[~data.video_id.eq(video_id)].sort_values("region_index").reset_index(drop=True)
        test = truth.sort_values("region_index").reset_index(drop=True)
        selected_row = selected_folds[(selected_folds.preview.eq(candidate_branch)) & selected_folds.test_video_id.eq(video_id)].iloc[0]
        config = next(row for row in configs if row["config_id"] == selected_row.config_id)
        columns = fold_features[(video_id, candidate_branch)]
        score, probability, count_prediction = fit_predict(config, train, test, columns, shuffled_labels=True)
        shuffled_label_rows.append({
            "control": "B7_SHUFFLED_LABEL", "video_id": video_id,
            **evaluate(test, score, probability, count_prediction),
        })
    pd.DataFrame(shuffled_label_rows).to_csv(OUT / "experiments/controls/B7_SHUFFLED_LABEL.csv", index=False)
    shuffled_score_rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        base = candidate_predictions[candidate_predictions.test_video_id.eq(video_id)].set_index("region_id").loc[truth.region_id].score.to_numpy()
        for seed in range(100):
            shuffled = np.random.default_rng(seed).permutation(base)
            shuffled_score_rows.append({
                "control": "B8_SHUFFLED_REGION_SCORE", "video_id": video_id, "seed": seed,
                **score_metrics(truth, shuffled),
            })
    pd.DataFrame(shuffled_score_rows).to_csv(OUT / "experiments/controls/B8_SHUFFLED_REGION_SCORE_100_SEEDS.csv", index=False)

    # Family ablation reuses the selected fold model/config and removes each
    # selected family without hyperparameter reselection.
    ablation_rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        train = data[~data.video_id.eq(video_id)].sort_values("region_index").reset_index(drop=True)
        test = truth.sort_values("region_index").reset_index(drop=True)
        selected_row = selected_folds[(selected_folds.preview.eq(candidate_branch)) & selected_folds.test_video_id.eq(video_id)].iloc[0]
        config = next(row for row in configs if row["config_id"] == selected_row.config_id)
        columns = fold_features[(video_id, candidate_branch)]
        family_map = schema.set_index("feature_name").feature_family.to_dict()
        for omitted_family in sorted({family_map[column] for column in columns}):
            remaining = [column for column in columns if family_map[column] != omitted_family]
            if not remaining:
                continue
            score, probability, count_prediction = fit_predict(config, train, test, remaining)
            ablation_rows.append({
                "preview": candidate_branch, "video_id": video_id,
                "config_id": config["config_id"], "omitted_family": omitted_family,
                "remaining_feature_count": len(remaining),
                **evaluate(test, score, probability, count_prediction),
            })
    pd.DataFrame(ablation_rows).to_csv(OUT / "experiments/ablations/candidate_family_ablation.csv", index=False)

    write_json(OUT / "experiments/models/phase3_summary.json", {
        "search_manifest_hash": manifest["manifest_hash"],
        "config_count": len(configs), "model_family_count": len({row["family"] for row in configs}),
        "candidate_branch": candidate_branch,
        "branch_summary": branch_summary.to_dict("records"),
        "fold_selected_configs": selected_folds[[
            "preview", "test_video_id", "train_video_id", "config_id", "family",
            "selected_feature_count", "selected_feature_schema_hash",
        ]].to_dict("records"),
        "selection_scope": "TWO_DESIGN_VIDEOS_EXPLORATORY_NESTED_LOVO",
    })
    report = "# Simple Model Search Report\n\n" + branch_summary.to_markdown(index=False) + "\n\nAll 45 configurations were frozen before univariate metrics. Feature columns and hyperparameters are selected on the training video only for each complete-video fold.\n"
    (OUT / "reports/SIMPLE_MODEL_SEARCH_REPORT.md").write_text(report)
    ablation_summary = pd.DataFrame(ablation_rows).groupby(["omitted_family"], as_index=False).agg(
        min_recall20=("recall_at_20", "min"), macro_recall20=("recall_at_20", "mean")
    )
    (OUT / "reports/FEATURE_ABLATION_REPORT.md").write_text(
        "# Feature Ablation Report\n\n" + ablation_summary.to_markdown(index=False) + "\n"
    )
    print(json.dumps({
        "status": "PASS", "candidate_branch": candidate_branch,
        "branch_summary": branch_summary.to_dict("records"),
        "selected_folds": selected_folds[["preview", "test_video_id", "config_id", "family", "train_recall_at_20", "test_recall_at_20"]].to_dict("records"),
    }, indent=2))


if __name__ == "__main__":
    main()
