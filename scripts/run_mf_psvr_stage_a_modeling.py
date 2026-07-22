#!/usr/bin/env python3
"""Train, evaluate, and audit MF-PSVR Stage-A value models.

The primary comparison is exact leave-one-provider-session-out on the frozen
development roles.  The preassigned pool-audit role is never used for model
selection or fitting.  All persisted predictions are query-aligned semantic
samples; abstentions remain in the source dataset but are excluded from binary
losses and metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import torch
from sklearn.base import BaseEstimator
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
CYCLE = ROOT / "outputs/mf_psvr_publication_program/cycle_01_training_pool"
STAGE = CYCLE / "stage_a"
OUT = STAGE / "modeling"
MODELS = OUT / "models"
DATASET = OUT / "STAGE_A_CANDIDATE_VALUE_DATASET.parquet"
FEATURE_SCHEMA = OUT / "STAGE_A_FEATURE_SCHEMA.json"
DATASET_AUDIT = OUT / "STAGE_A_DATASET_COMPLETION_AUDIT.json"
TEMPORAL = OUT / "STAGE_A_TEMPORAL_SEQUENCES.npz"
TEMPORAL_SCHEMA = OUT / "STAGE_A_TEMPORAL_FEATURE_SCHEMA.json"
PROTOCOL = OUT / "STAGE_A_MODELING_PROTOCOL.json"
PROTOCOL_PROVENANCE = OUT / "STAGE_A_MODELING_PROTOCOL_PROVENANCE.json"
ORACLE_AUDIT = STAGE / "STAGE_A_ORACLE_ROUNDTRIP_VERIFICATION_AUDIT.json"
EXECUTION_DIFFERENCE = STAGE / "STAGE_A_EXECUTION_DIFFERENCE_AUDIT.json"
SUPPORT_REPORT = STAGE / "STAGE_A_SUPPORT_REPORT.md"
PREDICTIONS = OUT / "STAGE_A_GROUPED_PREDICTIONS.parquet"
METRICS = OUT / "STAGE_A_MODEL_METRICS.csv"
AUXILIARY = OUT / "STAGE_A_AUXILIARY_EVALUATION.csv"
CONTROLS = OUT / "STAGE_A_CONTROL_SUMMARY.csv"
PER_SOURCE = OUT / "STAGE_A_PER_SOURCE_RESULTS.csv"
PER_QUERY = OUT / "STAGE_A_PER_QUERY_RESULTS.csv"
FEATURE_IMPORTANCE = OUT / "FEATURE_IMPORTANCE.csv"
CALIBRATION_CURVES = OUT / "CALIBRATION_CURVES.csv"
BOOTSTRAP_INTERVALS = OUT / "STAGE_A_GROUP_BOOTSTRAP_INTERVALS.csv"
HARD_NEGATIVES = OUT / "HARD_NEGATIVE_CASES.csv"
HARD_POSITIVES = OUT / "HARD_POSITIVE_CASES.csv"
MODEL_HASHES = OUT / "MODEL_HASHES.json"
BEST_VALUE = OUT / "BEST_STAGE_A_VALUE_MODEL.json"
BEST_TEMPORAL = OUT / "BEST_STAGE_A_TEMPORAL_REFINER.json"
READINESS = OUT / "STAGE_A_MODEL_READINESS_DECISION.json"
MODEL_CARD = OUT / "STAGE_A_MODEL_CARD.md"
AUDIT = OUT / "STAGE_A_MODELING_COMPLETION_AUDIT.json"
FINAL_REPORT = STAGE / "STAGE_A_TO_MODEL_FINAL_REPORT.md"

SEED = 20260719
DEVELOPMENT_ROLES = {"model_train", "model_calibration"}
AGGREGATE_MODELS = ["M0_LOGISTIC", "M1_CALIBRATED_LOGISTIC", "M2_LIGHTGBM"]
TEMPORAL_MODELS = ["TCN_TEMPORAL", "GRU_TEMPORAL"]
PRIMARY_MODELS = ["B0_RAW_YOLO", "B1_FIFO", *AGGREGATE_MODELS, *TEMPORAL_MODELS]
AGGREGATE_QUERY_ABLATIONS = {
    "M0_LOGISTIC": "M0_NO_EXPLICIT_QUERY",
    "M1_CALIBRATED_LOGISTIC": "M1_NO_EXPLICIT_QUERY",
    "M2_LIGHTGBM": "M2_NO_EXPLICIT_QUERY",
}
ALL_PREDICTION_MODELS = [
    *PRIMARY_MODELS,
    *AGGREGATE_QUERY_ABLATIONS.values(),
    "SOURCE_ID_ONLY",
    "SESSION_ID_ONLY",
    "QUERY_ID_ONLY",
    "SELECTION_STRATUM_ONLY",
    "ANCHOR_ID_ONLY",
]
IDENTITY_CONTROLS = ["SOURCE_ID_ONLY", "SESSION_ID_ONLY", "QUERY_ID_ONLY"]
POSTHOC_NUISANCE_CONTROLS = ["SELECTION_STRATUM_ONLY", "ANCHOR_ID_ONLY"]
CATEGORICAL_CONTROL_COLUMNS = {
    "SOURCE_ID_ONLY": "source_dataset",
    "SESSION_ID_ONLY": "session_id",
    "QUERY_ID_ONLY": "query_id",
    "SELECTION_STRATUM_ONLY": "sampling_stratum",
    "ANCHOR_ID_ONLY": "anchor_id",
}
BOOTSTRAP_REPETITIONS = 2000
FORBIDDEN_FEATURES = {
    "source_dataset", "session_id", "source_sha256", "physical_call_id",
    "semantic_sample_id", "verification_key", "anchor_id", "event_group_id",
    "raw_response_sha256", "oracle_projected_label", "label_binary", "label_status",
    "parse_status", "oracle_confidence", "oracle_generic_label",
    "oracle_generic_involved_object", "model_split_role", "sampling_stratum",
    "unit_id", "unit_start_seconds", "unit_end_seconds", "witness_track_id",
    "witness_class_id",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode())


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    atomic_bytes(path, frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))


def atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".parquet", dir=path.parent)
    os.close(descriptor)
    try:
        frame.to_parquet(temporary, index=False, engine="pyarrow", compression="zstd")
        with open(temporary, "rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_joblib(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".joblib", dir=path.parent)
    os.close(descriptor)
    try:
        joblib.dump(value, temporary, compress=3)
        with open(temporary, "rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_torch(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".pt", dir=path.parent)
    os.close(descriptor)
    try:
        torch.save(value, temporary)
        with open(temporary, "rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def finite_or_none(value: Any) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def stable_logit(probability: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probability, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(clipped / (1 - clipped))


def sigmoid(value: np.ndarray) -> np.ndarray:
    value = np.asarray(value, dtype=float)
    positive = value >= 0
    result = np.empty_like(value)
    result[positive] = 1.0 / (1.0 + np.exp(-value[positive]))
    exp_value = np.exp(value[~positive])
    result[~positive] = exp_value / (1.0 + exp_value)
    return result


def ece_score(y: np.ndarray, probability: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=int)
    probability = np.clip(np.asarray(probability, dtype=float), 0, 1)
    edges = np.linspace(0, 1, bins + 1)
    assignments = np.minimum(np.digitize(probability, edges[1:-1], right=False), bins - 1)
    result = 0.0
    for index in range(bins):
        selected = assignments == index
        if selected.any():
            result += selected.mean() * abs(float(y[selected].mean()) - float(probability[selected].mean()))
    return float(result)


def score_metrics(y: np.ndarray, probability: np.ndarray, ids: np.ndarray) -> dict[str, Any]:
    y = np.asarray(y, dtype=int)
    probability = np.clip(np.asarray(probability, dtype=float), 0, 1)
    ids = np.asarray(ids, dtype=str)
    order = np.lexsort((ids, -probability))
    result: dict[str, Any] = {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "negatives": int(len(y) - y.sum()),
        "auprc": float(average_precision_score(y, probability)) if len(np.unique(y)) == 2 else np.nan,
        "brier": float(brier_score_loss(y, probability)) if len(y) else np.nan,
        "ece": ece_score(y, probability) if len(y) else np.nan,
    }
    total_positive = int(y.sum())
    for budget in (8, 16, 32):
        actual = min(budget, len(y))
        recovered = int(y[order[:actual]].sum())
        result[f"semantic_budget_{budget}_actual"] = actual
        result[f"semantic_precision_at_{budget}"] = recovered / actual if actual else np.nan
        result[f"semantic_recall_at_{budget}"] = recovered / total_positive if total_positive else np.nan
        result[f"semantic_top_{budget}_positive_recovery"] = recovered
    return result


def physical_call_budget_metrics(scoped: pd.DataFrame, model: str) -> dict[str, Any]:
    calls = (
        scoped.groupby("physical_call_id", sort=True)
        .agg(
            label_binary=("label_binary", "max"),
            probability=(model, "max"),
            semantic_rows=("semantic_sample_id", "size"),
        )
        .reset_index()
    )
    y = calls["label_binary"].to_numpy(dtype=int)
    probability = calls["probability"].to_numpy(dtype=float)
    ids = calls["physical_call_id"].astype(str).to_numpy()
    order = np.lexsort((ids, -probability))
    positives = int(y.sum())
    result: dict[str, Any] = {
        "physical_calls": int(len(calls)),
        "physical_positive_calls": positives,
        "physical_call_probability_aggregation": "max_Q1_Q2_probability",
        "physical_call_label_aggregation": "positive_if_any_query_positive",
    }
    for budget in (8, 16, 32):
        actual = min(budget, len(calls))
        recovered = int(y[order[:actual]].sum())
        result[f"verify_call_budget_{budget}_actual"] = actual
        result[f"physical_call_precision_at_{budget}"] = recovered / actual if actual else np.nan
        result[f"physical_call_recall_at_{budget}"] = recovered / positives if positives else np.nan
        result[f"physical_call_top_{budget}_positive_recovery"] = recovered
    return result


def macro_query_metrics(scoped: pd.DataFrame, model: str) -> dict[str, Any]:
    per_query: list[dict[str, Any]] = []
    for _, part in scoped.groupby("query_id", sort=True):
        y = part["label_binary"].to_numpy(dtype=int)
        probability = part[model].to_numpy(dtype=float)
        per_query.append({
            "auprc": float(average_precision_score(y, probability)) if len(np.unique(y)) == 2 else np.nan,
            "brier": float(brier_score_loss(y, probability)),
            "ece": ece_score(y, probability),
        })
    return {
        f"macro_query_{metric}": float(np.nanmean([row[metric] for row in per_query]))
        if any(math.isfinite(row[metric]) for row in per_query) else np.nan
        for metric in ("auprc", "brier", "ece")
    }


def _bootstrap_metric_values(y: np.ndarray, probability: np.ndarray, query: np.ndarray) -> dict[str, float]:
    pooled = float(average_precision_score(y, probability)) if len(np.unique(y)) == 2 else np.nan
    query_values = []
    for query_id in sorted(set(query)):
        selected = query == query_id
        query_y = y[selected]
        if len(np.unique(query_y)) == 2:
            query_values.append(float(average_precision_score(query_y, probability[selected])))
    return {
        "auprc": pooled,
        "macro_query_auprc": float(np.mean(query_values)) if query_values else np.nan,
        "brier": float(brier_score_loss(y, probability)) if len(y) else np.nan,
        "ece": ece_score(y, probability) if len(y) else np.nan,
    }


def group_bootstrap_intervals(
    predictions: pd.DataFrame,
    selected_representation: str,
    best_aggregate: str,
    best_temporal: str,
) -> pd.DataFrame:
    """Descriptive cluster-bootstrap intervals conditional on fixed OOF predictions."""
    rows: list[dict[str, Any]] = []
    comparisons = [
        (selected_representation, "B0_RAW_YOLO", "selected_minus_raw_yolo"),
        (best_temporal, best_aggregate, "best_temporal_minus_best_aggregate"),
    ]
    for scope_ordinal, (scope, scoped) in enumerate(predictions.groupby("evaluation_scope", sort=True)):
        scoped = scoped.reset_index(drop=True)
        group_names = sorted(scoped["source_session_group"].astype(str).unique())
        group_indices = [
            np.flatnonzero(scoped["source_session_group"].astype(str).to_numpy() == group)
            for group in group_names
        ]
        y_all = scoped["label_binary"].to_numpy(dtype=int)
        query_all = scoped["query_id"].astype(str).to_numpy()
        probabilities = {
            model: scoped[model].to_numpy(dtype=float)
            for model in PRIMARY_MODELS
        }
        observed = {
            model: _bootstrap_metric_values(y_all, probability, query_all)
            for model, probability in probabilities.items()
        }
        draws: dict[tuple[str, str], list[float]] = {
            (model, metric): []
            for model in PRIMARY_MODELS
            for metric in ("auprc", "macro_query_auprc", "brier", "ece")
        }
        paired_draws: dict[tuple[str, str], list[float]] = {
            (label, metric): []
            for _, _, label in comparisons
            for metric in ("auprc", "macro_query_auprc")
        }
        rng = np.random.default_rng(SEED + 30000 + scope_ordinal)
        for _ in range(BOOTSTRAP_REPETITIONS):
            chosen = rng.integers(0, len(group_indices), size=len(group_indices))
            sampled = np.concatenate([group_indices[index] for index in chosen])
            sampled_y = y_all[sampled]
            sampled_query = query_all[sampled]
            replicate = {
                model: _bootstrap_metric_values(sampled_y, probability[sampled], sampled_query)
                for model, probability in probabilities.items()
            }
            for model in PRIMARY_MODELS:
                for metric, value in replicate[model].items():
                    if math.isfinite(value):
                        draws[(model, metric)].append(value)
            for model, reference, label in comparisons:
                for metric in ("auprc", "macro_query_auprc"):
                    left = replicate[model][metric]
                    right = replicate[reference][metric]
                    if math.isfinite(left) and math.isfinite(right):
                        paired_draws[(label, metric)].append(left - right)
        for model in PRIMARY_MODELS:
            for metric in ("auprc", "macro_query_auprc", "brier", "ece"):
                values = np.asarray(draws[(model, metric)], dtype=float)
                rows.append({
                    "evaluation_scope": scope,
                    "estimate_type": "model_metric",
                    "model": model,
                    "reference_model": np.nan,
                    "comparison": np.nan,
                    "metric": metric,
                    "estimate": observed[model][metric],
                    "ci_lower_2_5": float(np.quantile(values, 0.025)) if len(values) else np.nan,
                    "ci_upper_97_5": float(np.quantile(values, 0.975)) if len(values) else np.nan,
                    "valid_replicates": int(len(values)),
                    "requested_replicates": BOOTSTRAP_REPETITIONS,
                    "resampling_unit": "source_dataset_plus_session_id",
                    "interpretation": "descriptive_percentile_interval_conditional_on_fixed_oof_predictions",
                })
        for model, reference, label in comparisons:
            for metric in ("auprc", "macro_query_auprc"):
                values = np.asarray(paired_draws[(label, metric)], dtype=float)
                rows.append({
                    "evaluation_scope": scope,
                    "estimate_type": "paired_model_delta",
                    "model": model,
                    "reference_model": reference,
                    "comparison": label,
                    "metric": metric,
                    "estimate": observed[model][metric] - observed[reference][metric],
                    "ci_lower_2_5": float(np.quantile(values, 0.025)) if len(values) else np.nan,
                    "ci_upper_97_5": float(np.quantile(values, 0.975)) if len(values) else np.nan,
                    "valid_replicates": int(len(values)),
                    "requested_replicates": BOOTSTRAP_REPETITIONS,
                    "resampling_unit": "source_dataset_plus_session_id",
                    "interpretation": "descriptive_paired_percentile_interval_conditional_on_fixed_oof_predictions",
                })
    return pd.DataFrame(rows)


def calibration_rows(scope: str, model: str, y: np.ndarray, probability: np.ndarray) -> list[dict[str, Any]]:
    edges = np.linspace(0, 1, 11)
    assignments = np.minimum(np.digitize(probability, edges[1:-1], right=False), 9)
    rows: list[dict[str, Any]] = []
    for index in range(10):
        selected = assignments == index
        rows.append({
            "evaluation_scope": scope,
            "model": model,
            "bin_index": index,
            "lower_bound": edges[index],
            "upper_bound": edges[index + 1],
            "count": int(selected.sum()),
            "mean_probability": float(np.mean(probability[selected])) if selected.any() else np.nan,
            "observed_positive_fraction": float(np.mean(y[selected])) if selected.any() else np.nan,
        })
    return rows


def fit_logistic(x: np.ndarray, y: np.ndarray, seed: int = SEED) -> BaseEstimator:
    if len(np.unique(y)) < 2:
        return DummyClassifier(strategy="prior").fit(np.zeros((len(y), 1)), y)
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(C=1.0, class_weight="balanced", max_iter=3000, random_state=seed)),
    ]).fit(x, y)


def predict_estimator(model: BaseEstimator, x: np.ndarray) -> np.ndarray:
    if isinstance(model, DummyClassifier):
        classes = list(model.classes_)
        probability = model.predict_proba(np.zeros((len(x), 1)))
        return probability[:, classes.index(1)] if 1 in classes else np.zeros(len(x), dtype=float)
    return model.predict_proba(x)[:, 1]


def fit_lightgbm(x: np.ndarray, y: np.ndarray, seed: int = SEED) -> BaseEstimator:
    if len(np.unique(y)) < 2:
        return DummyClassifier(strategy="prior").fit(np.zeros((len(y), 1)), y)
    model = lgb.LGBMClassifier(
        objective="binary", n_estimators=160, learning_rate=0.03, num_leaves=7,
        max_depth=3, min_child_samples=10, subsample=1.0, colsample_bytree=1.0,
        reg_alpha=0.1, reg_lambda=1.0, random_state=seed, n_jobs=1,
        deterministic=True, force_col_wise=True, verbosity=-1,
    )
    return model.fit(x, y)


def fit_platt(raw_probability: np.ndarray, y: np.ndarray) -> LogisticRegression | None:
    if len(y) < 4 or len(np.unique(y)) < 2:
        return None
    return LogisticRegression(C=1e6, solver="lbfgs", max_iter=2000, random_state=SEED).fit(
        stable_logit(raw_probability).reshape(-1, 1), y
    )


def final_calibration_support(binary: pd.DataFrame) -> dict[str, Any]:
    calibration = binary[binary["model_split_role"] == "model_calibration"]
    positives = int(calibration["label_binary"].sum())
    negatives = int(len(calibration) - positives)
    per_query = {}
    for query_id in ("Q1", "Q2"):
        part = calibration[calibration["query_id"] == query_id]
        query_positives = int(part["label_binary"].sum())
        per_query[query_id] = {
            "rows": int(len(part)),
            "positives": query_positives,
            "negatives": int(len(part) - query_positives),
        }
    status = (
        "UNSUPPORTED_ONE_POSITIVE_NOT_DEPLOYABLE"
        if positives == 1
        else "UNSUPPORTED_ZERO_POSITIVES_NOT_DEPLOYABLE"
        if positives == 0
        else "EXPLORATORY_NOT_DEPLOYMENT_VALIDATED"
    )
    return {
        "rows": int(len(calibration)),
        "positives": positives,
        "negatives": negatives,
        "per_query": per_query,
        "status": status,
        "deployable": False,
        "interpretation": "A fitted Platt map is retained only to reproduce the exploratory audit; it is not a deployable calibrator.",
    }


def apply_platt(calibrator: LogisticRegression | None, raw_probability: np.ndarray) -> np.ndarray:
    if calibrator is None:
        return np.asarray(raw_probability, dtype=float)
    return calibrator.predict_proba(stable_logit(raw_probability).reshape(-1, 1))[:, 1]


def group_calibration_split(indices: np.ndarray, groups: np.ndarray, y: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    unique_groups = np.unique(groups[indices])
    if len(unique_groups) < 5:
        return indices, np.asarray([], dtype=int)
    for offset in range(64):
        rng = np.random.default_rng(seed + offset)
        shuffled = unique_groups.copy()
        rng.shuffle(shuffled)
        count = max(1, int(round(0.2 * len(shuffled))))
        calibration_groups = set(shuffled[:count])
        calibration = indices[np.array([group in calibration_groups for group in groups[indices]])]
        fit = indices[np.array([group not in calibration_groups for group in groups[indices]])]
        if len(fit) and len(calibration) and len(np.unique(y[fit])) == 2 and len(np.unique(y[calibration])) == 2:
            return fit, calibration
    return indices, np.asarray([], dtype=int)


def category_matrix(train_values: np.ndarray, test_values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    categories = sorted(set(str(value) for value in train_values))
    x_train = np.asarray([[float(str(value) == category) for category in categories] for value in train_values])
    x_test = np.asarray([[float(str(value) == category) for category in categories] for value in test_values])
    return x_train, x_test


def aggregate_loso_predictions(
    x: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    model: str,
    categorical: np.ndarray | None = None,
    shuffled_repeat: int | None = None,
) -> np.ndarray:
    result = np.full(len(y), np.nan, dtype=float)
    unique_groups = sorted(set(groups))
    for fold, held_group in enumerate(unique_groups):
        test = np.flatnonzero(groups == held_group)
        train = np.flatnonzero(groups != held_group)
        train_y = y[train].copy()
        if shuffled_repeat is not None:
            np.random.default_rng(SEED + 10000 * shuffled_repeat + fold).shuffle(train_y)
        if categorical is not None:
            x_train, x_test = category_matrix(categorical[train], categorical[test])
            estimator = fit_logistic(x_train, train_y, SEED + fold)
            result[test] = predict_estimator(estimator, x_test)
        elif model == "M0_LOGISTIC":
            estimator = fit_logistic(x[train], train_y, SEED + fold)
            result[test] = predict_estimator(estimator, x[test])
        elif model == "M2_LIGHTGBM":
            estimator = fit_lightgbm(x[train], train_y, SEED + fold)
            result[test] = predict_estimator(estimator, x[test])
        elif model == "M1_CALIBRATED_LOGISTIC":
            fit, calibration = group_calibration_split(train, groups, y, SEED + fold)
            estimator = fit_logistic(x[fit], y[fit], SEED + fold)
            calibrator = None
            if len(calibration):
                calibrator = fit_platt(predict_estimator(estimator, x[calibration]), y[calibration])
            result[test] = apply_platt(calibrator, predict_estimator(estimator, x[test]))
        else:
            raise ValueError(model)
    if not np.isfinite(result).all():
        raise RuntimeError(f"LOSO predictions incomplete for {model}")
    return result


class CausalConv1d(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int):
        super().__init__()
        self.crop = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, padding=self.crop, dilation=dilation)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        value = self.conv(value)
        return value[:, :, :-self.crop] if self.crop else value


class TemporalNet(nn.Module):
    def __init__(self, kind: str, input_size: int, hidden_size: int = 32):
        super().__init__()
        self.kind = kind
        if kind == "GRU_TEMPORAL":
            self.encoder = nn.GRU(input_size, hidden_size, batch_first=True)
        elif kind == "TCN_TEMPORAL":
            self.encoder = nn.Sequential(
                CausalConv1d(input_size, hidden_size, 3, 1), nn.ReLU(),
                CausalConv1d(hidden_size, hidden_size, 3, 2), nn.ReLU(),
            )
        else:
            raise ValueError(kind)
        self.output = nn.Linear(hidden_size, 1)

    def forward(self, sequence: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        if self.kind == "GRU_TEMPORAL":
            packed = nn.utils.rnn.pack_padded_sequence(
                sequence, lengths.cpu(), batch_first=True, enforce_sorted=False
            )
            _, hidden = self.encoder(packed)
            representation = hidden[-1]
        else:
            encoded = self.encoder(sequence.transpose(1, 2)).transpose(1, 2)
            row = torch.arange(len(sequence), device=sequence.device)
            representation = encoded[row, torch.clamp(lengths - 1, min=0)]
        return self.output(representation).squeeze(1)


@dataclass
class TemporalArrays:
    raw: np.ndarray
    mask: np.ndarray
    query: np.ndarray
    witness_class: np.ndarray


def temporal_transform(arrays: TemporalArrays, fit_indices: np.ndarray, apply_indices: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    raw = arrays.raw
    mask = arrays.mask.astype(bool)
    training_values = raw[fit_indices][mask[fit_indices]]
    mean = training_values.mean(axis=0)
    scale = training_values.std(axis=0)
    scale[scale < 1e-6] = 1.0
    normalized = (raw[apply_indices] - mean) / scale
    normalized[~mask[apply_indices]] = 0.0
    query_one_hot = np.eye(2, dtype=np.float32)[np.clip(arrays.query[apply_indices] - 1, 0, 1)]
    class_code = np.clip(arrays.witness_class[apply_indices] + 1, 0, 8)
    class_one_hot = np.eye(9, dtype=np.float32)[class_code]
    static = np.concatenate([query_one_hot, class_one_hot], axis=1)
    static = np.repeat(static[:, None, :], raw.shape[1], axis=1)
    static[~mask[apply_indices]] = 0.0
    transformed = np.concatenate([normalized.astype(np.float32), static], axis=2)
    lengths = np.maximum(mask[apply_indices].sum(axis=1), 1).astype(np.int64)
    return transformed, lengths, {"mean": mean.tolist(), "scale": scale.tolist()}


def fit_temporal(
    kind: str,
    arrays: TemporalArrays,
    train: np.ndarray,
    y: np.ndarray,
    seed: int,
) -> tuple[TemporalNet, dict[str, Any]]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    x, lengths, scaler = temporal_transform(arrays, train, train)
    model = TemporalNet(kind, x.shape[2], hidden_size=32)
    tensor_x = torch.from_numpy(x)
    tensor_lengths = torch.from_numpy(lengths)
    tensor_y = torch.from_numpy(y[train].astype(np.float32))
    positives = max(1, int(tensor_y.sum().item()))
    negatives = max(1, len(train) - positives)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(float(negatives / positives)))
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    model.train()
    for _ in range(32):
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(model(tensor_x, tensor_lengths), tensor_y)
        loss.backward()
        optimizer.step()
    return model, scaler


def predict_temporal(
    model: TemporalNet,
    scaler: dict[str, Any],
    arrays: TemporalArrays,
    indices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    raw = arrays.raw
    mask = arrays.mask.astype(bool)
    mean = np.asarray(scaler["mean"])
    scale = np.asarray(scaler["scale"])
    normalized = (raw[indices] - mean) / scale
    normalized[~mask[indices]] = 0.0
    query_one_hot = np.eye(2, dtype=np.float32)[np.clip(arrays.query[indices] - 1, 0, 1)]
    class_code = np.clip(arrays.witness_class[indices] + 1, 0, 8)
    static = np.concatenate([query_one_hot, np.eye(9, dtype=np.float32)[class_code]], axis=1)
    static = np.repeat(static[:, None, :], raw.shape[1], axis=1)
    static[~mask[indices]] = 0.0
    x = np.concatenate([normalized.astype(np.float32), static], axis=2)
    lengths = np.maximum(mask[indices].sum(axis=1), 1).astype(np.int64)
    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(x), torch.from_numpy(lengths)).numpy()
    return sigmoid(logits), logits


def temporal_loso_predictions(kind: str, arrays: TemporalArrays, y: np.ndarray, groups: np.ndarray) -> np.ndarray:
    result = np.full(len(y), np.nan, dtype=float)
    for fold, held_group in enumerate(sorted(set(groups))):
        test = np.flatnonzero(groups == held_group)
        train = np.flatnonzero(groups != held_group)
        fit, calibration = group_calibration_split(train, groups, y, SEED + 1000 + fold)
        model, scaler = fit_temporal(kind, arrays, fit, y, SEED + 1000 + fold)
        calibrator = None
        if len(calibration):
            raw_cal, _ = predict_temporal(model, scaler, arrays, calibration)
            calibrator = fit_platt(raw_cal, y[calibration])
        raw_test, _ = predict_temporal(model, scaler, arrays, test)
        result[test] = apply_platt(calibrator, raw_test)
        if (fold + 1) % 10 == 0 or fold + 1 == len(set(groups)):
            print(json.dumps({"temporal_model": kind, "completed_loso_folds": fold + 1, "total_folds": len(set(groups))}), flush=True)
    if not np.isfinite(result).all():
        raise RuntimeError(f"Temporal LOSO predictions incomplete for {kind}")
    return result


def validate_and_load() -> tuple[pd.DataFrame, list[str], TemporalArrays, dict[str, Any]]:
    required = [
        DATASET, FEATURE_SCHEMA, DATASET_AUDIT, TEMPORAL, TEMPORAL_SCHEMA,
        PROTOCOL, PROTOCOL_PROVENANCE, ORACLE_AUDIT, EXECUTION_DIFFERENCE,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Modeling prerequisite artifact missing: {missing}")
    dataset_audit = load_json(DATASET_AUDIT)
    oracle_audit = load_json(ORACLE_AUDIT)
    protocol = load_json(PROTOCOL)
    protocol_provenance = load_json(PROTOCOL_PROVENANCE)
    execution_difference = load_json(EXECUTION_DIFFERENCE)
    if dataset_audit.get("status") != "PASS" or oracle_audit.get("status") != "PASS":
        raise RuntimeError("Dataset or independent oracle completion audit is not PASS")
    if oracle_audit.get("frozen_verify_result", {}).get("status") != "VERIFIED_COMPLETE_COMMIT":
        raise RuntimeError("Full frozen oracle recomputation did not reach VERIFIED_COMPLETE_COMMIT")
    if execution_difference.get("status") != "PASS_WITH_RECORDED_FROZEN_VERIFIER_DEFECT":
        raise RuntimeError("Frozen verifier execution difference is not explicitly preserved")
    if oracle_audit.get("execution_difference_audit_sha256") != sha256_file(EXECUTION_DIFFERENCE):
        raise RuntimeError("Oracle round-trip receipt is detached from the verifier-exception audit")
    if protocol.get("status") != "FROZEN" or not protocol.get("frozen_before_oracle_parse"):
        raise RuntimeError("Modeling protocol is not frozen")
    if protocol.get("heldout_opened") is not False:
        raise RuntimeError("Modeling protocol held-out flag changed")
    if protocol_provenance.get("status") != "EXPLORATORY_FIXED_DURING_ORACLE_ACQUISITION":
        raise RuntimeError("Modeling protocol provenance is not honestly classified as exploratory")
    frame = pd.read_parquet(DATASET)
    if len(frame) != 192 or frame["semantic_sample_id"].nunique() != 192:
        raise RuntimeError("Modeling dataset semantic universe is not exact")
    feature_schema = load_json(FEATURE_SCHEMA)
    features = list(feature_schema["aggregate_model_features"])
    if not features or len(features) != len(set(features)):
        raise RuntimeError("Aggregate feature schema is empty or duplicated")
    forbidden = sorted(set(features) & FORBIDDEN_FEATURES)
    if forbidden:
        raise RuntimeError(f"Forbidden identity/label feature entered aggregate schema: {forbidden}")
    if any(column not in frame or not pd.api.types.is_numeric_dtype(frame[column]) for column in features):
        raise RuntimeError("Aggregate feature schema does not resolve to numeric dataset columns")
    if frame[features].isna().any().any() or not np.isfinite(frame[features].to_numpy(dtype=float)).all():
        raise RuntimeError("Aggregate runtime features are non-finite")
    pruning = feature_schema.get("aggregate_redundancy_pruning", {})
    centered = frame[features].to_numpy(dtype=float)
    centered -= centered.mean(axis=0, keepdims=True)
    scale = np.linalg.norm(centered, axis=0)
    if (scale <= 1e-12).any():
        raise RuntimeError("Aggregate feature basis retained a constant column")
    standardized = centered / scale
    design_rank = int(np.linalg.matrix_rank(np.column_stack([np.ones(len(frame)), standardized])))
    if design_rank != len(features) + 1:
        raise RuntimeError("Aggregate feature basis is not full rank with an intercept")
    if (
        pruning.get("labels_consulted") is not False
        or pruning.get("retained_feature_count") != len(features)
        or pruning.get("design_rank_with_intercept") != design_rank
    ):
        raise RuntimeError("Aggregate label-free redundancy audit does not match the effective basis")
    with np.load(TEMPORAL, allow_pickle=False) as archive:
        temporal_ids = archive["semantic_sample_id"].astype(str)
        if len(temporal_ids) != 192 or len(set(temporal_ids)) != 192:
            raise RuntimeError("Temporal semantic identity universe is not exact")
        position = {value: index for index, value in enumerate(temporal_ids)}
        try:
            order = np.asarray([position[value] for value in frame["semantic_sample_id"].astype(str)], dtype=int)
        except KeyError as error:
            raise RuntimeError("Dataset and temporal semantic identities differ") from error
        arrays = TemporalArrays(
            raw=archive["sequences"][order].astype(np.float32),
            mask=archive["valid_mask"][order].astype(np.uint8),
            query=archive["query_code"][order].astype(np.int64),
            witness_class=archive["witness_class_id"][order].astype(np.int64),
        )
    if arrays.raw.shape != (192, 64, 18) or arrays.mask.shape != (192, 64):
        raise RuntimeError("Temporal tensor shape changed")
    query_expected = frame["query_id"].map({"Q1": 1, "Q2": 2}).to_numpy(dtype=int)
    if not np.array_equal(arrays.query, query_expected):
        raise RuntimeError("Temporal query conditioning is detached from dataset rows")
    return frame, features, arrays, protocol


def choose_model(metrics: pd.DataFrame, candidates: list[str], scope: str = "development_loso") -> str:
    selected = metrics[(metrics["evaluation_scope"] == scope) & metrics["model"].isin(candidates)].copy()
    selected = selected[selected["auprc"].notna()]
    if selected.empty:
        raise RuntimeError(f"No identifiable AUPRC for model candidates {candidates}")
    selected = selected[selected["auprc"] >= float(selected["auprc"].max()) - 1e-12]
    selected = selected.sort_values(["brier", "ece", "model"], ascending=[True, True, True])
    return str(selected.iloc[0]["model"])


def metric_row(metrics: pd.DataFrame, model: str, scope: str) -> dict[str, Any]:
    selected = metrics[(metrics["model"] == model) & (metrics["evaluation_scope"] == scope)]
    if len(selected) != 1:
        raise RuntimeError(f"Metric row not unique: {model}/{scope}")
    return selected.iloc[0].to_dict()


def fit_final_aggregate_models(
    frame: pd.DataFrame,
    features: list[str],
    binary_indices: np.ndarray,
    audit_local: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict[str, Path], list[dict[str, Any]]]:
    binary = frame.iloc[binary_indices].reset_index(drop=True)
    x = binary[features].to_numpy(dtype=float)
    y = binary["label_binary"].to_numpy(dtype=int)
    roles = binary["model_split_role"].astype(str).to_numpy()
    train = np.flatnonzero(roles == "model_train")
    calibration = np.flatnonzero(roles == "model_calibration")
    development = np.flatnonzero(np.isin(roles, sorted(DEVELOPMENT_ROLES)))
    predictions: dict[str, np.ndarray] = {}
    paths: dict[str, Path] = {}
    importances: list[dict[str, Any]] = []
    calibration_support = final_calibration_support(binary)
    for ordinal, model_name in enumerate(AGGREGATE_MODELS):
        path = MODELS / f"{model_name}.joblib"
        if model_name == "M0_LOGISTIC":
            estimator = fit_logistic(x[development], y[development], SEED + ordinal)
            bundle = {"model_id": model_name, "features": features, "estimator": estimator, "calibrator": None,
                      "final_calibration_support": {"status": "NOT_APPLICABLE_UNCALIBRATED_MODEL", "deployable": False}}
            predictions[model_name] = predict_estimator(estimator, x[audit_local])
        elif model_name == "M2_LIGHTGBM":
            estimator = fit_lightgbm(x[development], y[development], SEED + ordinal)
            bundle = {"model_id": model_name, "features": features, "estimator": estimator, "calibrator": None,
                      "final_calibration_support": {"status": "NOT_APPLICABLE_UNCALIBRATED_MODEL", "deployable": False}}
            predictions[model_name] = predict_estimator(estimator, x[audit_local])
        else:
            estimator = fit_logistic(x[train], y[train], SEED + ordinal)
            calibrator = fit_platt(predict_estimator(estimator, x[calibration]), y[calibration])
            bundle = {"model_id": model_name, "features": features, "estimator": estimator, "calibrator": calibrator,
                      "final_calibration_support": calibration_support}
            predictions[model_name] = apply_platt(calibrator, predict_estimator(estimator, x[audit_local]))
        atomic_joblib(path, bundle)
        paths[model_name] = path
        if isinstance(estimator, Pipeline):
            coefficient = np.abs(estimator.named_steps["model"].coef_[0])
            for feature, value in zip(features, coefficient):
                importances.append({"model": model_name, "feature": feature, "importance_type": "absolute_standardized_coefficient", "importance": float(value)})
        elif isinstance(estimator, lgb.LGBMClassifier):
            values = estimator.booster_.feature_importance(importance_type="gain")
            total = max(float(values.sum()), 1e-12)
            for feature, value in zip(features, values):
                importances.append({"model": model_name, "feature": feature, "importance_type": "normalized_gain", "importance": float(value / total)})
    return predictions, paths, importances


def fit_final_temporal_models(
    frame: pd.DataFrame,
    arrays_all: TemporalArrays,
    binary_indices: np.ndarray,
    audit_local: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict[str, Path]]:
    binary = frame.iloc[binary_indices].reset_index(drop=True)
    arrays = TemporalArrays(
        raw=arrays_all.raw[binary_indices], mask=arrays_all.mask[binary_indices],
        query=arrays_all.query[binary_indices], witness_class=arrays_all.witness_class[binary_indices],
    )
    y = binary["label_binary"].to_numpy(dtype=int)
    roles = binary["model_split_role"].astype(str).to_numpy()
    train = np.flatnonzero(roles == "model_train")
    calibration = np.flatnonzero(roles == "model_calibration")
    predictions: dict[str, np.ndarray] = {}
    paths: dict[str, Path] = {}
    temporal_schema = load_json(TEMPORAL_SCHEMA)
    calibration_support = final_calibration_support(binary)
    for ordinal, model_name in enumerate(TEMPORAL_MODELS):
        estimator, scaler = fit_temporal(model_name, arrays, train, y, SEED + 5000 + ordinal)
        raw_calibration, _ = predict_temporal(estimator, scaler, arrays, calibration)
        calibrator = fit_platt(raw_calibration, y[calibration])
        raw_audit, _ = predict_temporal(estimator, scaler, arrays, audit_local)
        predictions[model_name] = apply_platt(calibrator, raw_audit)
        path = MODELS / f"{model_name}.pt"
        calibration_payload = None if calibrator is None else {
            "coefficient": calibrator.coef_.tolist(),
            "intercept": calibrator.intercept_.tolist(),
            "classes": calibrator.classes_.tolist(),
        }
        atomic_torch(path, {
            "model_id": model_name,
            "state_dict": estimator.state_dict(),
            "input_size": 29,
            "hidden_size": 32,
            "scaler": scaler,
            "calibration": calibration_payload,
            "final_calibration_support": calibration_support,
            "sequence_feature_order": temporal_schema["feature_order"],
            "query_conditioning": "Q1/Q2 one-hot",
            "witness_class_conditioning": "class -1..7 encoded as 9-way one-hot",
            "fit_roles": ["model_train"],
            "calibration_roles": ["model_calibration"],
            "audit_rows_used_for_fit": 0,
        })
        paths[model_name] = path
    return predictions, paths


def auxiliary_evaluations(
    binary: pd.DataFrame,
    x: np.ndarray,
    arrays: TemporalArrays,
    y: np.ndarray,
    ids: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    development = np.flatnonzero(binary["model_split_role"].isin(DEVELOPMENT_ROLES).to_numpy())
    for held_query in ("Q1", "Q2"):
        test = development[binary.iloc[development]["query_id"].to_numpy() == held_query]
        train = development[binary.iloc[development]["query_id"].to_numpy() != held_query]
        if not len(train) or not len(test):
            continue
        base_predictions = {
            "B0_RAW_YOLO": binary.iloc[test]["raw_yolo_score"].to_numpy(dtype=float),
            "B1_FIFO": binary.iloc[test]["fifo_creation_score"].to_numpy(dtype=float),
        }
        for model_name in AGGREGATE_MODELS:
            if model_name == "M0_LOGISTIC":
                estimator = fit_logistic(x[train], y[train], SEED)
                probability = predict_estimator(estimator, x[test])
            elif model_name == "M2_LIGHTGBM":
                estimator = fit_lightgbm(x[train], y[train], SEED)
                probability = predict_estimator(estimator, x[test])
            else:
                fit, calibration = group_calibration_split(
                    train, binary["source_session_group"].to_numpy(), y, SEED
                )
                estimator = fit_logistic(x[fit], y[fit], SEED)
                calibrator = fit_platt(predict_estimator(estimator, x[calibration]), y[calibration]) if len(calibration) else None
                probability = apply_platt(calibrator, predict_estimator(estimator, x[test]))
            base_predictions[model_name] = probability
        for ordinal, model_name in enumerate(TEMPORAL_MODELS):
            fit, calibration = group_calibration_split(
                train, binary["source_session_group"].to_numpy(), y, SEED + ordinal
            )
            estimator, scaler = fit_temporal(model_name, arrays, fit, y, SEED + 7000 + ordinal)
            raw_cal, _ = predict_temporal(estimator, scaler, arrays, calibration) if len(calibration) else (np.asarray([]), np.asarray([]))
            calibrator = fit_platt(raw_cal, y[calibration]) if len(calibration) else None
            raw_test, _ = predict_temporal(estimator, scaler, arrays, test)
            base_predictions[model_name] = apply_platt(calibrator, raw_test)
        for model_name, probability in base_predictions.items():
            metric = score_metrics(y[test], probability, ids[test])
            rows.append({
                "evaluation": "leave_one_query_out", "status": "COMPLETE",
                "held_out_value": held_query, "model": model_name, **metric,
            })
    datasets = sorted(binary.iloc[development]["source_dataset"].astype(str).unique())
    for model_name in PRIMARY_MODELS:
        if len(datasets) == 1:
            rows.append({
                "evaluation": "leave_one_dataset_out", "status": "NOT_IDENTIFIABLE",
                "held_out_value": datasets[0], "model": model_name,
                "n": int(len(development)), "positives": int(y[development].sum()),
                "negatives": int(len(development) - y[development].sum()),
                "auprc": np.nan, "brier": np.nan, "ece": np.nan,
                "reason": "Only one source_dataset is present; training on zero datasets would not be an evaluation.",
            })
    return pd.DataFrame(rows)


def extract_support_decision() -> str:
    gate = STAGE / "STAGE_A_SUPPORT_GATE_REPORT.json"
    if gate.is_file():
        return str(load_json(gate).get("decision", "UNKNOWN"))
    audit = load_json(ORACLE_AUDIT)
    return str(audit.get("support_decision", "UNKNOWN"))


def readiness_decision(
    metrics: pd.DataFrame,
    control_summary: pd.DataFrame,
    per_query: pd.DataFrame,
    best_aggregate: str,
    best_temporal: str,
    development_y: np.ndarray,
    calibration_support: dict[str, Any],
) -> dict[str, Any]:
    aggregate_dev = metric_row(metrics, best_aggregate, "development_loso")
    temporal_dev = metric_row(metrics, best_temporal, "development_loso")
    overall = choose_model(metrics, [best_aggregate, best_temporal])
    overall_dev = metric_row(metrics, overall, "development_loso")
    overall_audit = metric_row(metrics, overall, "fixed_pool_audit")
    raw_dev = metric_row(metrics, "B0_RAW_YOLO", "development_loso")
    raw_audit = metric_row(metrics, "B0_RAW_YOLO", "fixed_pool_audit")
    shuffled = control_summary[control_summary["control"] == "SHUFFLED_LABEL_M0"].iloc[0]
    identity = control_summary[control_summary["control"].isin(IDENTITY_CONTROLS)]
    nuisance = control_summary[control_summary["control"].isin(IDENTITY_CONTROLS + POSTHOC_NUISANCE_CONTROLS)]
    strongest_identity = float(identity["auprc_mean"].max())
    strongest_nuisance = float(nuisance["auprc_mean"].max())
    control_threshold = max(float(raw_dev["auprc"]), float(shuffled["auprc_p95"]), strongest_nuisance)
    support = extract_support_decision()
    per_query_checks: dict[str, dict[str, Any]] = {}
    for query_id in ("Q1", "Q2"):
        selected_development = per_query[
            (per_query["evaluation_scope"] == "development_loso")
            & (per_query["model"] == overall)
            & (per_query["query_id"] == query_id)
        ].iloc[0]
        selected_audit = per_query[
            (per_query["evaluation_scope"] == "fixed_pool_audit")
            & (per_query["model"] == overall)
            & (per_query["query_id"] == query_id)
        ].iloc[0]
        raw_query_audit = per_query[
            (per_query["evaluation_scope"] == "fixed_pool_audit")
            & (per_query["model"] == "B0_RAW_YOLO")
            & (per_query["query_id"] == query_id)
        ].iloc[0]
        per_query_checks[query_id] = {
            "development_positives": int(selected_development["positives"]),
            "development_negatives": int(selected_development["negatives"]),
            "minimum_development_class_count_each": (
                int(selected_development["positives"]) >= 20
                and int(selected_development["negatives"]) >= 20
            ),
            "fixed_audit_auprc_identifiable": bool(pd.notna(selected_audit["auprc"])),
            "fixed_audit_not_worse_than_raw_yolo": bool(
                pd.notna(selected_audit["auprc"])
                and pd.notna(raw_query_audit["auprc"])
                and float(selected_audit["auprc"]) >= float(raw_query_audit["auprc"])
            ),
            "fixed_audit_ece_at_most_0_20": bool(float(selected_audit["ece"]) <= 0.20),
            "fixed_audit_auprc": finite_or_none(selected_audit["auprc"]),
            "raw_yolo_fixed_audit_auprc": finite_or_none(raw_query_audit["auprc"]),
            "fixed_audit_ece": finite_or_none(selected_audit["ece"]),
        }
    all_per_query_gates = all(
        row[gate]
        for row in per_query_checks.values()
        for gate in (
            "minimum_development_class_count_each",
            "fixed_audit_auprc_identifiable",
            "fixed_audit_not_worse_than_raw_yolo",
            "fixed_audit_ece_at_most_0_20",
        )
    )
    checks = {
        "oracle_support_pass": support.startswith("PASS") or support.startswith("PROCEED"),
        "minimum_development_class_count_each": int(development_y.sum()) >= 20 and int((1 - development_y).sum()) >= 20,
        "development_margin_over_raw_shuffled_p95_and_expanded_nuisance_controls": float(overall_dev["auprc"]) >= control_threshold + 0.03,
        "fixed_audit_auprc_identifiable": pd.notna(overall_audit["auprc"]),
        "fixed_audit_not_worse_than_raw_yolo": pd.notna(overall_audit["auprc"]) and float(overall_audit["auprc"]) >= float(raw_audit["auprc"]),
        "fixed_audit_ece_at_most_0_20": float(overall_audit["ece"]) <= 0.20,
        "all_per_query_support_and_audit_gates": all_per_query_gates,
        "final_calibrator_deployable": bool(calibration_support["deployable"]),
    }
    ready = all(checks.values())
    explicit_query_ablation_name = AGGREGATE_QUERY_ABLATIONS[best_aggregate]
    explicit_query_ablation = metric_row(metrics, explicit_query_ablation_name, "development_loso")
    query_delta = float(aggregate_dev["auprc"] - explicit_query_ablation["auprc"])
    temporal_delta = float(temporal_dev["auprc"] - aggregate_dev["auprc"])
    result = {
        "decision_id": "MF_PSVR_STAGE_A_EXPLORATORY_MODEL_READINESS_V2",
        "created_at_utc": utc_now(),
        "analysis_status": "EXPLORATORY_NOT_PREREGISTERED_OR_CRYPTOGRAPHICALLY_BLINDED",
        "decision": "READY_FOR_BOUNDED_PHYSICAL_PILOT_DESIGN" if ready else "NOT_READY_FOR_PHYSICAL_PILOT",
        "ready": ready,
        "checks": checks,
        "oracle_support_decision": support,
        "selected_representation": overall,
        "best_aggregate_model": best_aggregate,
        "best_temporal_model": best_temporal,
        "development_auprc": finite_or_none(overall_dev["auprc"]),
        "fixed_audit_auprc": finite_or_none(overall_audit["auprc"]),
        "control_threshold_auprc": finite_or_none(control_threshold),
        "strongest_identity_control_auprc": finite_or_none(strongest_identity),
        "strongest_expanded_nuisance_control_auprc": finite_or_none(strongest_nuisance),
        "per_query_checks": per_query_checks,
        "final_calibration_support": calibration_support,
        "query_conditioning_signal": "DESCRIPTIVE_POSITIVE_EXPLICIT_QUERY_ABLATION" if query_delta >= 0.02 else "NO_CLEAR_EXPLICIT_QUERY_GAIN",
        "query_conditioning_auprc_delta": query_delta,
        "query_conditioning_reference_model": best_aggregate,
        "query_conditioning_ablation_model": explicit_query_ablation_name,
        "query_signal_caveat": "The ablation removes explicit query-code/interaction columns, but raw scores and witness construction remain query-specific.",
        "query_signal_rule_status": "POST_HOC_DESCRIPTIVE_0_02_RULE_NOT_IN_MODELING_PROTOCOL",
        "temporal_refinement_signal": "DESCRIPTIVE_POSITIVE" if temporal_delta >= 0.02 else "NO_CLEAR_GAIN",
        "temporal_minus_aggregate_auprc": temporal_delta,
        "temporal_signal_rule_status": "POST_HOC_DESCRIPTIVE_0_02_RULE_NOT_IN_MODELING_PROTOCOL",
        "strongest_supported_conclusion": "The selected representation passes every exploratory screen, but deployment still requires independent prospective evidence." if ready else "At least one exploratory evidence screen failed; Stage A does not justify physical-method execution.",
        "main_competing_explanation": "Enriched stratum sampling and a single dataset family can inflate apparent discrimination without cross-dataset transport.",
        "key_uncertainty": "Leave-one-dataset-out is unidentifiable until another source dataset is labeled.",
        "next_action": "Preregister a bounded physical-pilot design without running V0/V1." if ready else "Acquire a second source dataset under the same frozen label semantics before physical-pilot execution.",
        "rejection_trigger": "Reverse or revise this exploratory assessment if independent audit finds group leakage, audit-role fitting, unstable group-bootstrap deltas, or a below-control per-query audit result.",
        "heldout_opened": False,
    }
    result["decision_hash"] = canonical_hash(result)
    return result


def build_metric_tables(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metric_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    per_source_rows: list[dict[str, Any]] = []
    per_query_rows: list[dict[str, Any]] = []
    for scope, scoped in predictions.groupby("evaluation_scope", sort=True):
        y = scoped["label_binary"].to_numpy(dtype=int)
        ids = scoped["semantic_sample_id"].astype(str).to_numpy()
        for model in ALL_PREDICTION_MODELS:
            probability = scoped[model].to_numpy(dtype=float)
            metric_rows.append({
                "evaluation_scope": scope, "model": model,
                **score_metrics(y, probability, ids),
                **macro_query_metrics(scoped, model),
                **physical_call_budget_metrics(scoped, model),
            })
            curve_rows.extend(calibration_rows(scope, model, y, probability))
            for (source_dataset, session_id), part in scoped.groupby(["source_dataset", "session_id"], sort=True):
                metric = score_metrics(
                    part["label_binary"].to_numpy(dtype=int), part[model].to_numpy(dtype=float),
                    part["semantic_sample_id"].astype(str).to_numpy(),
                )
                per_source_rows.append({
                    "evaluation_scope": scope, "model": model,
                    "source_dataset": source_dataset, "session_id": session_id, **metric,
                })
            for query_id, part in scoped.groupby("query_id", sort=True):
                metric = score_metrics(
                    part["label_binary"].to_numpy(dtype=int), part[model].to_numpy(dtype=float),
                    part["semantic_sample_id"].astype(str).to_numpy(),
                )
                per_query_rows.append({
                    "evaluation_scope": scope, "model": model, "query_id": query_id, **metric,
                })
    return pd.DataFrame(metric_rows), pd.DataFrame(curve_rows), pd.DataFrame(per_source_rows), pd.DataFrame(per_query_rows)


def model_card(
    frame: pd.DataFrame,
    metrics: pd.DataFrame,
    readiness: dict[str, Any],
    best_aggregate: str,
    best_temporal: str,
) -> str:
    agg = metric_row(metrics, best_aggregate, "development_loso")
    temporal = metric_row(metrics, best_temporal, "development_loso")
    audit = metric_row(metrics, readiness["selected_representation"], "fixed_pool_audit")
    feature_schema = load_json(FEATURE_SCHEMA)
    calibration = readiness["final_calibration_support"]
    return f"""# MF-PSVR Stage-A model card

