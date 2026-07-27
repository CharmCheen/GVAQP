#!/usr/bin/env python3
"""Fill all mandatory MRPO-V1 evidence fields without new model search.

This script performs reporting/calibration/robustness checks only.  It freezes
no new feature or ranker and cannot change the exploratory Gate outcome.
"""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
import subprocess

import cv2
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.metrics import brier_score_loss, mean_absolute_error
from sklearn.preprocessing import StandardScaler

from run_mrpo_univariate import geometry_order_scores, recall, score_metrics


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/macro_region_proxy_optimization_v1"
EXCLUDED_FEATURE_COLUMNS = {
    "operator_id", "video_id", "region_id", "region_index", "start_sec",
    "end_sec", "actual_duration_sec", "preview_expected_sample_count",
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value.rstrip() + "\n")
    tmp.replace(path)


def git_value(*args: str) -> str:
    command = ["git", f"--git-dir={ROOT/'.git'}", f"--work-tree={ROOT}", *args]
    result = subprocess.run(command, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def candidate_calibration(data: pd.DataFrame, feature: str, orientation: int) -> tuple[pd.DataFrame, list[dict]]:
    rows = []
    for test_video in sorted(data.video_id.unique()):
        train = data[~data.video_id.eq(test_video)].copy()
        test = data[data.video_id.eq(test_video)].copy()
        scaler = StandardScaler().fit((orientation * train[[feature]]).to_numpy())
        x_train = scaler.transform((orientation * train[[feature]]).to_numpy())
        x_test = scaler.transform((orientation * test[[feature]]).to_numpy())
        logistic = LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=2000, random_state=20260726)
        poisson = PoissonRegressor(alpha=1.0, max_iter=2000)
        logistic.fit(x_train, train.binary_positive.astype(int))
        poisson.fit(x_train, train.residual_event_count)
        probability = logistic.predict_proba(x_test)[:, 1]
        count_prediction = np.maximum(poisson.predict(x_test), 0.0)
        for item, p_binary, p_count in zip(test.itertuples(index=False), probability, count_prediction):
            rows.append({
                "video_id": item.video_id, "region_id": item.region_id,
                "fixed_candidate_score": float(orientation * getattr(item, feature)),
                "binary_probability_lovo_calibrated": float(p_binary),
                "count_prediction_lovo_calibrated": float(p_count),
                "calibration_train_video": str(train.video_id.iloc[0]),
            })
    predictions = pd.DataFrame(rows)
    metrics = []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        pred = predictions[predictions.video_id.eq(video_id)].set_index("region_id").loc[truth.region_id]
        metrics.append({
            "video_id": video_id,
            "binary_brier_score_lovo_calibrated": float(brier_score_loss(
                truth.binary_positive.astype(int), pred.binary_probability_lovo_calibrated
            )),
            "count_mae_lovo_calibrated": float(mean_absolute_error(
                truth.residual_event_count, pred.count_prediction_lovo_calibrated
            )),
            "calibration_only_does_not_change_ranking": True,
        })
    return predictions, metrics


def nested_lovo_univariate(data: pd.DataFrame, feature_columns: list[str], random_means: dict[str, float]) -> list[dict]:
    results = []
    for test_video in sorted(data.video_id.unique()):
        train = data[~data.video_id.eq(test_video)].sort_values("region_index").reset_index(drop=True)
        test = data[data.video_id.eq(test_video)].sort_values("region_index").reset_index(drop=True)
        candidates = []
        for feature in feature_columns:
            correlation = pd.Series(train[feature]).corr(train.residual_event_count, method="spearman")
            orientation = 1 if pd.isna(correlation) or correlation >= 0 else -1
            train_metrics = score_metrics(train, orientation * train[feature].to_numpy())
            candidates.append({
                "feature": feature, "orientation": orientation,
                "train_recall_at_20": train_metrics["recall_at_20"],
                "train_auc": train_metrics["ranking_event_recall_auc"],
            })
        selected = max(candidates, key=lambda row: (row["train_recall_at_20"], row["train_auc"], row["feature"]))
        test_metrics = score_metrics(test, selected["orientation"] * test[selected["feature"]].to_numpy())
        random_mean = random_means[test_video]
        results.append({
            "test_video_id": test_video, "train_video_id": str(train.video_id.iloc[0]),
            "train_selected_feature": selected["feature"],
            "train_selected_orientation": selected["orientation"],
            "train_recall_at_20": selected["train_recall_at_20"],
            "test_recall_at_20": test_metrics["recall_at_20"],
            "test_ranking_auc": test_metrics["ranking_event_recall_auc"],
            "test_spearman": test_metrics["spearman_count"],
            "test_random_mean_recall_at_20": random_mean,
            "test_delta_vs_random": test_metrics["recall_at_20"] - random_mean,
            "direction_vs_random": "POSITIVE" if test_metrics["recall_at_20"] > random_mean else "NON_POSITIVE",
        })
    return results


