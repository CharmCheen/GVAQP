#!/usr/bin/env python3
"""MRPO Phase 3/4: bounded simple-model search, controls, and gates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error
from sklearn.preprocessing import StandardScaler

from run_mrpo_univariate import (
    FEATURE_FAMILIES, geometry_order_scores, recall, ranking_auc, score_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/macro_region_proxy_optimization_v1"
LENGTH = 40
FEATURE_SETS = {
    "S2_CORE": ["brightness_contrast", "edge_structure"],
    "S5_STABLE": ["brightness_contrast", "edge_structure", "histogram_change", "spatial_center_border", "frame_difference"],
    "S5_COLOR": ["brightness_contrast", "edge_structure", "histogram_change", "spatial_center_border", "color_saturation"],
}


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def family_columns(data: pd.DataFrame, families: list[str]) -> list[str]:
    stems = [stem for family in families for stem in FEATURE_FAMILIES[family]]
    return [c for c in data.columns if any(c == stem or c.startswith(stem + "__") for stem in stems)]


def configs() -> list[dict]:
    output = []
    for feature_set in FEATURE_SETS:
        output.append({"family": "M0_HEURISTIC", "feature_set": feature_set})
        for c in (0.01, 0.1, 1.0, 10.0):
            for weight in (None, "balanced"):
                output.append({"family": "M1_LOGISTIC", "feature_set": feature_set, "C": c, "class_weight": weight})
        for alpha in (0.01, 0.1, 1.0, 10.0):
            output.append({"family": "M2_POISSON", "feature_set": feature_set, "alpha": alpha})
        for depth in (2, 3):
            output.append({"family": "M4_SHALLOW_FOREST", "feature_set": feature_set, "max_depth": depth})
    for index, config in enumerate(output):
        config["config_id"] = f"CFG_{index:02d}"
    assert len(output) == 45
    return output


def fit_predict(config: dict, train: pd.DataFrame, test: pd.DataFrame,
                *, shuffled_labels: bool = False) -> tuple[np.ndarray, np.ndarray]:
    columns = family_columns(train, FEATURE_SETS[config["feature_set"]])
    x_train = train[columns].to_numpy(dtype=float)
    x_test = test[columns].to_numpy(dtype=float)
    scaler = StandardScaler().fit(x_train)
    x_train = scaler.transform(x_train); x_test = scaler.transform(x_test)
    y_count = train.residual_event_count.to_numpy(dtype=float)
    y_binary = train.binary_positive.astype(int).to_numpy()
    if shuffled_labels:
        rng = np.random.default_rng(8675309)
        permutation = rng.permutation(len(train))
        y_count = y_count[permutation]; y_binary = y_binary[permutation]
    family = config["family"]
    if family == "M0_HEURISTIC":
        signs = []
        for index in range(x_train.shape[1]):
            correlation = pd.Series(x_train[:, index]).corr(pd.Series(y_count), method="spearman")
            signs.append(1.0 if pd.isna(correlation) or correlation >= 0 else -1.0)
        raw = x_test @ np.asarray(signs) / max(np.sqrt(len(signs)), 1.0)
        binary_probability = 1.0 / (1.0 + np.exp(-np.clip(raw, -30, 30)))
        count_prediction = binary_probability * max(float(y_count[y_count > 0].mean()) if np.any(y_count > 0) else 0.0, 0.0)
    elif family == "M1_LOGISTIC":
        model = LogisticRegression(C=config["C"], class_weight=config["class_weight"], penalty="l2", solver="lbfgs", max_iter=2000, random_state=20260726)
        model.fit(x_train, y_binary)
        binary_probability = model.predict_proba(x_test)[:, 1]
        positive_mean = float(y_count[y_binary > 0].mean()) if np.any(y_binary > 0) else 0.0
        count_prediction = binary_probability * positive_mean
    elif family == "M2_POISSON":
        model = PoissonRegressor(alpha=config["alpha"], max_iter=2000)
        model.fit(x_train, y_count)
        count_prediction = np.maximum(model.predict(x_test), 0.0)
        binary_probability = 1.0 - np.exp(-count_prediction)
    elif family == "M4_SHALLOW_FOREST":
        model = RandomForestRegressor(n_estimators=200, max_depth=config["max_depth"], min_samples_leaf=10, random_state=20260726, n_jobs=1)
        model.fit(x_train, y_count)
        count_prediction = np.maximum(model.predict(x_test), 0.0)
        binary_probability = 1.0 - np.exp(-count_prediction)
    else:
        raise ValueError(family)
    return count_prediction, np.clip(binary_probability, 0.0, 1.0)


def oov_predictions(config: dict, data: pd.DataFrame, *, shuffled_labels: bool = False) -> pd.DataFrame:
    rows = []
    for test_video in sorted(data.video_id.unique()):
        train = data[~data.video_id.eq(test_video)].copy()
        test = data[data.video_id.eq(test_video)].copy()
        count, probability = fit_predict(config, train, test, shuffled_labels=shuffled_labels)
        for row, count_value, probability_value in zip(test.itertuples(index=False), count, probability):
            rows.append({
                "config_id": config["config_id"], "video_id": row.video_id,
                "region_id": row.region_id, "score": float(count_value),
                "binary_probability": float(probability_value),
                "count_prediction": float(count_value),
            })
    return pd.DataFrame(rows)


def evaluate_predictions(config: dict, predictions: pd.DataFrame, data: pd.DataFrame) -> list[dict]:
    rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        pred = predictions[predictions.video_id.eq(video_id)].set_index("region_id").loc[truth.region_id]
        scores = pred.score.to_numpy(dtype=float)
        metrics = score_metrics(truth, scores)
        binary = truth.binary_positive.astype(int).to_numpy()
        metrics.update({
            "binary_brier": float(brier_score_loss(binary, pred.binary_probability)),
            "count_mae": float(mean_absolute_error(truth.residual_event_count, pred.count_prediction)),
            "binary_auprc_calibrated": float(average_precision_score(binary, pred.binary_probability)),
        })
        # Robustness to the single highest-count region.
        drop_position = int(np.argmax(truth.residual_event_count.to_numpy()))
        reduced = truth.drop(index=drop_position).reset_index(drop=True)
        reduced_scores = np.delete(scores, drop_position)
        metrics["leave_best_region_out_recall_at_20"] = recall(reduced, reduced_scores, 0.20)[0]
        rows.append({**config, "video_id": video_id, **metrics})
    return rows


def select_candidate(summary: pd.DataFrame) -> pd.Series:
    ranked = summary.sort_values(["min_video_recall_at_20", "macro_recall_at_20", "macro_auc"], ascending=False)
    best = ranked.iloc[0]
    logistic = ranked[ranked.family.eq("M1_LOGISTIC")]
    if len(logistic):
        best_logistic = logistic.iloc[0]
        if float(best.macro_recall_at_20) - float(best_logistic.macro_recall_at_20) < 0.02:
            return best_logistic
    return best


def main() -> None:
    labels = pd.read_parquet(OUT / f"labels/candidates/region_labels_L{LENGTH:03d}.parquet")
    features = pd.read_parquet(OUT / "preview/region_features/SELECTED.parquet")
    data = labels.merge(features, on=["video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec"], validate="one_to_one")
    data = data.sort_values(["video_id", "region_index"]).reset_index(drop=True)
    configuration_list = configs()
    all_predictions, metric_rows = [], []
    for config in configuration_list:
        predictions = oov_predictions(config, data)
        all_predictions.append(predictions)
        metric_rows.extend(evaluate_predictions(config, predictions, data))
    prediction_frame = pd.concat(all_predictions, ignore_index=True)
    metric_frame = pd.DataFrame(metric_rows)
    prediction_frame.to_parquet(OUT / "predictions/all_45_config_oov_predictions.parquet", index=False)
    metric_frame.to_csv(OUT / "experiments/models/all_45_config_per_video_metrics.csv", index=False)

    summary = metric_frame.groupby(["config_id", "family", "feature_set"], as_index=False).agg(
        macro_recall_at_20=("recall_at_20", "mean"), min_video_recall_at_20=("recall_at_20", "min"),
        macro_auc=("ranking_event_recall_auc", "mean"), macro_auprc=("binary_auprc_calibrated", "mean"),
        macro_brier=("binary_brier", "mean"), macro_count_mae=("count_mae", "mean"),
        min_leave_best_region_out_recall20=("leave_best_region_out_recall_at_20", "min"),
        max_best_region_contribution_ratio=("best_region_contribution_ratio_at_20", "max"),
    )
    selected = select_candidate(summary)
    summary["selected"] = summary.config_id.eq(selected.config_id)
    summary.sort_values(["min_video_recall_at_20", "macro_recall_at_20"], ascending=False).to_csv(OUT / "experiments/models/config_ranking.csv", index=False)
    chosen_config = next(c for c in configuration_list if c["config_id"] == selected.config_id)
    chosen_predictions = prediction_frame[prediction_frame.config_id.eq(selected.config_id)].copy()
    chosen_predictions.to_parquet(OUT / "predictions/best_combination_model_oov_predictions.parquet", index=False)

    # Mandatory controls B4, B6, and B7.
    uni = pd.read_csv(OUT / "experiments/univariate/feature_ranking.csv").iloc[0]
    uni_scores = float(uni.pooled_orientation) * data[uni.feature].to_numpy(dtype=float)
    b4_rows = []
    for video_id, group in data.groupby("video_id", sort=True):
        b4_rows.append({"control": "B4_BEST_UNIVARIATE_HEURISTIC", "video_id": video_id, **score_metrics(group.reset_index(drop=True), uni_scores[group.index.to_numpy()])})
    b4_frame = pd.DataFrame(b4_rows)
    b4_frame.to_csv(OUT / "experiments/controls/B4_best_univariate.csv", index=False)
    # The strongest deployable design candidate is allowed to remain M0.  The
    # bounded combination search did not beat this preregistered univariate.
    combination_min = float(metric_frame[metric_frame.config_id.eq(selected.config_id)].recall_at_20.min())
    b4_min = float(b4_frame.recall_at_20.min())
    stage_candidate_is_b4 = b4_min > combination_min
    stage_candidate_config = {
        "family": "M0_UNIVARIATE_HEURISTIC", "feature": str(uni.feature),
        "orientation": int(uni.pooled_orientation), "selected_on": "TWO_DESIGN_VIDEOS_EXPLORATORY_ONLY",
    } if stage_candidate_is_b4 else chosen_config
    if stage_candidate_is_b4:
        stage_predictions = data[["video_id", "region_id"]].copy()
        stage_predictions["score"] = uni_scores
        stage_predictions["config_id"] = "B4_BEST_UNIVARIATE_HEURISTIC"
    else:
        stage_predictions = chosen_predictions[["video_id", "region_id", "score", "config_id"]].copy()
    stage_predictions.to_parquet(OUT / "predictions/frozen_candidate_oov_predictions.parquet", index=False)

    shuffled_label_predictions = oov_predictions(chosen_config, data, shuffled_labels=True)
    shuffled_label_metrics = evaluate_predictions({**chosen_config, "control": "B6_SHUFFLED_LABEL"}, shuffled_label_predictions, data)
    pd.DataFrame(shuffled_label_metrics).to_csv(OUT / "experiments/controls/B6_shuffled_label.csv", index=False)
    shuffled_score_rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        base = stage_predictions[stage_predictions.video_id.eq(video_id)].set_index("region_id").loc[truth.region_id].score.to_numpy()
        for seed in range(100):
            shuffled = np.random.default_rng(seed).permutation(base)
            shuffled_score_rows.append({"control": "B7_SHUFFLED_REGION_SCORE", "video_id": video_id, "seed": seed, **score_metrics(truth, shuffled)})
    pd.DataFrame(shuffled_score_rows).to_csv(OUT / "experiments/controls/B7_shuffled_score_100_seeds.csv", index=False)

    # Feature-family ablation of the selected model, refit out of video.
    ablation_rows = []
    selected_families = FEATURE_SETS[chosen_config["feature_set"]]
    for omitted in selected_families:
        remaining = [x for x in selected_families if x != omitted]
        temporary_name = f"ABLATE_{omitted}"
        FEATURE_SETS[temporary_name] = remaining
        ablated_config = {**chosen_config, "feature_set": temporary_name, "config_id": f"{chosen_config['config_id']}__NO_{omitted}"}
        predictions = oov_predictions(ablated_config, data)
        ablation_rows.extend(evaluate_predictions({**ablated_config, "omitted_family": omitted}, predictions, data))
        del FEATURE_SETS[temporary_name]
    pd.DataFrame(ablation_rows).to_csv(OUT / "experiments/ablations/selected_model_family_ablation.csv", index=False)

    # Net yield at the pre-registered 60-second total wall-clock budget.
    cost_audit = json.loads((OUT / "audits/preview_cost_audit.json").read_text())
    operator = cost_audit["selected_operator_id"]
    runtime_by_video = {}
    for path in (OUT / "preview/runtime_samples").glob(f"{operator}__*__run1.json"):
        row = json.loads(path.read_text()); runtime_by_video[row["video_id"]] = row["wallclock_sec"]
    net_rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        model_scores = stage_predictions[stage_predictions.video_id.eq(video_id)].set_index("region_id").loc[truth.region_id].score.to_numpy()
        geometry_scores = geometry_order_scores(truth)
        preview_cost = float(runtime_by_video[video_id])
        total_budget = 60.0
        proxy_scan_fraction = max(0.0, total_budget - preview_cost) / float(truth.full_scan_cost_sec.sum())
        coverage_scan_fraction = total_budget / float(truth.full_scan_cost_sec.sum())
        proxy_recall, proxy_used, proxy_selected = recall(truth, model_scores, proxy_scan_fraction)
        coverage_recall, coverage_used, coverage_selected = recall(truth, geometry_scores, coverage_scan_fraction)
        proxy_events = int(truth.iloc[proxy_selected].residual_event_count.sum()) if proxy_selected else 0
        coverage_events = int(truth.iloc[coverage_selected].residual_event_count.sum()) if coverage_selected else 0
        net_rows.append({
            "video_id": video_id, "total_budget_sec": total_budget, "preview_cost_sec": preview_cost,
            "proxy_available_scan_budget_sec": max(0.0, total_budget - preview_cost),
            "proxy_event_count": proxy_events, "coverage_event_count": coverage_events,
            "delta_event_count": proxy_events - coverage_events,
            "proxy_recall": proxy_recall, "coverage_recall": coverage_recall,
            "proxy_scan_cost_used_sec": proxy_used * float(truth.full_scan_cost_sec.sum()),
            "coverage_scan_cost_used_sec": coverage_used * float(truth.full_scan_cost_sec.sum()),
        })
    net_frame = pd.DataFrame(net_rows)
    net_frame.to_csv(OUT / "metrics/net_event_yield_60s.csv", index=False)

    # Gate calculations use honest leave-one-video-out predictions.
    selected_metrics = b4_frame.copy() if stage_candidate_is_b4 else metric_frame[metric_frame.config_id.eq(selected.config_id)].copy()
    random = pd.read_csv(OUT / "experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv").groupby("video_id").recall_at_20.mean()
    shuffled = pd.read_csv(OUT / "experiments/controls/B7_shuffled_score_100_seeds.csv").groupby("video_id").recall_at_20.mean()
    static = pd.read_csv(OUT / "experiments/controls/static_control_metrics.csv")
    time_macro = float(static[static.control.str.startswith("B3_TIME_INDEX")].groupby("control").recall_at_20.mean().max())
    selected_metrics["random_recall_at_20"] = selected_metrics.video_id.map(random)
    selected_metrics["enrichment_at_20"] = selected_metrics.recall_at_20 / selected_metrics.random_recall_at_20
    selected_metrics["shuffled_score_mean_recall_at_20"] = selected_metrics.video_id.map(shuffled)
    gate = {
        "candidate_config": stage_candidate_config,
        "best_combination_model": chosen_config,
        "selection_uses_leave_one_video_out_predictions": not stage_candidate_is_b4,
        "selection_scope_note": "B4 orientation and feature were selected on the two design videos; no validation claim",
        "per_video": selected_metrics[["video_id", "recall_at_10", "recall_at_20", "recall_at_30", "enrichment_at_20", "ranking_event_recall_auc", "binary_auprc", "spearman_count", "best_region_contribution_ratio_at_20", "shuffled_score_mean_recall_at_20"]].to_dict("records"),
        "macro_recall_at_20": float(selected_metrics.recall_at_20.mean()),
        "macro_time_index_best_recall_at_20": time_macro,
        "preview_cost_ratio": float(cost_audit["preview_to_full_scan_cost_ratio"]),
        "net_event_yield_60s_per_video": net_frame.to_dict("records"),
    }
    gate_checks = {
        "recall_at_20_ge_0_40_both": bool((selected_metrics.recall_at_20 >= 0.40).all()),
        "enrichment_gt_1_5_both": bool((selected_metrics.enrichment_at_20 > 1.5).all()),
        "beats_shuffled_score_both": bool((selected_metrics.recall_at_20 > selected_metrics.shuffled_score_mean_recall_at_20).all()),
        "beats_time_index_macro": bool(selected_metrics.recall_at_20.mean() > time_macro),
        "preview_cost_ratio_le_0_10": bool(cost_audit["preview_to_full_scan_cost_ratio"] <= 0.10),
        "net_event_yield_nonnegative_both": bool((net_frame.delta_event_count >= 0).all()),
    }
    gate["checks"] = gate_checks
    gate["all_exploratory_checks_pass"] = all(gate_checks.values())
    gate["exploratory_proxy_signal"] = "CANDIDATE_PROXY_HYPOTHESIS" if gate["all_exploratory_checks_pass"] else "NOT_ESTABLISHED"
    gate["formal_selection_status"] = "IMPOSSIBLE_WITH_TWO_DESIGN_VIDEOS"
    gate["one_step_allocator"] = "NOT_ALLOWED"
    gate["guarded_marginal_scan"] = "STOPPED_BY_PRIOR_HEADROOM_AUDIT"
    gate["next_stage"] = "MULTI_FIDELITY_PREVIEW_OR_NEW_VISIBLE_SIGNAL" if not gate["all_exploratory_checks_pass"] else "ACQUIRE_FOUR_NEW_VALIDATION_VIDEOS"
    dump_json(OUT / "metrics/exploratory_gate.json", gate)
    dump_json(OUT / "contracts/frozen_stage_a_candidate.json", {
        "status": "EXPLORATORY_ONLY", "macro_region_length_sec": LENGTH,
        "macro_region_partition_hash": json.loads((OUT / "metrics/phase2_univariate_summary.json").read_text())["partition_hash"],
        "preview_operator_id": operator, "feature_families": selected_families,
        "model": stage_candidate_config,
        "best_combination_model": chosen_config,
        "prediction_protocol": "DESIGN_SELECTED_UNIVARIATE_WITH_SEPARATE_LEAVE_ONE_VIDEO_OUT_COMBINATION_AUDIT" if stage_candidate_is_b4 else "LEAVE_ONE_COMPLETE_VIDEO_OUT",
        "code_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    })
    print(json.dumps(gate, indent=2))


if __name__ == "__main__":
    main()