## Outcome

- Readiness decision: `{readiness['decision']}`.
- Selected representation: `{readiness['selected_representation']}`.
- Best aggregate model: `{best_aggregate}` (development LOSO AUPRC {agg['auprc']:.6f}).
- Best temporal model: `{best_temporal}` (development LOSO AUPRC {temporal['auprc']:.6f}).
- Selected fixed pool-audit AUPRC: {audit['auprc'] if pd.notna(audit['auprc']) else 'undefined'}.
- Analysis status: exploratory; not preregistered and not cryptographically blinded to oracle labels.

## Evaluation contract

Exact leave-one-`(source_dataset, session_id)`-out predictions over the preassigned `model_train` and `model_calibration` roles are the primary selection evidence. The `pool_audit` role ({int((frame['model_split_role'] == 'pool_audit').sum())} semantic rows before binary exclusions) was arithmetically excluded from selection and fitting and evaluated only after the winner was fixed. The full dataset was locally available throughout; no cryptographic blind or label-blind preregistration is claimed. Random row splits are absent.

Leave-one-dataset-out is not identifiable because Stage A contains one dataset family. Leave-one-query-out is reported as a transfer stress test. AUPRC is deliberately left undefined for one-class source slices.

## Model inputs

Aggregate models use only the numeric runtime-visible feature list bound by `STAGE_A_FEATURE_SCHEMA.json`: {feature_schema['aggregate_redundancy_pruning']['retained_feature_count']} columns retained from {feature_schema['aggregate_redundancy_pruning']['candidate_feature_count']} candidates by a label-free, intercept-aware full-rank pruning. Raw numeric `witness_class_id` is excluded. Temporal models use 64-step YOLO/ByteTrack features, query one-hot conditioning, and witness-class one-hot conditioning. Source/session/call/unit/anchor/event/oracle fields are excluded. No RGB backbone or YOLO retraining occurs.