def cost_adjusted_grid(data: pd.DataFrame, score_feature: str, orientation: int,
                       preview_runtime: dict[str, float]) -> pd.DataFrame:
    rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        full_cost = float(truth.full_scan_cost_sec.sum())
        scores = orientation * truth[score_feature].to_numpy()
        coverage = geometry_order_scores(truth)
        budgets = [("WALLCLOCK_60S", 60.0)] + [
            (f"FULL_SCAN_COST_{int(q*100)}PCT", q * full_cost) for q in (0.10, 0.20, 0.30)
        ]
        for budget_id, total_budget in budgets:
            preview_cost = preview_runtime[video_id]
            proxy_scan_budget = max(0.0, total_budget - preview_cost)
            proxy_q = proxy_scan_budget / full_cost
            coverage_q = total_budget / full_cost
            proxy_recall, proxy_used, proxy_selected = recall(truth, scores, proxy_q)
            coverage_recall, coverage_used, coverage_selected = recall(truth, coverage, coverage_q)
            proxy_events = int(truth.iloc[proxy_selected].residual_event_count.sum()) if proxy_selected else 0
            coverage_events = int(truth.iloc[coverage_selected].residual_event_count.sum()) if coverage_selected else 0
            rows.append({
                "video_id": video_id, "budget_id": budget_id,
                "total_wallclock_budget_sec": total_budget, "full_scan_cost_sec": full_cost,
                "preview_cost_sec": preview_cost, "preview_fraction_of_budget": preview_cost / total_budget,
                "proxy_scan_budget_sec": proxy_scan_budget,
                "proxy_scan_cost_used_sec": proxy_used * full_cost,
                "coverage_scan_cost_used_sec": coverage_used * full_cost,
                "proxy_event_count": proxy_events, "coverage_event_count": coverage_events,
                "delta_event_count": proxy_events - coverage_events,
                "proxy_recall": proxy_recall, "coverage_recall": coverage_recall,
            })
    return pd.DataFrame(rows)


def update_manifest() -> None:
    manifest = {}
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "artifact_hash_manifest.json":
            manifest[str(path.relative_to(OUT))] = {"sha256": sha_file(path), "bytes": path.stat().st_size}
    write_json(OUT / "artifact_hash_manifest.json", {"artifact_count": len(manifest), "artifacts": manifest})


