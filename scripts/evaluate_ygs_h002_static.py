#!/usr/bin/env python3
"""Nested static value experiment and frozen Gate for H002."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error
from sklearn.preprocessing import StandardScaler

from run_mfrp_univariate import score_metrics
from run_mrpo_univariate import geometry_order_scores


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / "outputs/multi_fidelity_region_preview_v1"
OUT = ROOT / "outputs/scan_innovation_agentic_loop_v1"
EXP = OUT / "preview_experiments/YGS-H002"

CONFIGS = [
    {"id": "H002_LR_C0P1", "family": "LOGISTIC_REGRESSION", "C": 0.1, "class_weight": None},
    {"id": "H002_LR_C0P1_BAL", "family": "LOGISTIC_REGRESSION", "C": 0.1, "class_weight": "balanced"},
    {"id": "H002_LR_C1", "family": "LOGISTIC_REGRESSION", "C": 1.0, "class_weight": None},
    {"id": "H002_LR_C1_BAL", "family": "LOGISTIC_REGRESSION", "C": 1.0, "class_weight": "balanced"},
    {"id": "H002_POISSON_A0P1", "family": "POISSON_REGRESSION", "alpha": 0.1},
    {"id": "H002_POISSON_A1", "family": "POISSON_REGRESSION", "alpha": 1.0},
    {"id": "H002_LGBM_D2", "family": "SHALLOW_LIGHTGBM", "max_depth": 2, "num_leaves": 4},
    {"id": "H002_LGBM_D3", "family": "SHALLOW_LIGHTGBM", "max_depth": 3, "num_leaves": 8},
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20): h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    def convert(item):
        if isinstance(item, np.bool_): return bool(item)
        if isinstance(item, np.integer): return int(item)
        if isinstance(item, np.floating): return float(item)
        raise TypeError(type(item).__name__)
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False, default=convert) + "\n")
    tmp.replace(path)


def q2_family(column: str) -> str:
    if any(x in column for x in ("selected", "sample_count", "valid_sample", "missingness")): return "q2_support"
    if any(x in column for x in ("object_count", "vehicle_count", "vulnerable_count", "person_count", "bicycle_count", "car_count", "motorcycle_count", "bus_count", "truck_count")):
        return "q2_counts"
    if "confidence" in column: return "q2_confidence"
    if any(x in column for x in ("bbox_area", "bbox_center", "bbox_bottom")): return "q2_geometry"
    if "occupancy" in column or "large_bbox" in column: return "q2_occupancy"
    if "class_entropy" in column: return "q2_composition"
    if any(x in column for x in ("change_abs", "detection_burst", "empty_frame", "coarse_center_trigger")): return "q2_temporal"
    raise KeyError(column)


def select_q2_features(train: pd.DataFrame) -> list[str]:
    rows = []
    for column in [c for c in train.columns if c.startswith("q2__")]:
        values = train[column].to_numpy(float)
        if np.std(values) <= 1e-12: continue
        corr = spearmanr(values, train.residual_event_count.to_numpy(float)).statistic
        orientation = 1.0 if not np.isfinite(corr) or corr >= 0 else -1.0
        metric = score_metrics(train, orientation * values)
        rows.append({"feature": column, "family": q2_family(column),
                     "recall20": metric["recall_at_20"], "auc": metric["ranking_event_recall_auc"]})
    table = pd.DataFrame(rows)
    selected = []
    for _, group in table.groupby("family", sort=True):
        selected += group.sort_values(["recall20", "auc", "feature"], ascending=[False, False, True]).head(2).feature.tolist()
    return sorted(selected)


def fit_predict(config: dict, train: pd.DataFrame, target: pd.DataFrame, columns: list[str]):
    scaler = StandardScaler().fit(train[columns].to_numpy(float))
    xtrain = scaler.transform(train[columns].to_numpy(float)); xtarget = scaler.transform(target[columns].to_numpy(float))
    ycount = train.residual_event_count.to_numpy(float); ybinary = train.binary_positive.astype(int).to_numpy()
    if config["family"] == "LOGISTIC_REGRESSION":
        model = LogisticRegression(C=config["C"], class_weight=config["class_weight"], solver="lbfgs", max_iter=3000, random_state=20260726)
        model.fit(xtrain, ybinary); probability = model.predict_proba(xtarget)[:, 1]
        score = probability; count = probability * float(ycount[ybinary > 0].mean())
    elif config["family"] == "POISSON_REGRESSION":
        model = PoissonRegressor(alpha=config["alpha"], max_iter=3000).fit(xtrain, ycount)
        count = np.maximum(model.predict(xtarget), 0); probability = 1 - np.exp(-count); score = count
    else:
        model = LGBMRegressor(objective="poisson", max_depth=config["max_depth"], num_leaves=config["num_leaves"],
            min_child_samples=10, n_estimators=100, learning_rate=0.05, random_state=20260726,
            n_jobs=1, deterministic=True, force_col_wise=True, verbosity=-1).fit(xtrain, ycount)
        count = np.maximum(model.predict(xtarget), 0); probability = 1 - np.exp(-count); score = count
    return np.asarray(score), np.asarray(probability), np.asarray(count)


def evaluate(frame: pd.DataFrame, score: np.ndarray, probability: np.ndarray, count: np.ndarray) -> dict:
    result = score_metrics(frame, score)
    result["binary_brier_score"] = float(brier_score_loss(frame.binary_positive.astype(int), probability))
    result["count_mae"] = float(mean_absolute_error(frame.residual_event_count, count))
    drop = int(np.argmax(frame.residual_event_count.to_numpy()))
    reduced = frame.drop(index=drop).reset_index(drop=True)
    result["leave_best_region_out_recall_at_20"] = score_metrics(reduced, np.delete(score, drop))["recall_at_20"]
    result["dropped_best_region_id"] = str(frame.iloc[drop].region_id)
    return result


def choose(metrics: pd.DataFrame) -> pd.Series:
    ranked = metrics.sort_values(["train_recall20", "train_auc", "config_id"], ascending=[False, False, True])
    best = ranked.iloc[0]; logistic = ranked.query("family == 'LOGISTIC_REGRESSION'")
    if len(logistic):
        best_lr = logistic.iloc[0]
        if float(best.train_recall20) - float(best_lr.train_recall20) < 0.02: return best_lr
    return best


def selected_prefix(frame: pd.DataFrame, score: np.ndarray, budget: float) -> list[int]:
    spent = 0.0; selected = []
    for index in np.argsort(-np.asarray(score), kind="stable"):
        cost = float(frame.iloc[index].full_scan_cost_sec)
        if spent + cost > budget + 1e-12: break
        selected.append(int(index)); spent += cost
    return selected


def main() -> None:
    contract = json.loads((OUT / "contracts/YGS-H002.json").read_text())
    q2a = pd.read_parquet(EXP / "region_features_run1.parquet")
    q2b = pd.read_parquet(EXP / "region_features_run2.parquet")
    if sha256(EXP / "region_features_run1.parquet") != sha256(EXP / "region_features_run2.parquet"):
        raise AssertionError("Q2 byte determinism failed")
    truth = pd.read_parquet(PARENT / "labels/region_table.parquet")
    q1 = pd.read_parquet(PARENT / "features/region_features.parquet")
    keys = ["video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec"]
    data = truth.merge(q1, on=keys, validate="one_to_one").merge(q2a, on=keys, how="left", validate="one_to_one")
    q2cols = [c for c in q2a if c.startswith("q2__")]
    data[q2cols] = data[q2cols].fillna(0.0)
    data = data.sort_values(["video_id", "region_index"]).reset_index(drop=True)
    q1_features = json.loads((PARENT / "experiments/models/nested_feature_selections.json").read_text())

    metric_rows, prediction_rows, fold_features = [], [], {}
    for test_video in sorted(data.video_id.unique()):
        train = data.query("video_id != @test_video").reset_index(drop=True)
        test = data.query("video_id == @test_video").reset_index(drop=True)
        q1cols = q1_features[f"test={test_video}|preview=P1_L"]["features"]
        q2selected = select_q2_features(train)
        columns = q1cols + q2selected
        fold_features[test_video] = {"q1": q1cols, "q2": q2selected, "all": columns}
        for config in CONFIGS:
            train_score, train_prob, train_count = fit_predict(config, train, train, columns)
            test_score, test_prob, test_count = fit_predict(config, train, test, columns)
            tm = evaluate(train, train_score, train_prob, train_count); vm = evaluate(test, test_score, test_prob, test_count)
            metric_rows.append({"test_video_id": test_video, "config_id": config["id"], "family": config["family"],
                                "train_recall20": tm["recall_at_20"], "train_auc": tm["ranking_event_recall_auc"],
                                **{f"test_{k}": v for k, v in vm.items()}})
            for region_id, score, prob, count in zip(test.region_id, test_score, test_prob, test_count):
                prediction_rows.append({"test_video_id": test_video, "config_id": config["id"], "region_id": region_id,
                                        "score": float(score), "binary_probability": float(prob), "count_prediction": float(count)})
    all_metrics = pd.DataFrame(metric_rows); all_predictions = pd.DataFrame(prediction_rows)
    selections = []
    for test_video, group in all_metrics.groupby("test_video_id", sort=True): selections.append(choose(group).to_dict())
    selection = pd.DataFrame(selections)
    nested = pd.concat([all_predictions.query("test_video_id == @row.test_video_id and config_id == @row.config_id") for row in selection.itertuples()], ignore_index=True)

    final_rows = []
    for video_id, frame in data.groupby("video_id", sort=True):
        frame = frame.sort_values("region_index").reset_index(drop=True)
        chosen = selection.query("test_video_id == @video_id").iloc[0]
        pred = nested.query("test_video_id == @video_id").set_index("region_id").loc[frame.region_id]
        final_rows.append({"video_id": video_id, "selected_config_id": chosen.config_id, "selected_family": chosen.family,
                           **evaluate(frame, pred.score.to_numpy(), pred.binary_probability.to_numpy(), pred.count_prediction.to_numpy())})
    final = pd.DataFrame(final_rows)

    # Mandatory controls and actual cost accounting.
    random_mean = pd.read_csv(PARENT / "experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv").groupby("video_id").recall_at_20.mean().to_dict()
    p1metrics = pd.read_csv(PARENT / "metrics/nested_branch_per_video_metrics.csv").query("preview == 'P1_L'").set_index("video_id")
    p0 = json.loads((PARENT / "preview/p0/inheritance_manifest.json").read_text())["frozen_nested_lovo_recall_at_20"]
    controls = pd.read_csv(PARENT / "experiments/controls/static_control_metrics.csv")
    time_macro = float(controls[controls.control.str.startswith("B3_TIME_INDEX")].groupby("control").recall_at_20.mean().max())
    shuffled_rows = []
    for video_id, frame in data.groupby("video_id", sort=True):
        frame = frame.sort_values("region_index").reset_index(drop=True)
        score = nested.query("test_video_id == @video_id").set_index("region_id").loc[frame.region_id].score.to_numpy()
        for seed in range(100):
            shuffled_rows.append({"video_id": video_id, "seed": seed,
                                  **score_metrics(frame, np.random.default_rng(seed).permutation(score))})
    shuffled = pd.DataFrame(shuffled_rows); shuffled_mean = shuffled.groupby("video_id").recall_at_20.mean().to_dict()

    parent_cost = json.loads((PARENT / "audits/preview_cost_audit.json").read_text())
    q1_costs = parent_cost["configs"]["P1_L"]["conservative_per_video_cost_sec"]
    q2r = pd.concat([pd.read_csv(EXP / f"runtime_run{i}.csv") for i in (1, 2)])
    q2_costs = q2r.groupby("video_id").total_wallclock_sec.max().to_dict()
    total_costs = {video: float(q1_costs[video] + q2_costs[video]) for video in q1_costs}
    full_scan_cost = float(data.full_scan_cost_sec.sum())
    total_cost_ratio = sum(total_costs.values()) / full_scan_cost

    budget_rows = []
    for video_id, frame in data.groupby("video_id", sort=True):
        frame = frame.sort_values("region_index").reset_index(drop=True)
        score = nested.query("test_video_id == @video_id").set_index("region_id").loc[frame.region_id].score.to_numpy()
        geometry = geometry_order_scores(frame); full = float(frame.full_scan_cost_sec.sum())
        for budget_id, total_budget in (("WALLCLOCK_60S", 60.0), ("FULL_SCAN_COST_20PCT", .2 * full), ("FULL_SCAN_COST_30PCT", .3 * full)):
            remain = total_budget - total_costs[video_id]
            if remain < 0:
                budget_rows.append({"video_id": video_id, "budget_id": budget_id, "budget_cell": "INFEASIBLE_PREVIEW_COST",
                                    "total_budget_sec": total_budget, "preview_cost_sec": total_costs[video_id]})
                continue
            ps = selected_prefix(frame, score, remain); cs = selected_prefix(frame, geometry, total_budget)
            pe = int(frame.iloc[ps].residual_event_count.sum()) if ps else 0; ce = int(frame.iloc[cs].residual_event_count.sum()) if cs else 0
            budget_rows.append({"video_id": video_id, "budget_id": budget_id, "budget_cell": "FEASIBLE",
                                "total_budget_sec": total_budget, "preview_cost_sec": total_costs[video_id], "remaining_scan_budget_sec": remain,
                                "preview_event_count": pe, "coverage_event_count": ce, "delta_event_count": pe-ce})
    budget = pd.DataFrame(budget_rows)

    checks_by_video = {}
    for row in final.itertuples():
        checks_by_video[row.video_id] = {
            "recall20_ge_0p40": row.recall_at_20 >= .40,
            "auc_gt_0p55": row.ranking_event_recall_auc > .55,
            "enrichment_gt_1p5": row.recall_at_20 / random_mean[row.video_id] > 1.5,
            "beats_p0": row.recall_at_20 > p0[row.video_id],
            "beats_p1l": row.recall_at_20 > p1metrics.loc[row.video_id].recall_at_20 + 1e-12,
            "beats_shuffled": row.recall_at_20 > shuffled_mean[row.video_id],
            "leave_best_nonnegative_vs_p1l": row.leave_best_region_out_recall_at_20 >= p1metrics.loc[row.video_id].leave_best_region_out_recall_at_20,
            "best_region_contribution_lt_0p50": row.best_region_contribution_ratio_at_20 < .50,
        }
    primary = budget.query("budget_id == 'FULL_SCAN_COST_20PCT'")
    common_positive = any(
        len((cells := budget.query("budget_id == @bid"))) == 2 and cells.budget_cell.eq("FEASIBLE").all() and cells.delta_event_count.gt(0).all()
        for bid in ["WALLCLOCK_60S", "FULL_SCAN_COST_20PCT", "FULL_SCAN_COST_30PCT"]
    )
    global_checks = {
        "all_per_video_checks": all(all(v.values()) for v in checks_by_video.values()),
        "beats_time_index_macro": final.recall_at_20.mean() > time_macro,
        "total_preview_cost_ratio_le_0p10": total_cost_ratio <= .10,
        "net_yield_primary_nonnegative_both": primary.budget_cell.eq("FEASIBLE").all() and primary.delta_event_count.ge(0).all(),
        "one_common_budget_positive_both": common_positive,
    }
    gate_pass = all(global_checks.values())

    all_metrics.to_parquet(EXP / "all_config_nested_metrics.parquet", index=False)
    all_predictions.to_parquet(EXP / "all_config_nested_predictions.parquet", index=False)
    nested.to_parquet(EXP / "nested_predictions.parquet", index=False)
    final.to_csv(EXP / "per_video_metrics.csv", index=False)
    selection.to_csv(EXP / "nested_selected_configs.csv", index=False)
    shuffled.to_csv(EXP / "shuffled_score_100_seeds.csv", index=False)
    budget.to_csv(EXP / "net_event_yield_budget_grid.csv", index=False)
    atomic_json(EXP / "nested_feature_selections.json", fold_features)
    result = {
        "hypothesis_id": "YGS-H002", "status": "ACCEPTED" if gate_pass else "REJECTED",
        "static_observability_gate_pass": gate_pass, "per_video_checks": checks_by_video,
        "global_checks": global_checks, "metrics": final.to_dict("records"),
        "q1_costs_sec": q1_costs, "q2_costs_sec": q2_costs, "combined_preview_costs_sec": total_costs,
        "combined_preview_cost_ratio": total_cost_ratio, "shuffled_mean_recall20": shuffled_mean,
        "random_mean_recall20": random_mean, "time_index_macro_recall20": time_macro,
        "implementation_hash": sha256(Path(__file__)), "contract_hash": sha256(OUT / "contracts/YGS-H002.json"),
        "decision": "ALLOW_ONE_STEP_SCHEDULER" if gate_pass else "PROHIBIT_SCHEDULER_FOR_H002",
    }
    atomic_json(OUT / "hypotheses/YGS-H002.json", result)
    atomic_json(EXP / "static_gate.json", result)
    print((OUT / "hypotheses/YGS-H002.json").read_text(), end="")


if __name__ == "__main__": main()