## Interpretation limits

This is a stratum-enriched support sample, not a prevalence sample. Unit-level oracle outcomes do not verify the witness track itself. Cross-session transport is measured, but cross-dataset transport is unresolved. Coefficients and gain scores are exploratory associations, not independently identified feature effects. The pool-audit set is small, so its uncertainty is substantial even when its AUPRC is identifiable.

The final calibration role has {calibration['positives']} positive and {calibration['negatives']} negative binary rows (Q1/Q2 positives: {calibration['per_query']['Q1']['positives']}/{calibration['per_query']['Q2']['positives']}). Its status is `{calibration['status']}`. Serialized Platt maps for M1/TCN/GRU reproduce the exploratory audit only and are not deployable calibrators.
"""


def train() -> dict[str, Any]:
    started = time.perf_counter()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    frame, features, arrays_all, protocol = validate_and_load()
    binary_indices = np.flatnonzero(frame["label_binary"].notna().to_numpy())
    if len(binary_indices) < 40:
        raise RuntimeError("Too few valid binary semantic labels for the preregistered model suite")
    binary = frame.iloc[binary_indices].reset_index(drop=True).copy()
    binary["source_session_group"] = binary["source_dataset"].astype(str) + "::" + binary["session_id"].astype(str)
    arrays = TemporalArrays(
        raw=arrays_all.raw[binary_indices], mask=arrays_all.mask[binary_indices],
        query=arrays_all.query[binary_indices], witness_class=arrays_all.witness_class[binary_indices],
    )
    x = binary[features].to_numpy(dtype=float)
    y = binary["label_binary"].to_numpy(dtype=int)
    ids = binary["semantic_sample_id"].astype(str).to_numpy()
    groups = binary["source_session_group"].astype(str).to_numpy()
    development = np.flatnonzero(binary["model_split_role"].isin(DEVELOPMENT_ROLES).to_numpy())
    audit_local = np.flatnonzero((binary["model_split_role"] == "pool_audit").to_numpy())
    if not len(development) or not len(audit_local):
        raise RuntimeError("Frozen development or pool-audit role has no binary rows")
    if set(groups[development]) & set(groups[audit_local]):
        raise RuntimeError("Source/session group crosses development and pool-audit roles")

    dev = binary.iloc[development].reset_index(drop=True)
    x_dev = x[development]
    y_dev = y[development]
    ids_dev = ids[development]
    groups_dev = groups[development]
    arrays_dev = TemporalArrays(
        raw=arrays.raw[development], mask=arrays.mask[development],
        query=arrays.query[development], witness_class=arrays.witness_class[development],
    )
    print(json.dumps({
        "phase": "development_loso", "binary_rows": len(dev),
        "groups": len(set(groups_dev)), "positives": int(y_dev.sum()),
        "negatives": int(len(y_dev) - y_dev.sum()),
        "protocol_sha256": sha256_file(PROTOCOL),
    }), flush=True)

    dev_probabilities: dict[str, np.ndarray] = {
        "B0_RAW_YOLO": dev["raw_yolo_score"].to_numpy(dtype=float),
        "B1_FIFO": dev["fifo_creation_score"].to_numpy(dtype=float),
    }
    for model_name in AGGREGATE_MODELS:
        dev_probabilities[model_name] = aggregate_loso_predictions(x_dev, y_dev, groups_dev, model_name)
        print(json.dumps({"completed_model": model_name}), flush=True)
    no_query_features = [
        index for index, name in enumerate(features)
        if not name.startswith("query_") and name not in {"query_is_q1", "query_is_q2"}
    ]
    if not no_query_features:
        raise RuntimeError("Explicit-query ablation removed every aggregate feature")
    for base_model, ablation_model in AGGREGATE_QUERY_ABLATIONS.items():
        dev_probabilities[ablation_model] = aggregate_loso_predictions(
            x_dev[:, no_query_features], y_dev, groups_dev, base_model
        )
    for control_name, column in CATEGORICAL_CONTROL_COLUMNS.items():
        dev_probabilities[control_name] = aggregate_loso_predictions(
            np.zeros((len(dev), 1)), y_dev, groups_dev, "M0_LOGISTIC",
            categorical=dev[column].astype(str).to_numpy(),
        )
    for model_name in TEMPORAL_MODELS:
        dev_probabilities[model_name] = temporal_loso_predictions(model_name, arrays_dev, y_dev, groups_dev)

    shuffled_auprc: list[float] = []
    for repeat in range(int(protocol["controls"]["shuffled_label_permutations"])):
        probability = aggregate_loso_predictions(
            x_dev, y_dev, groups_dev, "M0_LOGISTIC", shuffled_repeat=repeat
        )
        shuffled_auprc.append(float(average_precision_score(y_dev, probability)))
    development_predictions = dev[[
        "semantic_sample_id", "physical_call_id", "source_dataset", "session_id", "source_session_group",
        "query_id", "anchor_id", "model_split_role", "sampling_stratum", "label_binary",
    ]].copy()
    development_predictions.insert(0, "evaluation_scope", "development_loso")
    for model_name in ALL_PREDICTION_MODELS:
        development_predictions[model_name] = np.clip(dev_probabilities[model_name], 0, 1)

    # Fix both learned winners from development OOF predictions before any
    # pool-audit prediction or metric is computed.
    development_metrics, _, _, _ = build_metric_tables(development_predictions)
    best_aggregate = choose_model(development_metrics, AGGREGATE_MODELS)
    best_temporal = choose_model(development_metrics, TEMPORAL_MODELS)
    preaudit_selected_representation = choose_model(
        development_metrics, [best_aggregate, best_temporal]
    )
    print(json.dumps({
        "phase": "preaudit_selection_fixed",
        "best_aggregate": best_aggregate,
        "best_temporal": best_temporal,
        "selected_representation": preaudit_selected_representation,
        "pool_audit_rows_used_for_selection": 0,
    }), flush=True)

    final_aggregate_predictions, aggregate_paths, importance_rows = fit_final_aggregate_models(
        frame, features, binary_indices, audit_local
    )
    final_temporal_predictions, temporal_paths = fit_final_temporal_models(
        frame, arrays_all, binary_indices, audit_local
    )
    audit_frame = binary.iloc[audit_local].reset_index(drop=True)
    audit_predictions = audit_frame[[
        "semantic_sample_id", "physical_call_id", "source_dataset", "session_id", "source_session_group",
        "query_id", "anchor_id", "model_split_role", "sampling_stratum", "label_binary",
    ]].copy()
    audit_predictions.insert(0, "evaluation_scope", "fixed_pool_audit")
    audit_predictions["B0_RAW_YOLO"] = audit_frame["raw_yolo_score"].to_numpy(dtype=float)
    audit_predictions["B1_FIFO"] = audit_frame["fifo_creation_score"].to_numpy(dtype=float)
    for model_name, probability in final_aggregate_predictions.items():
        audit_predictions[model_name] = probability
    for model_name, probability in final_temporal_predictions.items():
        audit_predictions[model_name] = probability
    x_audit = x[audit_local]
    for ordinal, (base_model, ablation_model) in enumerate(AGGREGATE_QUERY_ABLATIONS.items()):
        if base_model == "M0_LOGISTIC":
            estimator = fit_logistic(x[development][:, no_query_features], y[development], SEED + 90 + ordinal)
            probability = predict_estimator(estimator, x_audit[:, no_query_features])
        elif base_model == "M2_LIGHTGBM":
            estimator = fit_lightgbm(x[development][:, no_query_features], y[development], SEED + 90 + ordinal)
            probability = predict_estimator(estimator, x_audit[:, no_query_features])
        else:
            train_role = np.flatnonzero(binary["model_split_role"].to_numpy() == "model_train")
            calibration_role = np.flatnonzero(binary["model_split_role"].to_numpy() == "model_calibration")
            estimator = fit_logistic(x[train_role][:, no_query_features], y[train_role], SEED + 90 + ordinal)
            calibrator = fit_platt(
                predict_estimator(estimator, x[calibration_role][:, no_query_features]), y[calibration_role]
            )
            probability = apply_platt(
                calibrator, predict_estimator(estimator, x_audit[:, no_query_features])
            )
        audit_predictions[ablation_model] = probability
    for control_name, column in CATEGORICAL_CONTROL_COLUMNS.items():
        x_train, x_test = category_matrix(
            binary.iloc[development][column].astype(str).to_numpy(),
            audit_frame[column].astype(str).to_numpy(),
        )
        estimator = fit_logistic(x_train, y[development], SEED)
        audit_predictions[control_name] = predict_estimator(estimator, x_test)

    predictions = pd.concat([development_predictions, audit_predictions], ignore_index=True)
    if predictions["semantic_sample_id"].duplicated().any():
        raise RuntimeError("A binary semantic sample entered multiple primary evaluation scopes")
    if predictions[ALL_PREDICTION_MODELS].isna().any().any():
        raise RuntimeError("Primary prediction table is incomplete")
    metrics, curves, per_source, per_query = build_metric_tables(predictions)
    control_rows = []
    for control_name in CATEGORICAL_CONTROL_COLUMNS:
        value = float(metric_row(metrics, control_name, "development_loso")["auprc"])
        control_rows.append({
            "control": control_name, "repetitions": 1, "auprc_mean": value,
            "auprc_std": 0.0, "auprc_p05": value, "auprc_p95": value,
            "evaluation_scope": "development_loso",
        })
    control_rows.append({
        "control": "SHUFFLED_LABEL_M0", "repetitions": len(shuffled_auprc),
        "auprc_mean": float(np.mean(shuffled_auprc)), "auprc_std": float(np.std(shuffled_auprc, ddof=1)),
        "auprc_p05": float(np.quantile(shuffled_auprc, 0.05)),
        "auprc_p95": float(np.quantile(shuffled_auprc, 0.95)),
        "evaluation_scope": "development_loso",
    })
    control_summary = pd.DataFrame(control_rows)
    if choose_model(metrics, AGGREGATE_MODELS) != best_aggregate or choose_model(metrics, TEMPORAL_MODELS) != best_temporal:
        raise RuntimeError("Post-audit metric assembly changed a development-only winner")
    calibration_support = final_calibration_support(binary)
    readiness = readiness_decision(
        metrics, control_summary, per_query, best_aggregate, best_temporal, y_dev, calibration_support
    )
    selected_representation = readiness["selected_representation"]
    if selected_representation != preaudit_selected_representation:
        raise RuntimeError("Readiness assembly changed the frozen pre-audit representation selection")

    bootstrap_intervals = group_bootstrap_intervals(
        predictions, selected_representation, best_aggregate, best_temporal
    )
    auxiliary = auxiliary_evaluations(binary, x, arrays, y, ids)
    importance = pd.DataFrame(importance_rows).sort_values(["model", "importance", "feature"], ascending=[True, False, True])
    combined_selected = predictions[selected_representation].to_numpy(dtype=float)
    hard_base = predictions[[
        "evaluation_scope", "semantic_sample_id", "physical_call_id", "source_dataset", "session_id", "query_id",
        "model_split_role", "sampling_stratum", "label_binary",
    ]].copy()
    hard_base["selected_model"] = selected_representation
    hard_base["predicted_probability"] = combined_selected
    hard_negatives = hard_base[hard_base["label_binary"] == 0].sort_values(
        ["predicted_probability", "semantic_sample_id"], ascending=[False, True]
    ).head(25)
    hard_positives = hard_base[hard_base["label_binary"] == 1].sort_values(
        ["predicted_probability", "semantic_sample_id"], ascending=[True, True]
    ).head(25)

    MODELS.mkdir(parents=True, exist_ok=True)
    atomic_parquet(PREDICTIONS, predictions)
    atomic_csv(METRICS, metrics)
    atomic_csv(AUXILIARY, auxiliary)
    atomic_csv(CONTROLS, control_summary)
    atomic_csv(PER_SOURCE, per_source)
    atomic_csv(PER_QUERY, per_query)
    atomic_csv(FEATURE_IMPORTANCE, importance)
    atomic_csv(CALIBRATION_CURVES, curves)
    atomic_csv(BOOTSTRAP_INTERVALS, bootstrap_intervals)
    atomic_csv(HARD_NEGATIVES, hard_negatives)
    atomic_csv(HARD_POSITIVES, hard_positives)
    atomic_json(READINESS, readiness)
    atomic_bytes(MODEL_CARD, model_card(frame, metrics, readiness, best_aggregate, best_temporal).encode("utf-8"))

    model_paths = {**aggregate_paths, **temporal_paths}
    model_hashes = {
        "manifest_id": "MF_PSVR_STAGE_A_MODEL_HASHES_V1",
        "created_at_utc": utc_now(),
        "models": {
            model_name: {"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)}
            for model_name, path in sorted(model_paths.items())
        },
        "bindings": {
            "dataset_sha256": sha256_file(DATASET),
            "dataset_completion_audit_sha256": sha256_file(DATASET_AUDIT),
            "feature_schema_sha256": sha256_file(FEATURE_SCHEMA),
            "temporal_sequences_sha256": sha256_file(TEMPORAL),
            "temporal_schema_sha256": sha256_file(TEMPORAL_SCHEMA),
            "modeling_protocol_sha256": sha256_file(PROTOCOL),
            "modeling_protocol_provenance_sha256": sha256_file(PROTOCOL_PROVENANCE),
            "oracle_roundtrip_verification_audit_sha256": sha256_file(ORACLE_AUDIT),
            "execution_difference_audit_sha256": sha256_file(EXECUTION_DIFFERENCE),
            "trainer_source_sha256": sha256_file(Path(__file__)),
        },
        "analysis_status": "EXPLORATORY_NOT_PREREGISTERED_OR_CRYPTOGRAPHICALLY_BLINDED",
        "pool_audit_exclusion": "arithmetically_excluded_from_fit_and_selection_then_evaluated",
        "heldout_opened": False,
    }
    model_hashes["manifest_hash"] = canonical_hash(model_hashes)
    atomic_json(MODEL_HASHES, model_hashes)
    for target, model_name, artifact_id in (
        (BEST_VALUE, best_aggregate, "MF_PSVR_BEST_STAGE_A_VALUE_MODEL_V1"),
        (BEST_TEMPORAL, best_temporal, "MF_PSVR_BEST_STAGE_A_TEMPORAL_REFINER_V1"),
    ):
        path = model_paths[model_name]
        pointer = {
            "artifact_id": artifact_id, "created_at_utc": utc_now(), "model_id": model_name,
            "path": str(path.relative_to(ROOT)), "sha256": sha256_file(path),
            "selection_scope": "development_loso", "selection_metric": "AUPRC",
            "development_metrics": {
                key: finite_or_none(metric_row(metrics, model_name, "development_loso")[key])
                for key in ("auprc", "brier", "ece")
            },
            "fixed_pool_audit_metrics": {
                key: finite_or_none(metric_row(metrics, model_name, "fixed_pool_audit")[key])
                for key in ("auprc", "brier", "ece")
            },
            "pool_audit_rows_used_for_fit_or_selection": 0,
            "pool_audit_evaluated_after_selection": True,
            "pool_audit_cryptographically_blinded": False,
            "analysis_status": "EXPLORATORY_NOT_DEPLOYABLE",
            "final_calibration_support": (
                calibration_support
                if model_name in {"M1_CALIBRATED_LOGISTIC", *TEMPORAL_MODELS}
                else {"status": "NOT_APPLICABLE_UNCALIBRATED_MODEL", "deployable": False}
            ),
            "modeling_protocol_sha256": sha256_file(PROTOCOL),
            "heldout_opened": False,
        }
        pointer["artifact_hash"] = canonical_hash(pointer)
        atomic_json(target, pointer)

    write_final_report(
        frame, metrics, control_summary, per_query, per_source, importance,
        bootstrap_intervals, readiness,
    )
    finalized = [
        PREDICTIONS, METRICS, AUXILIARY, CONTROLS, PER_SOURCE, PER_QUERY,
        FEATURE_IMPORTANCE, CALIBRATION_CURVES, BOOTSTRAP_INTERVALS,
        HARD_NEGATIVES, HARD_POSITIVES,
        MODEL_HASHES, BEST_VALUE, BEST_TEMPORAL, READINESS, MODEL_CARD, FINAL_REPORT,
    ]
    audit = {
        "audit_id": "MF_PSVR_STAGE_A_MODELING_COMPLETION_AUDIT_V1",
        "created_at_utc": utc_now(), "status": "PASS",
        "semantic_dataset_rows": len(frame), "binary_evaluation_rows": len(binary),
        "development_binary_rows": len(development), "fixed_pool_audit_binary_rows": len(audit_local),
        "development_source_session_groups": len(set(groups_dev)),
        "source_datasets": int(frame["source_dataset"].nunique()),
        "source_sessions": int(frame[["source_dataset", "session_id"]].drop_duplicates().shape[0]),
        "main_evaluation": "exact_leave_one_source_session_out",
        "random_row_split_used": False, "pool_audit_rows_used_for_fit_or_selection": 0,
        "pool_audit_exclusion": "arithmetic_not_cryptographic",
        "pool_audit_evaluated_after_selection": True,
        "analysis_status": "EXPLORATORY_NOT_PREREGISTERED_OR_CRYPTOGRAPHICALLY_BLINDED",
        "leave_one_dataset_out_status": "NOT_IDENTIFIABLE" if frame["source_dataset"].nunique() == 1 else "COMPLETE",
        "trained_models": PRIMARY_MODELS[2:], "baseline_models": PRIMARY_MODELS[:2],
        "controls": ["SHUFFLED_LABEL_M0", *IDENTITY_CONTROLS, *POSTHOC_NUISANCE_CONTROLS],
        "best_aggregate_model": best_aggregate, "best_temporal_model": best_temporal,
        "selected_representation": selected_representation,
        "readiness_decision": readiness["decision"],
        "artifact_sha256": {path.name: sha256_file(path) for path in finalized},
        "model_hash_manifest_sha256": sha256_file(MODEL_HASHES),
        "dataset_completion_audit_sha256": sha256_file(DATASET_AUDIT),
        "oracle_completion_audit_sha256": sha256_file(ORACLE_AUDIT),
        "execution_difference_audit_sha256": sha256_file(EXECUTION_DIFFERENCE),
        "modeling_protocol_sha256": sha256_file(PROTOCOL),
        "modeling_protocol_provenance_sha256": sha256_file(PROTOCOL_PROVENANCE),
        "final_calibration_support": calibration_support,
        "trainer_source_sha256": sha256_file(Path(__file__)),
        "training_wall_seconds": time.perf_counter() - started,
        "heldout_opened": False,
    }
    audit["audit_hash"] = canonical_hash(audit)
    atomic_json(AUDIT, audit)
    print(json.dumps({
        "phase": "modeling_complete", "best_aggregate": best_aggregate,
        "best_temporal": best_temporal, "selected_representation": selected_representation,
        "readiness": readiness["decision"], "wall_seconds": audit["training_wall_seconds"],
    }), flush=True)
    return audit


def display_number(value: Any, digits: int = 6) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "NA"
    return f"{value:.{digits}f}" if math.isfinite(value) else "NA"


def write_final_report(
    frame: pd.DataFrame,
    metrics: pd.DataFrame,
    control_summary: pd.DataFrame,
    per_query: pd.DataFrame,
    per_source: pd.DataFrame,
    importance: pd.DataFrame,
    bootstrap_intervals: pd.DataFrame,
    readiness: dict[str, Any],
) -> None:
    candidate_audit = load_json(CYCLE / "candidates/CANDIDATE_EXTRACTION_COMPLETION_AUDIT.json")
    candidate_cost = load_json(CYCLE / "candidates/CANDIDATE_EXTRACTION_COST.json")
    oracle_complete = load_json(STAGE / "oracle/STAGE_A_ORACLE_COMPLETE.json")
    stage_state = load_json(STAGE / "STAGE_A_STATE.json")
    support_gate = load_json(STAGE / "STAGE_A_SUPPORT_GATE_REPORT.json")
    execution_difference = load_json(STAGE / "STAGE_A_EXECUTION_DIFFERENCE_AUDIT.json")
    roundtrip_audit = load_json(ORACLE_AUDIT)
    protocol_provenance = load_json(PROTOCOL_PROVENANCE)
    feature_schema = load_json(FEATURE_SCHEMA)
    physical_cost = load_json(STAGE / "STAGE_A_PHYSICAL_COST.json")
    labels = pd.read_csv(CYCLE / "ORACLE_LABEL_MANIFEST.csv", keep_default_na=False)
    groups = pd.read_csv(STAGE / "STAGE_A_K3_EVENT_GROUPS.csv", keep_default_na=False)
    best_aggregate = readiness["best_aggregate_model"]
    best_temporal = readiness["best_temporal_model"]
    selected = readiness["selected_representation"]
    aggregate_dev = metric_row(metrics, best_aggregate, "development_loso")
    temporal_dev = metric_row(metrics, best_temporal, "development_loso")
    selected_dev = metric_row(metrics, selected, "development_loso")
    raw_dev = metric_row(metrics, "B0_RAW_YOLO", "development_loso")
    shuffled = control_summary[control_summary["control"] == "SHUFFLED_LABEL_M0"].iloc[0]
    identity = control_summary[control_summary["control"].isin(IDENTITY_CONTROLS)]
    strongest_identity = float(identity["auprc_mean"].max())
    stratum_control = float(control_summary.loc[
        control_summary["control"] == "SELECTION_STRATUM_ONLY", "auprc_mean"
    ].iloc[0])
    anchor_control = float(control_summary.loc[
        control_summary["control"] == "ANCHOR_ID_ONLY", "auprc_mean"
    ].iloc[0])
    query_rows = per_query[
        (per_query["evaluation_scope"] == "development_loso") & (per_query["model"] == selected)
    ].sort_values("query_id")
    raw_query = per_query[
        (per_query["evaluation_scope"] == "development_loso") & (per_query["model"] == "B0_RAW_YOLO")
    ].set_index("query_id")
    selected_audit_query = per_query[
        (per_query["evaluation_scope"] == "fixed_pool_audit") & (per_query["model"] == selected)
    ].set_index("query_id")
    raw_audit_query = per_query[
        (per_query["evaluation_scope"] == "fixed_pool_audit") & (per_query["model"] == "B0_RAW_YOLO")
    ].set_index("query_id")
    query_lines = "\n".join(
        f"- {row.query_id}: development n={int(row.n)}, positives={int(row.positives)}, selected/raw AUPRC={display_number(row.auprc)}/{display_number(raw_query.loc[row.query_id, 'auprc'])}; fixed-audit selected/raw AUPRC={display_number(selected_audit_query.loc[row.query_id, 'auprc'])}/{display_number(raw_audit_query.loc[row.query_id, 'auprc'])}, selected ECE={display_number(selected_audit_query.loc[row.query_id, 'ece'])}."
        for row in query_rows.itertuples()
    )
    selected_vs_raw_bootstrap = bootstrap_intervals[
        (bootstrap_intervals["evaluation_scope"] == "development_loso")
        & (bootstrap_intervals["comparison"] == "selected_minus_raw_yolo")
    ].set_index("metric")
    temporal_vs_aggregate_bootstrap = bootstrap_intervals[
        (bootstrap_intervals["evaluation_scope"] == "development_loso")
        & (bootstrap_intervals["comparison"] == "best_temporal_minus_best_aggregate")
    ].set_index("metric")
    aggregate_query = per_query[
        (per_query["evaluation_scope"] == "development_loso") & (per_query["model"] == best_aggregate)
    ].set_index("query_id")
    temporal_query = per_query[
        (per_query["evaluation_scope"] == "development_loso") & (per_query["model"] == best_temporal)
    ].set_index("query_id")
    temporal_query_deltas = ", ".join(
        f"{query_id} {float(temporal_query.loc[query_id, 'auprc'] - aggregate_query.loc[query_id, 'auprc']):+.6f}"
        for query_id in ("Q1", "Q2")
    )
    worst = per_source[
        (per_source["evaluation_scope"] == "development_loso") & (per_source["model"] == selected)
    ].sort_values(["brier", "source_dataset", "session_id"], ascending=[False, True, True]).iloc[0]
    top_importance = importance[importance["model"] == best_aggregate].head(10)
    importance_lines = "\n".join(
        f"- `{row.feature}`: {row.importance:.6f} ({row.importance_type})"
        for row in top_importance.itertuples()
    ) or "- No coefficient/gain importance was available (one-class fallback)."
    q1_positive = int(((labels["query_id"] == "Q1") & (labels["projected_label"] == "positive")).sum())
    q2_positive = int(((labels["query_id"] == "Q2") & (labels["projected_label"] == "positive")).sum())
    q1_groups = int((groups["query_id"] == "Q1").sum()) if len(groups) else 0
    q2_groups = int((groups["query_id"] == "Q2").sum()) if len(groups) else 0
    best_model_path = ROOT / load_json(BEST_TEMPORAL if selected in TEMPORAL_MODELS else BEST_VALUE)["path"]
    next_stage = (
        "PREREGISTER_BOUNDED_MF_PSVR_PHYSICAL_PILOT_DESIGN"
        if readiness["ready"] else "ADD_SECOND_QUERY_ALIGNED_SOURCE_DATASET_AND_REPEAT_STAGE_A_MODEL_AUDIT"
    )
    physical_total = physical_cost.get(
        "total_physical_cost_seconds",
        physical_cost.get("preparation_plus_inference_wall_seconds", np.nan),
    )
    calibration = readiness["final_calibration_support"]
    forced = f"""CANDIDATE_EXTRACTION_STATUS = {candidate_audit['status']}