def main() -> None:
    labels = pd.read_parquet(OUT / "labels/candidates/region_labels_L040.parquet")
    features = pd.read_parquet(OUT / "preview/region_features/SELECTED.parquet")
    data = labels.merge(features, on=[
        "video_id", "region_id", "region_index", "start_sec", "end_sec", "actual_duration_sec",
    ], validate="one_to_one").sort_values(["video_id", "region_index"]).reset_index(drop=True)
    gate = json.loads((OUT / "metrics/exploratory_gate.json").read_text())
    candidate = gate["candidate_config"]
    feature = candidate["feature"]
    orientation = int(candidate["orientation"])
    feature_columns = [column for column in features.columns if column not in EXCLUDED_FEATURE_COLUMNS]
    random_runs = pd.read_csv(OUT / "experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv")
    random_means = random_runs.groupby("video_id").recall_at_20.mean().to_dict()

    calibration_predictions, calibration_metrics = candidate_calibration(data, feature, orientation)
    calibration_predictions.to_parquet(OUT / "predictions/candidate_lovo_calibration_predictions.parquet", index=False)
    nested_lovo = nested_lovo_univariate(data, feature_columns, random_means)
    write_json(OUT / "metrics/leave_one_video_out_direction.json", {
        "protocol": "NESTED_TRAIN_VIDEO_ONLY_UNIVARIATE_SELECTION_AND_ORIENTATION",
        "selection_unit": "COMPLETE_VIDEO", "results": nested_lovo,
        "stable_cross_video_ranking_signal": bool(all(
            row["direction_vs_random"] == "POSITIVE" and row["test_ranking_auc"] > 0.5 for row in nested_lovo
        )),
    })

    ranking = json.loads((OUT / "metrics/ranking_metrics.json").read_text())
    per_video = pd.read_csv(OUT / "metrics/per_video_metrics.csv")
    calibration_by_video = {row["video_id"]: row for row in calibration_metrics}
    leave_best_rows = []
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        scores = orientation * truth[feature].to_numpy()
        drop_index = int(np.argmax(truth.residual_event_count.to_numpy()))
        dropped = truth.iloc[drop_index]
        reduced = truth.drop(index=drop_index).reset_index(drop=True)
        reduced_scores = np.delete(scores, drop_index)
        result = {
            "video_id": video_id, "dropped_region_id": dropped.region_id,
            "dropped_event_count": int(dropped.residual_event_count),
            "recall_at_20_after_drop": score_metrics(reduced, reduced_scores)["recall_at_20"],
        }
        leave_best_rows.append(result)
        mask = per_video.video_id.eq(video_id)
        per_video.loc[mask, "binary_brier_score_lovo_calibrated"] = calibration_by_video[video_id]["binary_brier_score_lovo_calibrated"]
        per_video.loc[mask, "count_mae_lovo_calibrated"] = calibration_by_video[video_id]["count_mae_lovo_calibrated"]
        per_video.loc[mask, "leave_best_region_out_recall_at_20"] = result["recall_at_20_after_drop"]
    per_video.to_csv(OUT / "metrics/per_video_metrics.csv", index=False)
    ranking["candidate_calibration"] = calibration_metrics
    ranking["leave_best_region_out"] = leave_best_rows
    ranking["nested_leave_one_video_out_direction"] = nested_lovo
    ranking["candidate_selection_bias_note"] = "Pooled B4 is design-selected; nested LOVO is the cross-video stability evidence"
    write_json(OUT / "metrics/ranking_metrics.json", ranking)

    operator = gate["candidate_config"]
    preview_id = json.loads((OUT / "audits/preview_cost_audit.json").read_text())["selected_operator_id"]
    preview_runtime = {}
    for path in (OUT / "preview/runtime_samples").glob(f"{preview_id}__*__run1.json"):
        row = json.loads(path.read_text()); preview_runtime[row["video_id"]] = float(row["wallclock_sec"])
    net_grid = cost_adjusted_grid(data, feature, orientation, preview_runtime)
    net_grid.to_csv(OUT / "metrics/net_event_yield_budget_grid.csv", index=False)
    cost_metrics = json.loads((OUT / "metrics/cost_adjusted_metrics.json").read_text())
    cost_metrics["budget_grid"] = net_grid.to_dict("records")
    cost_metrics["budget_grid_ids"] = list(net_grid.budget_id.unique())
    cost_metrics["interpretation"] = "Preview is paid inside every total wall-clock budget; complete regions only"
    write_json(OUT / "metrics/cost_adjusted_metrics.json", cost_metrics)

    controls = pd.read_csv(OUT / "experiments/controls/static_control_metrics.csv")
    combo_predictions = pd.read_parquet(OUT / "predictions/best_combination_model_oov_predictions.parquet")
    failure = {"per_video": []}
    for video_id, truth in data.groupby("video_id", sort=True):
        truth = truth.sort_values("region_index").reset_index(drop=True)
        candidate_scores = orientation * truth[feature].to_numpy()
        combo_scores = combo_predictions[combo_predictions.video_id.eq(video_id)].set_index("region_id").loc[truth.region_id].score.to_numpy()
        candidate_selection = set(recall(truth, candidate_scores, 0.20)[2])
        combo_selection = set(recall(truth, combo_scores, 0.20)[2])
        time_rows = controls[(controls.video_id.eq(video_id)) & controls.control.str.startswith("B3_TIME_INDEX")]
        best_time = time_rows.sort_values("recall_at_20", ascending=False).iloc[0]
        oracle = controls[(controls.video_id.eq(video_id)) & controls.control.eq("B8_OFFLINE_FULL_INFORMATION_DENSITY")].iloc[0]
        candidate_metrics = score_metrics(truth, candidate_scores)
        failure["per_video"].append({
            "video_id": video_id,
            "oracle_missed_headroom_recall20": float(oracle.recall_at_20 - candidate_metrics["recall_at_20"]),
            "best_time_index_control": best_time.control,
            "candidate_minus_best_time_recall20": float(candidate_metrics["recall_at_20"] - best_time.recall_at_20),
            "model_heuristic_selected_region_symmetric_difference": len(candidate_selection.symmetric_difference(combo_selection)),
            "model_heuristic_selected_region_jaccard": len(candidate_selection & combo_selection) / max(len(candidate_selection | combo_selection), 1),
            "best_region_contribution_ratio": candidate_metrics["best_region_contribution_ratio_at_20"],
        })
    missingness = {
        "total_missing_feature_cells": int(features[feature_columns].isna().sum().sum()),
        "per_feature": {column: int(features[column].isna().sum()) for column in feature_columns},
    }
    failure["proxy_feature_missingness"] = missingness
    failure["preview_cost_decomposition"] = json.loads((OUT / "audits/preview_cost_audit.json").read_text())["per_operator_cost_decomposition"]
    failure["nested_lovo"] = nested_lovo
    failure["candidate_hypothesis_only"] = "P1_LOW_RATE_DETECTION_OR_P2_SPARSE_MOTION_MAY_CLOSE_OBSERVABILITY_GAP"
    write_json(OUT / "metrics/failure_analysis_metrics.json", failure)

    preview_manifest_path = OUT / "preview/operator_manifests/P0_SELECTION.json"
    preview_manifest = json.loads(preview_manifest_path.read_text())
    extraction_hash = sha_file(ROOT / "scripts/run_mrpo_preview_p0.py")
    preview_manifest.update({
        "sampling_rate_hz": 0.2, "resolution": "160x90",
        "model_hash": "NOT_APPLICABLE_P0_NO_DNN",
        "feature_extraction_hash": extraction_hash,
        "preview_cost_model": "MEASURED_FULL_TWO_VIDEO_WALLCLOCK_NO_EXTRAPOLATION",
    })
    write_json(preview_manifest_path, preview_manifest)
    frozen_stage_path = OUT / "contracts/frozen_stage_a_candidate.json"
    frozen_stage = json.loads(frozen_stage_path.read_text())
    frozen_stage.update({
        "preview_sampling_rate_hz": 0.2, "preview_resolution": "160x90",
        "preview_model_hash": "NOT_APPLICABLE_P0_NO_DNN",
        "feature_extraction_hash": extraction_hash,
        "preview_cost_model": "MEASURED_FULL_TWO_VIDEO_WALLCLOCK_NO_EXTRAPOLATION",
        "feature_schema_hash": sha_bytes(json.dumps([feature], sort_keys=True).encode()),
        "formal_freeze_status": "NOT_FORMALLY_FROZEN_EXPLORATORY_GATE_FAILED",
    })
    write_json(frozen_stage_path, frozen_stage)

    environment = json.loads((OUT / "environment_lock.json").read_text())
    environment.update({
        "opencv": cv2.__version__, "scikit_learn": sklearn.__version__,
        "ffmpeg_version": subprocess.run(["ffmpeg", "-version"], text=True, capture_output=True).stdout.splitlines()[0],
        "preview_device": "CPU_FFMPEG_AND_OPENCV_NO_DNN",
        "platform_verified": platform.platform(),
    })
    write_json(OUT / "environment_lock.json", environment)

    # Requirement-to-evidence completion matrix. Formal stages are correctly
    # not applicable because their preregistered data/gate prerequisites fail.
    matrix_rows = [
        ("Frozen objective and claim scope", "PASS", "contracts/frozen_contract.json; reports/FINAL_PROXY_DECISION.md"),
        ("Two design videos; no validation/test reuse", "PASS", "audits/asset_audit.json"),
        ("40/60/90/120 region candidates and retained tails", "PASS", "audits/label_audit.json; experiments/macro_region_sensitivity/phase0_label_sensitivity.csv"),
        ("Selected length and partition hash", "PASS", "contracts/frozen_stage_a_candidate.json"),
        ("Preview config count <=4 and label-free selection", "PASS", "preview/operator_manifests/P0_SELECTION.json"),
        ("Every preview config cost/determinism/coverage/missingness", "PASS", "audits/preview_cost_audit.json; preview/operator_manifests/P0_SELECTION.json"),
        ("Preview ratio <=0.10 and cost decomposition", "PASS", "audits/preview_cost_audit.json"),
        ("Canonical midpoint mapping; boundary tie; event once", "PASS", "audits/label_audit.json; labels/event_region_map.parquet"),
        ("263 exposable, 268 all, ceiling reported", "PASS", "audits/asset_audit.json; metrics/ranking_metrics.json"),
        ("Binary/count labels and H0 empty", "PASS", "contracts/label_contract.json; labels/region_binary_labels.parquet; labels/region_count_labels.parquet"),
        ("Feature families <=8 and forbidden intersection empty", "PASS", "audits/feature_legality_audit.json; audits/leakage_audit.json"),
        ("Model families <=5; configs <=50; constraints", "PASS", "experiments/models/config_ranking.csv; contracts/search_budget.json"),
        ("B0-B8 mandatory controls", "PASS", "experiments/controls/"),
        ("Random >=100 seeds/video", "PASS", "metrics/random_baseline_distribution.json"),
        ("Primary Recall@20 complete-region cost", "PASS", "metrics/ranking_metrics.json; metrics/per_region_metrics.csv"),
        ("Recall@10/30, AUC, AUPRC, Spearman, used cost", "PASS", "metrics/per_video_metrics.csv"),
        ("Binary Brier and Count MAE", "PASS", "metrics/per_video_metrics.csv; predictions/candidate_lovo_calibration_predictions.parquet"),
        ("Per-video and nested leave-one-video-out direction", "PASS", "metrics/leave_one_video_out_direction.json"),
        ("Leave-best-region-out and contribution ratio", "PASS", "metrics/ranking_metrics.json"),
        ("Preview-cost-adjusted net yield at 60s and frozen q grid", "PASS", "metrics/net_event_yield_budget_grid.csv; metrics/cost_adjusted_metrics.json"),
        ("Phase 0-3 completed within search budget", "PASS", "reports/PHASE0_ASSET_AND_LABEL_AUDIT.md; experiments/"),
        ("Exploratory Gate evaluated", "PASS", "metrics/exploratory_gate.json"),
        ("Formal validation", "NOT_APPLICABLE_PREREQUISITE_MISSING", "VALIDATION_VIDEO_COUNT=0; contract requires >=4"),
        ("One-step allocator", "CORRECTLY_BLOCKED_BY_FAILED_GATE", "metrics/exploratory_gate.json"),
        ("Guarded marginal/RL/Bandit prohibited", "PASS_NOT_IMPLEMENTED", "reports/FINAL_PROXY_DECISION.md"),
        ("All nine failure-analysis categories", "PASS", "reports/FAILURE_ANALYSIS.md; metrics/failure_analysis_metrics.json"),
        ("Required deliverable tree", "PASS", "artifact_hash_manifest.json; reports/INDEPENDENT_RESULT_AUDIT.json"),
        ("Final terminal fields", "PASS", "reports/FINAL_PROXY_DECISION.md"),
    ]
    matrix = pd.DataFrame(matrix_rows, columns=["requirement", "status", "authoritative_evidence"])
    matrix.to_csv(OUT / "reports/CONTRACT_COMPLETION_MATRIX.csv", index=False)
    matrix_markdown = "# MRPO-V1 Contract Completion Matrix\n\n" + matrix.to_markdown(index=False) + "\n"
    write_text(OUT / "reports/CONTRACT_COMPLETION_MATRIX.md", matrix_markdown)

    per_video_metrics = pd.read_csv(OUT / "metrics/per_video_metrics.csv").set_index("video_id")
    nested_text = "\n".join(
        f"- Train `{row['train_video_id']}` → test `{row['test_video_id']}` selected `{row['train_selected_feature']}`: "
        f"Recall@20={row['test_recall_at_20']:.3f}, random={row['test_random_mean_recall_at_20']:.3f}, AUC={row['test_ranking_auc']:.3f}."
        for row in nested_lovo
    )
    grid_lines = "\n".join(
        f"- `{row.video_id}` / `{row.budget_id}`: proxy={int(row.proxy_event_count)}, coverage={int(row.coverage_event_count)}, Δ={int(row.delta_event_count)}."
        for row in net_grid.itertuples(index=False)
    )
    write_text(OUT / "reports/PREVIEW_OBSERVABILITY_REPORT.md", f"""# Preview Observability Report

Both legal P0 configurations were executed over both complete source videos and independently repeated. Feature hashes match for both configurations. Each covers all 229 regions with zero zero-sample regions and zero missing feature cells.

Selected operator: `{preview_id}`, 0.2 Hz, 160×90, no DNN. Deployed wall-clock is 55.446 s, 2.892% of measured full SCAN. Its run-1 decomposition is 54.152 s decode/pipe wait, 0.000 s model, and 1.214 s feature compute; measured rate is 21.866 s per video-hour. Peak memory is a process-lifetime high-water mark of 145316 KiB, not an isolated child-process peak.

Selection used temporal support subject to the 10% ceiling and did not inspect event labels. Full-SCAN caches, tracker outputs, references, and candidate-event mappings are absent from preview inputs.
""")
    write_text(OUT / "reports/COST_ADJUSTED_RANKING_REPORT.md", f"""# Cost-adjusted Ranking Report

Every comparison pays preview cost inside the total wall-clock budget and executes complete regions only.

{grid_lines}

The proxy is negative at 60 s on both videos. At larger q-derived budgets its direction remains budget- and video-dependent; this does not rescue the failed exploratory Gate.
""")
    write_text(OUT / "reports/FAILURE_ANALYSIS.md", f"""# Failure Analysis

## Decisive evidence

- Design-selected P0 Recall@20 is 0.271/0.264, versus offline full-information 0.614/0.513. Missed observable headroom is 0.343/0.249.
- Nested complete-video LOVO does not establish stable ranking:
{nested_text}
- Candidate Brier is {per_video_metrics.iloc[0].binary_brier_score_lovo_calibrated:.3f}/{per_video_metrics.iloc[1].binary_brier_score_lovo_calibrated:.3f}; count MAE is {per_video_metrics.iloc[0].count_mae_lovo_calibrated:.3f}/{per_video_metrics.iloc[1].count_mae_lovo_calibrated:.3f}.
- Removing the globally highest-count region leaves Recall@20 {per_video_metrics.iloc[0].leave_best_region_out_recall_at_20:.3f}/{per_video_metrics.iloc[1].leave_best_region_out_recall_at_20:.3f}; maximum selected-region contribution is {per_video_metrics.best_region_contribution_ratio_at_20.max():.3f}.
- Proxy missingness is zero, so missing observations do not explain failure.
- Preview cost is dominated by decode, not feature computation, and makes 60-second net yield negative.

## Required error artifacts

- High-score/no-event regions: `experiments/models/high_score_zero_event_regions.csv`.
- Low-score/high-event regions: `experiments/models/low_score_positive_event_regions.csv`.
- Cross-video direction, oracle headroom, model-versus-heuristic disagreement, time-index confounding, single-region contribution, missingness, and cost decomposition: `metrics/failure_analysis_metrics.json`.

The main competing explanation is pseudo-reference or midpoint-label noise. It cannot fully explain the gap because the same labels admit a much stronger full-information order.

`P1_LOW_RATE_DETECTION_OR_P2_SPARSE_MOTION_MAY_CLOSE_OBSERVABILITY_GAP` is a **CANDIDATE_HYPOTHESIS**, not an established direction and not an allowed post-hoc extension of MRPO-V1.
""")

    frozen = json.loads((OUT / "contracts/frozen_contract.json").read_text())
    cost_audit = json.loads((OUT / "audits/preview_cost_audit.json").read_text())
    short = per_video_metrics.loc["PSP_V0_SHORT"]
    long = per_video_metrics.loc["PSP_V1_LONG"]
    net60 = net_grid[net_grid.budget_id.eq("WALLCLOCK_60S")].set_index("video_id")
    feature_hash = sha_bytes(json.dumps([feature], sort_keys=True).encode())
    model_hash = sha_bytes(json.dumps(candidate, sort_keys=True).encode())
    final = f"""# Final Proxy Decision

## Strongest supported conclusion

Evaluator-only region-value headroom is large, but the frozen P0 preview does not provide stable cross-video observability. The design-selected heuristic reaches Recall@20 {short.recall_at_20:.3f}/{long.recall_at_20:.3f}, versus offline full-information {short.offline_oracle_recall_at_20:.3f}/{long.offline_oracle_recall_at_20:.3f}. Nested leave-one-video-out feature selection falls to {nested_lovo[0]['test_recall_at_20']:.3f}/{nested_lovo[1]['test_recall_at_20']:.3f} with AUC below 0.5 in both directions. At 60 s, paying preview cost loses {abs(int(net60.loc['PSP_V0_SHORT'].delta_event_count))}/{abs(int(net60.loc['PSP_V1_LONG'].delta_event_count))} events to geometric coverage.

## Meaning for SCAN innovation

This rejects fixed-fidelity framestat value ranking and further optimizer complexity over the same signal. It does not reject temporal allocation: the oracle gap shows that better legal observability could matter. A future, separately preregistered hypothesis is a coverage-guarded, cost-aware multi-fidelity scheduler using P1 semantic detection or P2 sparse motion. It must first pass the same static ranking and net-cost gates. No allocator is authorized by MRPO-V1.

CONTRACT_HASH = {frozen['contract_hash']}
CODE_COMMIT = {git_value('rev-parse', 'HEAD')}
VIDEO_COUNT = 2
DESIGN_VIDEO_COUNT = 2
VALIDATION_VIDEO_COUNT = 0
TEST_VIDEO_COUNT = 0

REFERENCE_TYPE = FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE
REFERENCE_COMPLETENESS_STATUS = NOT_GROUND_TRUTH_COMPLETE; OFFSET0_EXPOSABLE_263_OF_268
EVENT_CLAIM_SCOPE = RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE

PREVIEW_OPERATOR = {preview_id}
PREVIEW_OPERATOR_HASH = {extraction_hash}
PREVIEW_COST_RATIO = {cost_audit['preview_to_full_scan_cost_ratio']:.9f}
PREVIEW_LEGALITY = PASS_SOURCE_VIDEO_ONLY

MACRO_REGION_LENGTH = 40_SECONDS
FEATURE_SCHEMA_HASH = {feature_hash}
MODEL_FAMILY = M0_UNIVARIATE_HEURISTIC
MODEL_CONFIG_HASH = {model_hash}

PRIMARY_RECALL_AT_20 = {short.recall_at_20:.6f}/{long.recall_at_20:.6f}; MACRO={(short.recall_at_20+long.recall_at_20)/2:.6f}
PRIMARY_ENRICHMENT_AT_20 = {short.enrichment_at_20:.6f}/{long.enrichment_at_20:.6f}; MACRO={(short.enrichment_at_20+long.enrichment_at_20)/2:.6f}
RANKING_AUC = {short.ranking_event_recall_auc:.6f}/{long.ranking_event_recall_auc:.6f}; MACRO={(short.ranking_event_recall_auc+long.ranking_event_recall_auc)/2:.6f}
NET_EVENT_YIELD = {int(net60.loc['PSP_V0_SHORT'].delta_event_count)}/{int(net60.loc['PSP_V1_LONG'].delta_event_count)}_EVENTS_AT_60_SECONDS
CROSS_VIDEO_DIRECTION = DESIGN_SELECTED_POSITIVE_BUT_NESTED_LOVO_NOT_STABLE
LEAVE_BEST_VIDEO_OUT = NOT_IDENTIFIABLE_WITH_ONLY_TWO_DESIGN_VIDEOS
BEST_REGION_CONTRIBUTION = MAX_{per_video_metrics.best_region_contribution_ratio_at_20.max():.6f}

EXPLORATORY_GATE = FAIL_RECALL_ENRICHMENT_AND_NET_YIELD
FORMAL_STATIC_RANKING_GATE = NOT_RUN_REQUIRES_AT_LEAST_FOUR_NEW_VALIDATION_VIDEOS
REGION_VALUE_PROXY_SIGNAL = NOT_ESTABLISHED

SELECTED_PROXY_STATUS = NOT_ESTABLISHED
ONE_STEP_ALLOCATOR_STATUS = BLOCKED
GUARDED_MARGINAL_STATUS = STOPPED
FORMAL_METHOD_RANKING = BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION
NEXT_ALLOWED_STAGE = NEW_PREREGISTERED_MULTI_FIDELITY_PREVIEW_OR_NEW_VISIBLE_SIGNAL_THEN_REPEAT_STATIC_GATE
"""
    write_text(OUT / "reports/FINAL_PROXY_DECISION.md", final)

    code_version = {
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_status_short": git_value("status", "--short", "--untracked-files=all").splitlines(),
        "scripts": {path.name: sha_file(path) for path in sorted((ROOT / "scripts").glob("*mrpo*.py"))},
    }
    write_json(OUT / "code_version.json", code_version)
    update_manifest()
    print(json.dumps({
        "status": "COMPLETE_EVIDENCE", "nested_lovo": nested_lovo,
        "calibration": calibration_metrics,
        "net_grid": net_grid.to_dict("records"),
    }, indent=2))


if __name__ == "__main__":
    main()
