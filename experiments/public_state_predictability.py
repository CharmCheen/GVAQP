"""Leave-one-source-out predictability screen for cached branch Q values.

The input must be the paired branch table produced by
``controller_dynamic_headroom.py``.  All fitted features are public-state
summaries.  Evaluator Q values are targets only and never enter the features.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


PUBLIC_FEATURES = (
    "elapsed_fraction",
    "remaining_fraction",
    "scanned_fraction",
    "frontier_size",
    "frontier_top_score",
    "frontier_mean_score",
    "committed_event_count",
    "scan_count",
    "verify_count",
    "scan_verify_balance",
)
FIXED_RATIOS = (0.10, 0.25, 0.50, 0.75, 0.90)


def load_rows(path: Path) -> pd.DataFrame:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows = []
    for record in records:
        budget = float(record["budget"])
        scan_count = int(record["scan_count"])
        verify_count = int(record["verify_count"])
        rows.append(
            {
                "domain": record["domain"],
                "video_id": record["video_id"],
                "state_hash": record["state_hash"],
                "delta_q": float(record["delta_q"]),
                "q_scan": float(record["scan_branch"]["q"]),
                "q_verify": float(record["verify_branch"]["q"]),
                "elapsed_fraction": float(record["elapsed"]) / budget,
                "remaining_fraction": float(record["remaining"]) / budget,
                "scanned_fraction": float(record["scanned_fraction"]),
                "frontier_size": int(record["frontier_size"]),
                "frontier_top_score": float(record["frontier_top_score"]),
                "frontier_mean_score": float(record["frontier_mean_score"]),
                "committed_event_count": int(record["committed_event_count"]),
                "scan_count": scan_count,
                "verify_count": verify_count,
                "scan_verify_balance": (scan_count - verify_count)
                / max(1, scan_count + verify_count),
                "id_only": int(record["state_hash"][:8], 16) / 0xFFFFFFFF,
            }
        )
    frame = pd.DataFrame(rows)
    if len(frame.video_id.unique()) < 2:
        raise RuntimeError("leave-one-source-out requires at least two source videos")
    return frame


def sigmoid(values: np.ndarray, scale: float) -> np.ndarray:
    scale = max(float(scale), 1e-9)
    clipped = np.clip(np.asarray(values, dtype=float) / scale, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def expected_metrics(delta: np.ndarray, probability_scan: np.ndarray) -> dict[str, float]:
    delta = np.asarray(delta, dtype=float)
    probability_scan = np.clip(np.asarray(probability_scan, dtype=float), 0.0, 1.0)
    regret = np.where(
        delta > 0,
        (1.0 - probability_scan) * delta,
        probability_scan * (-delta),
    )
    non_tie = np.abs(delta) > 1e-12
    if not non_tie.any():
        return {
            "decision_regret": float(regret.mean()),
            "weighted_sign_accuracy": math.nan,
            "top_margin_accuracy": math.nan,
            "brier": math.nan,
            "ece_5bin": math.nan,
        }
    labels = (delta[non_tie] > 0).astype(float)
    probabilities = probability_scan[non_tie]
    weights = np.abs(delta[non_tie])
    expected_correct = np.where(labels == 1, probabilities, 1.0 - probabilities)
    weighted_accuracy = float(np.average(expected_correct, weights=weights))
    threshold = np.quantile(weights, 0.75)
    top = weights >= threshold
    top_accuracy = float(np.mean(expected_correct[top]))
    brier = float(np.mean((probabilities - labels) ** 2))
    ece = 0.0
    for left in np.linspace(0.0, 0.8, 5):
        right = left + 0.2
        selected = (probabilities >= left) & (
            probabilities <= right if right >= 1.0 else probabilities < right
        )
        if selected.any():
            ece += selected.mean() * abs(probabilities[selected].mean() - labels[selected].mean())
    return {
        "decision_regret": float(regret.mean()),
        "weighted_sign_accuracy": weighted_accuracy,
        "top_margin_accuracy": top_accuracy,
        "brier": brier,
        "ece_5bin": float(ece),
    }


def fit_probabilities(method: str, train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    x_train = train[list(PUBLIC_FEATURES)].to_numpy(dtype=float)
    x_test = test[list(PUBLIC_FEATURES)].to_numpy(dtype=float)
    y_train = train.delta_q.to_numpy(dtype=float)
    scale = float(np.std(y_train))

    if method == "always_scan":
        return np.ones(len(test))
    if method == "always_verify":
        return np.zeros(len(test))
    if method == "best_fixed_action":
        scan_regret = expected_metrics(y_train, np.ones(len(train)))["decision_regret"]
        verify_regret = expected_metrics(y_train, np.zeros(len(train)))["decision_regret"]
        return np.full(len(test), float(scan_regret <= verify_regret))
    if method == "best_fixed_ratio":
        ratio = min(
            FIXED_RATIOS,
            key=lambda value: expected_metrics(y_train, np.full(len(train), value))[
                "decision_regret"
            ],
        )
        return np.full(len(test), ratio)
    if method == "logistic":
        selected = np.abs(y_train) > 1e-12
        labels = (y_train[selected] > 0).astype(int)
        if len(np.unique(labels)) < 2:
            return np.full(len(test), labels[0] if len(labels) else 0.5)
        model = make_pipeline(
            StandardScaler(), LogisticRegression(C=1.0, max_iter=2000, random_state=0)
        ).fit(x_train[selected], labels)
        return model.predict_proba(x_test)[:, 1]
    if method == "linear":
        prediction = make_pipeline(StandardScaler(), LinearRegression()).fit(
            x_train, y_train
        ).predict(x_test)
        return sigmoid(prediction, scale)
    if method == "hist_gradient_boosting":
        prediction = HistGradientBoostingRegressor(
            max_depth=3, max_iter=80, learning_rate=0.05, random_state=0
        ).fit(x_train, y_train).predict(x_test)
        return sigmoid(prediction, scale)
    if method == "small_mlp":
        prediction = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(8,),
                alpha=0.1,
                max_iter=2000,
                early_stopping=True,
                random_state=0,
            ),
        ).fit(x_train, y_train).predict(x_test)
        return sigmoid(prediction, scale)
    if method == "contextual_bandit":
        scaler = StandardScaler().fit(x_train)
        train_scaled = scaler.transform(x_train)
        test_scaled = scaler.transform(x_test)
        scan_model = Ridge(alpha=1.0).fit(train_scaled, train.q_scan)
        verify_model = Ridge(alpha=1.0).fit(train_scaled, train.q_verify)
        advantage = scan_model.predict(test_scaled) - verify_model.predict(test_scaled)
        return sigmoid(advantage, scale)
    if method == "shuffled_state":
        rng = np.random.default_rng(20260730)
        shuffled = x_train[rng.permutation(len(x_train))]
        prediction = make_pipeline(StandardScaler(), LinearRegression()).fit(
            shuffled, y_train
        ).predict(x_test)
        return sigmoid(prediction, scale)
    if method == "id_only":
        prediction = LinearRegression().fit(
            train[["id_only"]], y_train
        ).predict(test[["id_only"]])
        return sigmoid(prediction, scale)
    if method == "oracle_upper_bound":
        return np.where(test.delta_q.to_numpy() > 1e-12, 1.0, 0.0)
    raise ValueError(method)


METHODS = (
    "always_scan",
    "always_verify",
    "best_fixed_action",
    "best_fixed_ratio",
    "logistic",
    "linear",
    "hist_gradient_boosting",
    "small_mlp",
    "contextual_bandit",
    "shuffled_state",
    "id_only",
    "oracle_upper_bound",
)


def execute(branches: Path, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    frame = load_rows(branches)
    metrics_rows = []
    prediction_rows = []
    for heldout in sorted(frame.video_id.unique()):
        train = frame[frame.video_id != heldout].reset_index(drop=True)
        test = frame[frame.video_id == heldout].reset_index(drop=True)
        for method in METHODS:
            probabilities = fit_probabilities(method, train, test)
            metrics = expected_metrics(test.delta_q.to_numpy(), probabilities)
            metrics_rows.append(
                {
                    "heldout_video_id": heldout,
                    "method": method,
                    "train_rows": len(train),
                    "test_rows": len(test),
                    **metrics,
                }
            )
            for row, probability in zip(test.itertuples(index=False), probabilities):
                prediction_rows.append(
                    {
                        "heldout_video_id": heldout,
                        "method": method,
                        "state_hash": row.state_hash,
                        "delta_q": row.delta_q,
                        "probability_scan": float(probability),
                    }
                )
    metrics = pd.DataFrame(metrics_rows)
    predictions = pd.DataFrame(prediction_rows)
    metrics.to_csv(output / "fold_metrics.csv", index=False)
    predictions.to_csv(output / "predictions.csv", index=False)
    macro = metrics.groupby("method", as_index=False)[
        ["decision_regret", "weighted_sign_accuracy", "top_margin_accuracy", "brier", "ece_5bin"]
    ].mean()
    macro.to_csv(output / "macro_metrics.csv", index=False)
    best_fixed_ratio = macro[macro.method == "best_fixed_ratio"].iloc[0]
    best_fixed_action = macro[macro.method == "best_fixed_action"].iloc[0]
    learned_names = {
        "logistic",
        "linear",
        "hist_gradient_boosting",
        "small_mlp",
        "contextual_bandit",
    }
    best_learned = macro[macro.method.isin(learned_names)].sort_values(
        ["decision_regret", "method"]
    ).iloc[0]
    state_gate_pass = bool(
        float(best_learned.decision_regret) < float(best_fixed_action.decision_regret)
        and float(best_learned.weighted_sign_accuracy)
        > max(
            float(macro[macro.method == "id_only"].weighted_sign_accuracy.iloc[0]),
            float(macro[macro.method == "shuffled_state"].weighted_sign_accuracy.iloc[0]),
        )
    )
    summary = {
        "schema_version": "CACHED_PUBLIC_STATE_PREDICTABILITY_V1",
        "classification": "cached_abstract_cost_leave_one_source_out_not_physical",
        "source_video_count": int(frame.video_id.nunique()),
        "state_count": len(frame),
        "public_features": list(PUBLIC_FEATURES),
        "best_learned_method": str(best_learned.method),
        "best_learned_decision_regret": float(best_learned.decision_regret),
        "best_learned_weighted_sign_accuracy": float(
            best_learned.weighted_sign_accuracy
        ),
        "best_fixed_action_method": "always_verify",
        "best_fixed_action_decision_regret": float(best_fixed_action.decision_regret),
        "best_fixed_action_weighted_sign_accuracy": float(
            best_fixed_action.weighted_sign_accuracy
        ),
        "best_fixed_ratio_decision_regret": float(best_fixed_ratio.decision_regret),
        "learned_regret_ratio_to_best_fixed_action": (
            float(best_learned.decision_regret) / float(best_fixed_action.decision_regret)
            if float(best_fixed_action.decision_regret)
            else None
        ),
        "cached_public_state_gate_pass": state_gate_pass,
        "macro_metrics": macro.to_dict(orient="records"),
        "limitations": [
            "only two independent source videos",
            "Q targets use older cached query/reference and abstract action costs",
            "branch states were sampled rather than population-weighted",
            "predictive utility does not establish closed-loop utility",
            "LightGBM is not installed; sklearn HistGradientBoosting is reported as the available tree control",
        ],
        "input_sha256": hashlib.sha256(branches.read_bytes()).hexdigest(),
    }
    (output / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branches", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execute(args.branches.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