PROVIDER_VIDEOS_COMPLETED = {candidate_audit['completed_provider_videos']}
UNIT_SCORE_ROWS = {candidate_audit['observed_unit_score_rows']}
CANDIDATE_EXTRACTION_GPU_SECONDS = {candidate_cost['detector_gpu_seconds']}

STAGE_A_STATE = {stage_state['status']}
STAGE_A_ORACLE_EXECUTION_STATE = {oracle_complete['status']}
STAGE_A_DEFAULT_FROZEN_VERIFY = {execution_difference['frozen_runner_verification']['status']}
STAGE_A_ROUNDTRIP_FROZEN_VERIFY = {roundtrip_audit['frozen_verify_result']['status']}
STAGE_A_PHYSICAL_ATTEMPTS = {oracle_complete['physical_attempts_started']}
STAGE_A_ACCEPTED_DURABLE_CALLS = {oracle_complete['accepted_durable_calls']}
STAGE_A_UNCERTAIN_CALLS = {oracle_complete['uncertain_started_calls']}
STAGE_A_PARSE_FAILURES = {oracle_complete['parse_failures']}
STAGE_A_Q1_POSITIVES = {q1_positive}
STAGE_A_Q2_POSITIVES = {q2_positive}
STAGE_A_Q1_EVENT_GROUPS = {q1_groups}
STAGE_A_Q2_EVENT_GROUPS = {q2_groups}
STAGE_A_TOTAL_PHYSICAL_COST_SECONDS = {physical_total}
STAGE_A_SUPPORT_DECISION = {oracle_complete['support_decision']}

