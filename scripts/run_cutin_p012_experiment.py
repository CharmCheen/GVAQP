#!/usr/bin/env python3
"""Run frozen grouped P0/P1/P2 candidate and event experiments."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import time
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from cutin_p012_common import (
    CONTRACT, MODELING, OUT, P0_FEATURES, P1_INCREMENTAL, P2_INCREMENTAL,
    POOL, ROOT, SEED, STAGE, read_json, sha256_file, utc_now, write_json,
)

warnings.filterwarnings("ignore", category=UserWarning)

LOGISTIC_CONFIGS = [
    {"C": c, "class_weight": weight}
    for c, weight in itertools.product([.01, .1, 1., 10.], [None, "balanced"])
]
LGBM_CONFIGS = [
    {"num_leaves": leaves, "max_depth": depth, "learning_rate": rate, "min_child_samples": child}
    for leaves, depth, rate, child in itertools.product([7, 15], [3, 6], [.03, .10], [10, 30])
]
META = [
    "candidate_id", "physical_call_id", "source_dataset", "session_id", "query_id",
    "unit_id", "window_start", "window_end",
]


def safe_auprc(y, score) -> float | None:
    return float(average_precision_score(y, score)) if len(np.unique(y)) == 2 else None


def safe_auroc(y, score) -> float | None:
    return float(roc_auc_score(y, score)) if len(np.unique(y)) == 2 else None


def ece(y, score, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = len(y)
    value = 0.0
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (score >= left) & (score < right if right < 1 else score <= right)
        if mask.any():
            value += mask.mean() * abs(float(np.mean(y[mask])) - float(np.mean(score[mask])))
    return float(value)


def fit_logistic(x: pd.DataFrame, y: np.ndarray, config: dict[str, Any]):
    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True),
        StandardScaler(),
        LogisticRegression(
            C=config["C"], class_weight=config["class_weight"], penalty="l2",
            max_iter=3000, random_state=SEED,
        ),
    )
    model.fit(x, y)
    return model


def fit_lgbm(
    x: pd.DataFrame, y: np.ndarray, config: dict[str, Any],
    eval_x: pd.DataFrame | None = None, eval_y: np.ndarray | None = None,
    estimators: int = 500,
):
    model = lgb.LGBMClassifier(
        **config, n_estimators=estimators, objective="binary",
        random_state=SEED, deterministic=True, force_col_wise=True,
        verbosity=-1, n_jobs=1,
    )
    kwargs = {}
    if eval_x is not None:
        kwargs = {
            "eval_set": [(eval_x, eval_y)], "eval_metric": "average_precision",
            "callbacks": [lgb.early_stopping(30, verbose=False)],
        }
    model.fit(x, y, **kwargs)
    return model


def tune(
    family: str, x: pd.DataFrame, y: np.ndarray, groups: np.ndarray, inner_folds: np.ndarray,
) -> tuple[dict[str, Any], int]:
    configs = LOGISTIC_CONFIGS if family == "LOGISTIC" else LGBM_CONFIGS
    ranked = []
    for index, config in enumerate(configs):
        pred = np.full(len(y), np.nan)
        iterations = []
        for inner_fold in range(3):
            train, dev = np.flatnonzero(inner_folds != inner_fold), np.flatnonzero(inner_folds == inner_fold)
            if family == "LOGISTIC":
                model = fit_logistic(x.iloc[train], y[train], config)
            else:
                model = fit_lgbm(x.iloc[train], y[train], config, x.iloc[dev], y[dev])
                iterations.append(int(model.best_iteration_ or 500))
            pred[dev] = model.predict_proba(x.iloc[dev])[:, 1]
        score = average_precision_score(y, pred)
        ranked.append((-float(score), index, config, int(np.median(iterations)) if iterations else 0))
    ranked.sort(key=lambda row: (row[0], row[1]))
    _, _, config, iteration = ranked[0]
    return config, iteration


def load_data() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    split = pd.read_csv(OUT / "split_manifest.csv", keep_default_na=False)
    labels = pd.read_csv(POOL / "ORACLE_LABEL_MANIFEST.csv", keep_default_na=False)
    labels = labels[labels.query_id.eq("Q1")].copy()
    labels["candidate_id"] = labels.verification_key
    labels["label_binary"] = labels.projected_label.map({"negative": 0, "positive": 1})
    join = split.merge(
        labels[["candidate_id", "label_binary", "generation_runtime_seconds"]]
        if "generation_runtime_seconds" in labels else labels[["candidate_id", "label_binary"]],
        on="candidate_id", how="left", validate="one_to_one",
    )
    calls = pd.read_csv(POOL / "ORACLE_CALL_MANIFEST.csv", keep_default_na=False)
    call_latency = calls.set_index("physical_call_id").generation_runtime_seconds.astype(float).to_dict()
    label_call = labels.set_index("candidate_id").physical_call_id.to_dict()
    join["oracle_latency_sec"] = join.candidate_id.map(lambda x: call_latency[label_call[x]])
    sample = pd.read_csv(STAGE / "STAGE_A_FROZEN_SAMPLE.csv", keep_default_na=False)
    sample["candidate_id"] = (
        sample.source_dataset.astype(str) + "|" + sample.session_id.astype(str)
        + "|Q1|" + sample.unit_id.astype(int).astype(str)
    )
    join = join.merge(
        sample[["candidate_id", "q1_score"]].rename(columns={"q1_score": "existing_frozen_q1_score"}),
        on="candidate_id", how="left", validate="one_to_one",
    )
    reps = {}
    motion = pd.read_parquet(
        OUT / "features/p2.parquet", columns=["candidate_id", "global_motion_magnitude"]
    )
    for rep in ["p0", "p1", "p2"]:
        features = pd.read_parquet(OUT / f"features/{rep}.parquet")
        if "global_motion_magnitude" not in features:
            features = features.merge(motion, on="candidate_id", how="left", validate="one_to_one")
        frame = features.merge(join, on="candidate_id", how="inner", suffixes=("", "_audit"), validate="one_to_one")
        reps[rep.upper()] = frame
    return reps, join


def run_grouped_oof(reps: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict, dict]:
    all_predictions = []
    selections: dict[str, list[dict]] = defaultdict(list)
    importances: dict[str, list[dict[str, float]]] = defaultdict(list)
    feature_sets = {
        "P0": P0_FEATURES,
        "P1": P0_FEATURES + P1_INCREMENTAL,
        "P2": P0_FEATURES + P1_INCREMENTAL + P2_INCREMENTAL,
    }
    for rep, frame in reps.items():
        valid = frame.valid_for_confirmatory.astype(str).str.lower().eq("true")
        for family in ["LOGISTIC", "LIGHTGBM"]:
            method = f"{rep}-{family}"
            for fold in range(5):
                train = valid & frame.outer_fold.ne(fold)
                test = frame.outer_fold.eq(fold)
                x_train = frame.loc[train, feature_sets[rep]]
                y_train = frame.loc[train, "label_binary"].astype(int).to_numpy()
                groups = frame.loc[train, "split_group_id"].to_numpy()
                inner_folds = frame.loc[train, f"inner_fold_outer_{fold}"].astype(int).to_numpy()
                if set(inner_folds) != {0, 1, 2}:
                    raise RuntimeError(f"Invalid frozen inner split for outer fold {fold}")
                config, iteration = tune(family, x_train, y_train, groups, inner_folds)
                started = time.perf_counter_ns()
                if family == "LOGISTIC":
                    model = fit_logistic(x_train, y_train, config)
                else:
                    # Early stopping on one grouped inner fold, then refit all outer-train rows
                    inner = (np.flatnonzero(inner_folds != 0), np.flatnonzero(inner_folds == 0))
                    early = fit_lgbm(
                        x_train.iloc[inner[0]], y_train[inner[0]], config,
                        x_train.iloc[inner[1]], y_train[inner[1]],
                    )
                    iteration = int(early.best_iteration_ or iteration or 500)
                    model = fit_lgbm(x_train, y_train, config, estimators=iteration)
                fit_seconds = (time.perf_counter_ns() - started) / 1e9
                started = time.perf_counter_ns()
                scores = model.predict_proba(frame.loc[test, feature_sets[rep]])[:, 1]
                inference_seconds = (time.perf_counter_ns() - started) / 1e9
                block = frame.loc[test, META + [
                    "candidate_status", "valid_for_confirmatory", "label_binary",
                    "reference_event_id", "split_group_id", "outer_fold", "oracle_latency_sec",
                    "global_motion_magnitude",
                ]].copy()
                block["method"] = method
                block["score"] = scores
                block["fit_seconds"] = fit_seconds
                # Store apportioned per-candidate inference so aggregation
                # recovers the measured fold batch time exactly once.
                block["inference_seconds"] = inference_seconds / max(1, len(block))
                block["selected_config"] = json.dumps(config, sort_keys=True)
                block["selected_iterations"] = iteration
                all_predictions.append(block)
                selections[method].append({"fold": fold, "config": config, "iterations": iteration})
                if family == "LIGHTGBM":
                    importances[method].append(dict(zip(feature_sets[rep], model.feature_importances_.astype(float))))
    # Direct raw score baseline.
    raw = reps["P0"][META + [
        "candidate_status", "valid_for_confirmatory", "label_binary", "reference_event_id",
        "split_group_id", "outer_fold", "oracle_latency_sec", "global_motion_magnitude",
    ]].copy()
    raw["method"] = "B-RAW-YOLO"
    raw["score"] = reps["P0"]["existing_frozen_q1_score"].to_numpy()
    raw["fit_seconds"] = 0.0; raw["inference_seconds"] = 0.0
    raw["selected_config"] = "{}"; raw["selected_iterations"] = 0
    all_predictions.append(raw)
    result = pd.concat(all_predictions, ignore_index=True)
    return result, selections, importances


def topk_metrics(block: pd.DataFrame, ks=(8, 16, 32)) -> dict[str, Any]:
    ordered = block.sort_values(["score", "candidate_id"], ascending=[False, True])
    valid = block[block.valid_for_confirmatory.astype(str).str.lower().eq("true")]
    y = valid.label_binary.astype(int).to_numpy()
    s = valid.score.astype(float).to_numpy()
    result = {
        "n": len(valid), "positives": int(y.sum()), "negatives": int((1-y).sum()),
        "auprc": safe_auprc(y, s), "auroc": safe_auroc(y, s),
        "brier": float(brier_score_loss(y, s)), "ece_10bin": ece(y, s),
    }
    for k in ks:
        head = ordered.head(k)
        if not head.valid_for_confirmatory.astype(str).str.lower().eq("true").all():
            result[f"precision_at_{k}"] = "INVALID_OUTSIDE_ORACLE_SUPPORT"
            result[f"recall_at_{k}"] = "INVALID_OUTSIDE_ORACLE_SUPPORT"
        else:
            positives = int(head.label_binary.astype(int).sum())
            result[f"precision_at_{k}"] = positives / len(head)
            result[f"recall_at_{k}"] = positives / max(1, int(y.sum()))
    return result


def motion_fpr(predictions: pd.DataFrame, method: str) -> dict[str, Any]:
    block = predictions[predictions.method.eq(method)].copy()
    flags = []
    counts = []
    thresholds = {}
    for fold in range(5):
        train = block[
            block.outer_fold.ne(fold)
            & block.valid_for_confirmatory.astype(str).str.lower().eq("true")
            & block.label_binary.eq(0)
        ]
        threshold = float(train.global_motion_magnitude.dropna().quantile(.8))
        thresholds[str(fold)] = threshold
        test = block[
            block.outer_fold.eq(fold) & block.label_binary.eq(0)
            & block.global_motion_magnitude.ge(threshold)
        ]
        flags.extend((test.score >= .5).tolist())
        counts.append(len(test))
    return {
        "threshold_policy": "training-fold negative global-motion 80th percentile",
        "classification_threshold": .5,
        "fold_thresholds": thresholds,
        "high_motion_negative_count": int(sum(counts)),
        "fpr": float(np.mean(flags)) if flags else None,
    }


def baseline_distributions(base: pd.DataFrame, reps: dict[str, pd.DataFrame], selections: dict) -> tuple[dict, pd.DataFrame]:
    valid = base.valid_for_confirmatory.astype(str).str.lower().eq("true")
    random_rows = []
    random_auprc = []
    for seed in range(100):
        rng = np.random.default_rng(SEED + seed)
        block = base.copy()
        block["score"] = rng.random(len(block))
        block["method"] = f"B-RANDOM-SEED-{seed:03d}"
        random_rows.append(block)
        v = block[valid]
        random_auprc.append(average_precision_score(v.label_binary.astype(int), v.score))
    # Shuffled P2 LightGBM, exact 20 training-fold-only permutations.
    shuffled_rows = []
    frame = reps["P2"]
    features = P0_FEATURES + P1_INCREMENTAL + P2_INCREMENTAL
    modal = Counter(
        json.dumps(x["config"], sort_keys=True) for x in selections["P2-LIGHTGBM"]
    ).most_common(1)[0][0]
    config = json.loads(modal)
    for seed in range(20):
        pieces = []
        for fold in range(5):
            train = frame.valid_for_confirmatory.astype(str).str.lower().eq("true") & frame.outer_fold.ne(fold)
            test = frame.outer_fold.eq(fold)
            y = frame.loc[train, "label_binary"].astype(int).to_numpy()
            rng = np.random.default_rng(SEED + 1000 + seed * 10 + fold)
            shuffled = rng.permutation(y)
            model = fit_lgbm(frame.loc[train, features], shuffled, config, estimators=160)
            piece = base[base.outer_fold.eq(fold)].copy()
            piece["score"] = model.predict_proba(frame.loc[test, features])[:, 1]
            pieces.append(piece)
        one = pd.concat(pieces, ignore_index=True)
        one["method"] = f"B-SHUFFLED-SEED-{seed:02d}"
        shuffled_rows.append(one)
    summary = {
        "B-RANDOM": {
            "seeds": 100, "mean_auprc": float(np.mean(random_auprc)),
            "ci95": [float(np.quantile(random_auprc, .025)), float(np.quantile(random_auprc, .975))],
        },
        "B-SHUFFLED": {"permutations": 20, "policy": "training-fold labels only; P2 LightGBM fixed modal inner-selected config"},
    }
    return summary, pd.concat(random_rows + shuffled_rows, ignore_index=True)


def event_metrics(predictions: pd.DataFrame, methods: list[str]) -> dict[str, Any]:
    return {
        "status": "BLOCKED_MISSING_FROZEN_MATCH_RULE",
        "reference_event_count": 0,
        "methods": {},
        "reason": (
            "The only K3 groups are derived directly from the same projected "
            "candidate labels and are not an independent EventRelation reference."
        ),
        "blocked_metrics": [
            "distinct_event_recall_at_8_16_32", "event_recall_confirm_calls_auc",
            "duplicate_candidate_rate", "candidates_per_recovered_event",
            "unrecovered_reference_events",
        ],
    }


def paired_bootstrap(predictions: pd.DataFrame, comparisons: list[tuple[str, str]]) -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    out = {"replicates": 10000, "resampling_unit": "split_group_id", "comparisons": {}}
    for better, base in comparisons:
        a = predictions[predictions.method.eq(better)]
        b = predictions[predictions.method.eq(base)]
        merged = a[["candidate_id", "split_group_id", "label_binary", "valid_for_confirmatory", "score"]].merge(
            b[["candidate_id", "score"]], on="candidate_id", suffixes=("_a", "_b"), validate="one_to_one"
        )
        merged = merged[merged.valid_for_confirmatory.astype(str).str.lower().eq("true")]
        groups = sorted(merged.split_group_id.unique())
        group_blocks = {g: merged[merged.split_group_id.eq(g)] for g in groups}
        deltas = []
        for g, block in group_blocks.items():
            signed = np.where(block.label_binary.eq(1), block.score_a - block.score_b, block.score_b - block.score_a)
            deltas.append((g, float(np.mean(signed))))
        bootstrap = np.empty(10000)
        for index in range(10000):
            sampled = rng.choice(groups, size=len(groups), replace=True)
            block = pd.concat([group_blocks[g] for g in sampled], ignore_index=True)
            bootstrap[index] = average_precision_score(block.label_binary.astype(int), block.score_a) - average_precision_score(block.label_binary.astype(int), block.score_b)
        aggregate = average_precision_score(merged.label_binary.astype(int), merged.score_a) - average_precision_score(merged.label_binary.astype(int), merged.score_b)
        best_group = max(deltas, key=lambda x: x[1])[0]
        leave = merged[merged.split_group_id.ne(best_group)]
        leave_delta = average_precision_score(leave.label_binary.astype(int), leave.score_a) - average_precision_score(leave.label_binary.astype(int), leave.score_b)
        win_rate = float(np.mean([delta >= 0 for _, delta in deltas]))
        out["comparisons"][f"{better}_minus_{base}"] = {
            "metric": "pooled_grouped_oof_auprc",
            "aggregate_delta": float(aggregate),
            "ci95": [float(np.quantile(bootstrap, .025)), float(np.quantile(bootstrap, .975))],
            "group_win_rate_signed_margin": win_rate,
            "median_per_group_signed_margin_delta": float(np.median([d for _, d in deltas])),
            "best_group": best_group,
            "leave_best_group_out_delta": float(leave_delta),
            "not_single_group_driven": bool(aggregate > 0 and win_rate > .5 and leave_delta > 0),
            "group_metric_note": "Most sessions have one row, so per-group AUPRC is undefined; win rate uses label-signed score-margin improvement.",
        }
    return out


def runtime_profile(predictions: pd.DataFrame) -> dict[str, Any]:
    samples = pd.read_csv(OUT / "features/runtime_samples.csv")
    repeated = pd.read_csv(OUT / "features/runtime_repeated_samples.csv")
    total_video = samples.video_seconds.sum()
    components = {}
    mapping = {
        "video_decode_scan": "decode_seconds",
        "YOLO_detection": "detection_seconds", "ByteTrack_incremental": "tracking_seconds",
        "camera_motion_incremental": "motion_seconds", "feature_aggregation": "aggregation_seconds",
    }
    for name, column in mapping.items():
        values = repeated[column].to_numpy()
        total = float(values.sum())
        components[name] = {
            "measurement_count": len(values), "mean_runtime_sec": float(np.mean(values)),
            "median_runtime_sec": float(np.median(values)), "p90_runtime_sec": float(np.quantile(values, .9)),
            "fps": float(repeated.sampled_frames.sum() / total) if total else None,
            "seconds_per_video_hour": float(np.mean(values) / repeated.video_seconds.mean() * 3600),
            "peak_gpu_memory_mib": float(repeated.peak_gpu_memory_mib.max()),
            "peak_cpu_memory_mib": float(repeated.peak_cpu_memory_mib.max()),
        }
    inference = predictions[predictions.method.str.contains("P[012]-", regex=True)].groupby("method").inference_seconds.sum()
    components["classifier_inference"] = {
        "measurement_count": int(len(inference)), "mean_runtime_sec": float(inference.mean()),
        "median_runtime_sec": float(inference.median()), "p90_runtime_sec": float(inference.quantile(.9)),
        "fps": float(96 / inference.mean()) if inference.mean() else None,
        "seconds_per_video_hour": float(inference.mean() / total_video * 3600),
        "peak_gpu_memory_mib": 0.0, "peak_cpu_memory_mib": float(samples.peak_cpu_memory_mib.max()),
    }
    return {
        "hardware": read_json(OUT / "environment_lock.json")["gpu"],
        "same_resolution_policy": "per frozen source frame; YOLO imgsz=640; motion long-side=320; sample_fps=5",
        "cached_features_charged": True, "components": components,
        "feature_cost_per_candidate": {
            "P0": float(samples[["decode_seconds", "detection_seconds", "aggregation_seconds"]].sum(axis=1).mean()),
            "P1": float(samples[["decode_seconds", "detection_seconds", "tracking_seconds", "aggregation_seconds"]].sum(axis=1).mean()),
            "P2": float(samples[["decode_seconds", "detection_seconds", "tracking_seconds", "motion_seconds", "aggregation_seconds"]].sum(axis=1).mean()),
        },
    }


def run_loso(reps: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    feature_sets = {
        "P0": P0_FEATURES, "P1": P0_FEATURES + P1_INCREMENTAL,
        "P2": P0_FEATURES + P1_INCREMENTAL + P2_INCREMENTAL,
    }
    fixed_logistic = {"C": 1., "class_weight": "balanced"}
    fixed_lgbm = {"num_leaves": 7, "max_depth": 3, "learning_rate": .03, "min_child_samples": 10}
    for rep, frame in reps.items():
        valid = frame.valid_for_confirmatory.astype(str).str.lower().eq("true")
        for group in sorted(frame.loc[valid, "split_group_id"].unique()):
            train = valid & frame.split_group_id.ne(group)
            test = valid & frame.split_group_id.eq(group)
            for family, config in [("LOGISTIC", fixed_logistic), ("LIGHTGBM", fixed_lgbm)]:
                if family == "LOGISTIC":
                    model = fit_logistic(frame.loc[train, feature_sets[rep]], frame.loc[train, "label_binary"].astype(int).to_numpy(), config)
                else:
                    model = fit_lgbm(frame.loc[train, feature_sets[rep]], frame.loc[train, "label_binary"].astype(int).to_numpy(), config, estimators=160)
                block = frame.loc[test, ["candidate_id", "session_id", "split_group_id", "label_binary"]].copy()
                block["method"] = f"{rep}-{family}"
                block["score"] = model.predict_proba(frame.loc[test, feature_sets[rep]])[:, 1]
                block["config_scope"] = "a_priori_fixed_auxiliary_loso"
                rows.append(block)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-loso", action="store_true")
    args = parser.parse_args()
    freeze = read_json(OUT / "contract_freeze.json")
    if sha256_file(CONTRACT) != freeze["contract_sha256"]:
        raise SystemExit("Frozen contract changed")
    if not (OUT / "features/extraction_complete.json").is_file():
        raise SystemExit("Run frozen feature extraction first")
    reps, _ = load_data()
    predictions, selections, importances = run_grouped_oof(reps)
    base = predictions[predictions.method.eq("B-RAW-YOLO")].copy()
    baseline_summary, baseline_predictions = baseline_distributions(base, reps, selections)
    pred_dir = OUT / "predictions"; pred_dir.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(pred_dir / "grouped_oof_predictions.parquet", index=False)
    predictions.to_csv(pred_dir / "grouped_oof_predictions.csv", index=False)
    baseline_predictions.to_parquet(pred_dir / "baseline_replication_predictions.parquet", index=False)
    if not args.skip_loso:
        loso = run_loso(reps)
        loso.to_parquet(pred_dir / "loso_predictions.parquet", index=False)
        loso.to_csv(pred_dir / "loso_predictions.csv", index=False)
    metric_dir = OUT / "metrics"; metric_dir.mkdir(parents=True, exist_ok=True)
    methods = sorted(predictions.method.unique())
    candidate = {"primary_metric": "grouped_oof_auprc", "methods": {}, "baselines": baseline_summary}
    for method in methods:
        block = predictions[predictions.method.eq(method)]
        candidate["methods"][method] = topk_metrics(block)
        candidate["methods"][method]["high_global_motion_negative_fpr"] = motion_fpr(predictions, method)
    # Full candidate-metric summaries for random/shuffled replications.
    for prefix in ["B-RANDOM", "B-SHUFFLED"]:
        rep_metrics = []
        for method, block in baseline_predictions.groupby("method"):
            if method.startswith(prefix):
                rep_metrics.append(topk_metrics(block))
        summaries = {}
        for key in rep_metrics[0]:
            values = [row[key] for row in rep_metrics if isinstance(row[key], (int, float)) and row[key] is not None]
            if len(values) != len(rep_metrics):
                summaries[key] = {
                    "status": "INVALID_OUTSIDE_ORACLE_SUPPORT",
                    "valid_replicates": len(values),
                    "invalid_replicates": len(rep_metrics) - len(values),
                    "conditional_mean_prohibited": True,
                }
            else:
                summaries[key] = {
                    "mean": float(np.mean(values)),
                    "ci95": [float(np.quantile(values, .025)), float(np.quantile(values, .975))],
                }
        candidate["baselines"][prefix]["candidate_metric_distribution"] = summaries
        candidate["baselines"][prefix]["auprc_mean"] = summaries["auprc"]["mean"]
        candidate["baselines"][prefix]["auprc_ci95"] = summaries["auprc"]["ci95"]
    write_json(metric_dir / "candidate_metrics.json", candidate)
    events = event_metrics(predictions, methods)
    write_json(metric_dir / "event_metrics.json", events)
    bootstrap = paired_bootstrap(predictions, [
        ("P1-LOGISTIC", "P0-LOGISTIC"), ("P1-LIGHTGBM", "P0-LIGHTGBM"),
        ("P2-LOGISTIC", "P1-LOGISTIC"), ("P2-LIGHTGBM", "P1-LIGHTGBM"),
    ])
    write_json(metric_dir / "paired_bootstrap.json", bootstrap)
    per_group = []
    for method, block in predictions.groupby("method"):
        valid = block[block.valid_for_confirmatory.astype(str).str.lower().eq("true")]
        for group, rows in valid.groupby("split_group_id"):
            per_group.append({
                "method": method, "split_group_id": group, "n": len(rows),
                "positives": int(rows.label_binary.sum()),
                "mean_score": float(rows.score.mean()),
                "mean_signed_margin": float(np.mean(np.where(rows.label_binary.eq(1), rows.score, 1-rows.score))),
                "auprc": safe_auprc(rows.label_binary.astype(int), rows.score),
            })
    pd.DataFrame(per_group).to_csv(metric_dir / "per_group_metrics.csv", index=False)
    write_json(OUT / "runtime_profile.json", runtime_profile(predictions))
    write_json(metric_dir / "feature_importance.json", {
        method: {
            feature: float(np.mean([fold.get(feature, 0.0) for fold in folds]))
            for feature in sorted(set().union(*(fold.keys() for fold in folds)))
        } for method, folds in importances.items()
    })
    write_json(metric_dir / "selected_hyperparameters.json", selections)
    system = {
        "status": "NOT_ESTABLISHED",
        "formal_deadline_metrics": "NOT_ESTABLISHED",
        "reason": (
            "No independent frozen event mapping, complete Oracle policy support, "
            "or ARC deadline/SCAN trace matches the Stage-A candidate universe."
        ),
        "arc_component_replacement": "BLOCKED_ASSET_MISMATCH",
        "costs_charged": read_json(OUT / "runtime_profile.json")["feature_cost_per_candidate"],
        "event_system_metrics": "BLOCKED_MISSING_FROZEN_MATCH_RULE",
        "supported_results": "CANDIDATE_ONLY_COST_REPLAY",
    }
    write_json(metric_dir / "system_metrics.json", system)
    write_json(OUT / "experiment_complete.json", {
        "status": "COMPLETE", "created_at_utc": utc_now(), "new_oracle_calls": 0,
        "candidate_metrics_sha256": sha256_file(metric_dir / "candidate_metrics.json"),
        "event_metrics_sha256": sha256_file(metric_dir / "event_metrics.json"),
        "paired_bootstrap_sha256": sha256_file(metric_dir / "paired_bootstrap.json"),
    })
    print(json.dumps({
        method: candidate["methods"][method]["auprc"] for method in methods
    }, indent=2))


if __name__ == "__main__":
    main()