TRAINING_SEMANTIC_SAMPLES = {len(frame)}
TRAINING_SOURCE_DATASETS = {frame['source_dataset'].nunique()}
TRAINING_SOURCE_SESSIONS = {frame[['source_dataset', 'session_id']].drop_duplicates().shape[0]}

BEST_AGGREGATED_MODEL = {best_aggregate}
BEST_AGGREGATED_LOSO_AUPRC = {display_number(aggregate_dev['auprc'])}
BEST_AGGREGATED_MACRO_QUERY_AUPRC = {display_number(aggregate_dev['macro_query_auprc'])}
BEST_TEMPORAL_REFINER = {best_temporal}
BEST_TEMPORAL_REFINER_LOSO_AUPRC = {display_number(temporal_dev['auprc'])}
BEST_TEMPORAL_REFINER_MACRO_QUERY_AUPRC = {display_number(temporal_dev['macro_query_auprc'])}
BEST_MODEL_BRIER = {display_number(selected_dev['brier'])}
BEST_MODEL_ECE = {display_number(selected_dev['ece'])}

RAW_YOLO_AUPRC = {display_number(raw_dev['auprc'])}
SHUFFLED_LABEL_AUPRC = {display_number(shuffled['auprc_mean'])}
ID_ONLY_AUPRC = {display_number(strongest_identity)}
SELECTION_STRATUM_ONLY_AUPRC = {display_number(stratum_control)}
ANCHOR_ID_ONLY_AUPRC = {display_number(anchor_control)}

QUERY_CONDITIONING_SIGNAL = {readiness['query_conditioning_signal']}
TEMPORAL_REFINEMENT_SIGNAL = {readiness['temporal_refinement_signal']}
MODEL_READY_FOR_PHYSICAL_PILOT = {'YES' if readiness['ready'] else 'NO'}
FINAL_CALIBRATOR_STATUS = {calibration['status']}
FINAL_CALIBRATOR_DEPLOYABLE = {'YES' if calibration['deployable'] else 'NO'}
MODELING_ANALYSIS_STATUS = {readiness['analysis_status']}

BEST_MODEL_PATH = {best_model_path.relative_to(ROOT)}
BEST_MODEL_SHA256 = {sha256_file(best_model_path)}
NEXT_RESEARCH_STAGE = {next_stage}
NEXT_EXACT_COMMAND = python scripts/run_mf_psvr_stage_a_modeling.py verify
"""
    report = f"""# MF-PSVR Stage A to model final report

## Mandatory result block

```text
{forced.rstrip()}
```

## Strongest supported conclusion

{readiness['strongest_supported_conclusion']} The best aggregate representation is `{best_aggregate}` and the best temporal representation is `{best_temporal}`. Their pooled exact development-LOSO AUPRC values are {display_number(aggregate_dev['auprc'])} and {display_number(temporal_dev['auprc'])}; their macro-query AUPRC values are {display_number(aggregate_dev['macro_query_auprc'])} and {display_number(temporal_dev['macro_query_auprc'])}. The representation selected without using `pool_audit` is `{selected}`. Pooled lift is not treated as a uniform learned refinement because Q1/Q2 behavior and nuisance controls differ materially.

## Decisive evidence

- Candidate extraction independently reconciled all {candidate_audit['completed_provider_videos']} frozen providers and {candidate_audit['observed_unit_score_rows']} query-unit rows.
- Oracle accounting reconciled {oracle_complete['physical_attempts_started']} STARTED attempts, {oracle_complete['accepted_durable_calls']} durable accepted calls, {oracle_complete['uncertain_started_calls']} uncertain calls, and {oracle_complete['parse_failures']} retained parse failures.
- The oracle execution finalized a `COMPLETE_COMMIT`. The default frozen verify command reproducibly fails because pandas' default CSV parser changes one textual runtime float before an exact-equality check. The hash-frozen verifier reaches `{roundtrip_audit['frozen_verify_result']['status']}` when only its module-local CSV float parser is switched to round-trip mode; the bound exception audit status is `{execution_difference['status']}`.
- Main model results are pooled predictions from exact leave-one-provider-session-out fits on development roles. No random row split or source/session identity feature is used by an effective model.
- The fixed `pool_audit` role was arithmetically excluded from fitting and model selection, then evaluated separately. The full dataset was available locally; this was not a cryptographic blind.
- The modeling protocol is exploratory, not preregistered: {protocol_provenance['raw_envelopes_present_before_or_at_protocol_mtime']} human-readable raw oracle envelopes already existed when it was fixed. The physical oracle protocol remains separately frozen before calls.
- The strongest identity-only, selection-stratum-only, and anchor-only development AUPRC values are {display_number(strongest_identity)}, {display_number(stratum_control)}, and {display_number(anchor_control)}. The 32 fold-specific shuffled-label runs have mean {display_number(shuffled['auprc_mean'])} and empirical 95th percentile {display_number(shuffled['auprc_p95'])}; 32 repetitions are a noisy diagnostic, not a formal significance test.
- A paired provider-session bootstrap conditional on the fixed OOF predictions estimates selected-minus-raw pooled AUPRC at {display_number(selected_vs_raw_bootstrap.loc['auprc', 'estimate'])} (descriptive 95% interval {display_number(selected_vs_raw_bootstrap.loc['auprc', 'ci_lower_2_5'])} to {display_number(selected_vs_raw_bootstrap.loc['auprc', 'ci_upper_97_5'])}) and macro-query AUPRC at {display_number(selected_vs_raw_bootstrap.loc['macro_query_auprc', 'estimate'])} ({display_number(selected_vs_raw_bootstrap.loc['macro_query_auprc', 'ci_lower_2_5'])} to {display_number(selected_vs_raw_bootstrap.loc['macro_query_auprc', 'ci_upper_97_5'])}). These intervals do not cover dataset-to-dataset transport uncertainty.

## Exploratory aggregate-feature associations

The aggregate schema retained {feature_schema['aggregate_redundancy_pruning']['retained_feature_count']} of {feature_schema['aggregate_redundancy_pruning']['candidate_feature_count']} candidates in a label-free full-rank basis. Raw numeric witness class is excluded. The following are coefficient-magnitude or LightGBM-gain associations, not independently identified feature effects or causal effects:

{importance_lines}

These entries are hypothesis generators only. Even after algebraic redundancy pruning, regularization, correlation, and the small positive count make individual attribution unstable.

## Temporal refinement

The temporal-minus-aggregate development LOSO AUPRC difference is {readiness['temporal_minus_aggregate_auprc']:+.6f}, classified as `{readiness['temporal_refinement_signal']}` by a post-hoc descriptive 0.02 rule that was absent from the modeling protocol. Its paired provider-session bootstrap interval is {display_number(temporal_vs_aggregate_bootstrap.loc['auprc', 'ci_lower_2_5'])} to {display_number(temporal_vs_aggregate_bootstrap.loc['auprc', 'ci_upper_97_5'])}; this is conditional on fixed OOF predictions. Per-query temporal-minus-aggregate AUPRC deltas are {temporal_query_deltas}, so direction and magnitude must be inspected rather than inferred from the pooled value. Both temporal models are causal, query-conditioned, have hidden width 32, use fixed trajectories only, and do not train an RGB backbone or YOLO. At the primary budget of 16 physical VERIFY calls, query probabilities are aggregated by maximum and a call is positive if either query is positive; `{selected}` recovers {int(selected_dev['physical_call_top_16_positive_recovery'])}/{int(selected_dev['physical_positive_calls'])} development-positive calls (precision {selected_dev['physical_call_precision_at_16']:.4f}, recall {selected_dev['physical_call_recall_at_16']:.4f}). Semantic-opportunity top-k metrics are separately named in the metric table.

## Q1 versus Q2 learnability

{query_lines}

Explicit query-column ablation of the selected aggregate model (`{readiness['query_conditioning_reference_model']}` versus `{readiness['query_conditioning_ablation_model']}`) changes development AUPRC by {readiness['query_conditioning_auprc_delta']:+.6f}. This is classified as `{readiness['query_conditioning_signal']}` by the same post-hoc descriptive rule. Caveat: {readiness['query_signal_caveat']}

## Calibration limitation

The final calibration role contains {calibration['positives']} positive and {calibration['negatives']} negative binary rows; Q1/Q2 contribute {calibration['per_query']['Q1']['positives']}/{calibration['per_query']['Q2']['positives']} positives. Status is `{calibration['status']}`. Serialized M1/TCN/GRU Platt maps reproduce this exploratory run only and are not deployable calibrators.

## Worst provider-session result

For `{selected}`, the highest development-fold Brier source/session is `{worst.source_dataset}/{worst.session_id}` with n={int(worst.n)}, positives={int(worst.positives)}, Brier={display_number(worst.brier)}, and AUPRC={display_number(worst.auprc)}. Per-session AUPRC is intentionally undefined for one-class folds; Brier is used to identify the worst fold without inventing a ranking metric.

## Main competing explanation and unresolved uncertainty

{readiness['main_competing_explanation']} {readiness['key_uncertainty']} The frozen support gate failed specifically because the calibration role had only {support_gate['per_query']['Q1']['split_usability']['model_calibration']['positive_units']} Q1 positive and {support_gate['per_query']['Q2']['split_usability']['model_calibration']['positive_units']} Q2 positives, even though overall support existence passed for both queries. The data still lack a second source dataset, natural-prevalence sampling, and enough independent positive event groups for narrow source-specific claims. Unit outcomes also cannot be interpreted as verified witness-track labels.

## Decision and next action

The exploratory readiness decision is `{readiness['decision']}`. Independently, the frozen semantic support state is `{stage_state['status']}` because the oracle support decision is `{stage_state['support_decision']}`. {readiness['next_action']} The observation that would trigger rejection or revision is: {readiness['rejection_trigger']}

This run stops before any V0/V1 physical-method matrix. The exact next command above only re-verifies the completed Stage-A modeling handoff; it does not authorize or execute a physical pilot.
"""
    atomic_bytes(FINAL_REPORT, report.encode("utf-8"))


def verify() -> dict[str, Any]:
    frame, features, arrays, _ = validate_and_load()
    required = [
        PREDICTIONS, METRICS, AUXILIARY, CONTROLS, PER_SOURCE, PER_QUERY,
        FEATURE_IMPORTANCE, CALIBRATION_CURVES, BOOTSTRAP_INTERVALS,
        HARD_NEGATIVES, HARD_POSITIVES,
        MODEL_HASHES, BEST_VALUE, BEST_TEMPORAL, READINESS, MODEL_CARD, FINAL_REPORT, AUDIT,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Final modeling artifact set is incomplete: {missing}")
    predictions = pd.read_parquet(PREDICTIONS)
    if predictions["semantic_sample_id"].duplicated().any():
        raise RuntimeError("Primary prediction identities are duplicated")
    binary_ids = set(frame.loc[frame["label_binary"].notna(), "semantic_sample_id"].astype(str))
    if set(predictions["semantic_sample_id"].astype(str)) != binary_ids:
        raise RuntimeError("Primary prediction universe differs from binary dataset universe")
    if predictions[ALL_PREDICTION_MODELS].isna().any().any():
        raise RuntimeError("Primary predictions contain NaN")
    development = predictions[predictions["evaluation_scope"] == "development_loso"]
    fixed_audit = predictions[predictions["evaluation_scope"] == "fixed_pool_audit"]
    if set(development["model_split_role"]) - DEVELOPMENT_ROLES or set(fixed_audit["model_split_role"]) != {"pool_audit"}:
        raise RuntimeError("Primary evaluation scope crosses frozen split roles")
    if set(development["source_session_group"]) & set(fixed_audit["source_session_group"]):
        raise RuntimeError("Development/audit source-session leakage detected")
    expected_metrics, expected_curves, expected_per_source, expected_per_query = build_metric_tables(predictions)
    for path, expected in (
        (METRICS, expected_metrics), (CALIBRATION_CURVES, expected_curves),
        (PER_SOURCE, expected_per_source), (PER_QUERY, expected_per_query),
    ):
        observed = pd.read_csv(path)
        pd.testing.assert_frame_equal(observed, expected, check_dtype=False, atol=1e-12, rtol=1e-12)
    readiness_for_bootstrap = load_json(READINESS)
    expected_bootstrap = group_bootstrap_intervals(
        predictions,
        readiness_for_bootstrap["selected_representation"],
        readiness_for_bootstrap["best_aggregate_model"],
        readiness_for_bootstrap["best_temporal_model"],
    )
    pd.testing.assert_frame_equal(
        pd.read_csv(BOOTSTRAP_INTERVALS), expected_bootstrap,
        check_dtype=False, atol=1e-12, rtol=1e-12,
    )
    hashes = load_json(MODEL_HASHES)
    claimed = hashes.get("manifest_hash")
    if claimed != canonical_hash({key: value for key, value in hashes.items() if key != "manifest_hash"}):
        raise RuntimeError("Model hash manifest self-hash is invalid")
    for model_name, binding in hashes["models"].items():
        path = ROOT / binding["path"]
        if not path.is_file() or sha256_file(path) != binding["sha256"]:
            raise RuntimeError(f"Serialized model binding changed: {model_name}")
    expected_bindings = {
        "dataset_sha256": sha256_file(DATASET),
        "dataset_completion_audit_sha256": sha256_file(DATASET_AUDIT),
        "feature_schema_sha256": sha256_file(FEATURE_SCHEMA),
        "temporal_sequences_sha256": sha256_file(TEMPORAL),
        "temporal_schema_sha256": sha256_file(TEMPORAL_SCHEMA),
        "modeling_protocol_sha256": sha256_file(PROTOCOL),
        "modeling_protocol_provenance_sha256": sha256_file(PROTOCOL_PROVENANCE),
        "oracle_roundtrip_verification_audit_sha256": sha256_file(ORACLE_AUDIT),
        "execution_difference_audit_sha256": sha256_file(EXECUTION_DIFFERENCE),
        "trainer_source_sha256": sha256_file(Path(__file__)),
    }
    if hashes["bindings"] != expected_bindings:
        raise RuntimeError("Model input/source binding changed")
    for pointer_path in (BEST_VALUE, BEST_TEMPORAL):
        pointer = load_json(pointer_path)
        if pointer.get("artifact_hash") != canonical_hash({key: value for key, value in pointer.items() if key != "artifact_hash"}):
            raise RuntimeError(f"Best-model pointer self-hash invalid: {pointer_path.name}")
        model_path = ROOT / pointer["path"]
        if sha256_file(model_path) != pointer["sha256"]:
            raise RuntimeError(f"Best-model pointer binding changed: {pointer_path.name}")
        if pointer.get("pool_audit_rows_used_for_fit_or_selection") != 0:
            raise RuntimeError("Pool audit entered model fitting or selection")
        if pointer.get("pool_audit_cryptographically_blinded") is not False:
            raise RuntimeError("Pointer misstates the pool-audit blinding status")
        if pointer.get("final_calibration_support", {}).get("deployable") is not False:
            raise RuntimeError("Pointer improperly marks a final calibrator deployable")
    readiness = readiness_for_bootstrap
    if readiness.get("decision_hash") != canonical_hash({key: value for key, value in readiness.items() if key != "decision_hash"}):
        raise RuntimeError("Readiness decision self-hash is invalid")
    audit = load_json(AUDIT)
    if audit.get("audit_hash") != canonical_hash({key: value for key, value in audit.items() if key != "audit_hash"}):
        raise RuntimeError("Modeling completion audit self-hash is invalid")
    if audit.get("status") != "PASS" or audit.get("heldout_opened") is not False:
        raise RuntimeError("Modeling completion audit status invalid")
    current_audit_bindings = {
        "dataset_completion_audit_sha256": sha256_file(DATASET_AUDIT),
        "oracle_completion_audit_sha256": sha256_file(ORACLE_AUDIT),
        "execution_difference_audit_sha256": sha256_file(EXECUTION_DIFFERENCE),
        "modeling_protocol_sha256": sha256_file(PROTOCOL),
        "modeling_protocol_provenance_sha256": sha256_file(PROTOCOL_PROVENANCE),
        "trainer_source_sha256": sha256_file(Path(__file__)),
    }
    if any(audit.get(key) != value for key, value in current_audit_bindings.items()):
        raise RuntimeError("Modeling completion audit prerequisite/source binding changed")
    for name, digest in audit["artifact_sha256"].items():
        matches = [path for path in required if path.name == name]
        if len(matches) != 1 or sha256_file(matches[0]) != digest:
            raise RuntimeError(f"Final modeling artifact binding changed: {name}")
    if set(features) & FORBIDDEN_FEATURES:
        raise RuntimeError("Forbidden effective feature detected during final verify")
    if arrays.raw.shape != (192, 64, 18):
        raise RuntimeError("Temporal input shape changed during final verify")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["train", "verify"])
    args = parser.parse_args()
    result = train() if args.stage == "train" else verify()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
