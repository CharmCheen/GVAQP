#!/usr/bin/env python3
"""Frozen probe_set_v1 signal evaluation relative to VLM oracle labels.

No selector tuning, threshold tuning, or feature selection from probe labels.
Representative feature/direction choices are read from the pre-existing
6-event diagnostic table.
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "outputs/agent_loop_v1/probe_eval_after_vlm_oracle"
LABELS = ROOT / "outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv"
INTERVAL_FEATURES = ROOT / "outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv"
DIAG_METRICS = ROOT / "outputs/cheap_signal_v2/signal_upgrade_within_bin_metrics.csv"
REFERENCE_SOURCE = "probe_set_v1_vlm_oracle_reference"
BOOTSTRAP_N = 2000
SEED = 20260703


REPRESENTATIVE_FEATURES = [
    ("existing_signal", "motion_energy_mean"),
    ("track_interaction_signal", "track_mean_track_speed_mean"),
    ("track_interaction_signal", "track_mean_relative_speed_mean"),
    ("inside_outside_contrast_signal", "contrast_optical_flow_burst_z_max"),
    ("inside_outside_contrast_signal", "contrast_object_density_change_z_min"),
    ("inside_outside_contrast_signal", "contrast_optical_flow_burst_z_mean"),
]


def auc_mann_whitney(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y).astype(int)
    score = np.asarray(score).astype(float)
    pos = score[y == 1]
    neg = score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return math.nan
    wins = 0.0
    for p in pos:
        wins += np.sum(p > neg) + 0.5 * np.sum(p == neg)
    return float(wins / (len(pos) * len(neg)))


def topk_metrics(y: np.ndarray, score: np.ndarray, k: int) -> tuple[float, float]:
    n = len(y)
    k = min(k, n)
    order = np.lexsort((np.arange(n), -score))
    top = order[:k]
    tp = float(np.sum(y[top] == 1))
    precision = tp / k if k else math.nan
    positives = float(np.sum(y == 1))
    coverage = tp / positives if positives else math.nan
    return precision, coverage


def ci(vals: list[float]) -> tuple[float, float]:
    arr = np.asarray([v for v in vals if not math.isnan(v)], dtype=float)
    if len(arr) == 0:
        return math.nan, math.nan
    return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


def summarize_metric(y: np.ndarray, score: np.ndarray, rng: np.random.Generator) -> dict:
    out = {}
    out["auc"] = auc_mann_whitney(y, score)
    for k in (5, 10, 20):
        p, cov = topk_metrics(y, score, k)
        out[f"precision_at_{k}"] = p
        out[f"positive_coverage_at_{k}"] = cov

    boot = {name: [] for name in out}
    n = len(y)
    for _ in range(BOOTSTRAP_N):
        idx = rng.integers(0, n, n)
        yy = y[idx]
        ss = score[idx]
        boot["auc"].append(auc_mann_whitney(yy, ss))
        for k in (5, 10, 20):
            p, cov = topk_metrics(yy, ss, k)
            boot[f"precision_at_{k}"].append(p)
            boot[f"positive_coverage_at_{k}"].append(cov)
    for name, vals in boot.items():
        lo, hi = ci(vals)
        out[f"{name}_ci_low"] = lo
        out[f"{name}_ci_high"] = hi
    return out


def aggregate_probe_scores(labels: pd.DataFrame, intervals: pd.DataFrame, feature: str, direction: str) -> pd.DataFrame:
    rows = []
    for _, probe in labels.iterrows():
        ps = float(probe["local_t_start"])
        pe = float(probe["local_t_end"])
        overlap = np.minimum(intervals["t_end"].to_numpy(float), pe) - np.maximum(intervals["t_start"].to_numpy(float), ps)
        mask = overlap > 0
        vals = pd.to_numeric(intervals.loc[mask, feature], errors="coerce").dropna() if mask.any() else pd.Series(dtype=float)
        if len(vals) == 0:
            raw = math.nan
            oriented = math.nan
        elif direction == "asc":
            raw = float(vals.min())
            oriented = -raw
        else:
            raw = float(vals.max())
            oriented = raw
        rows.append(
            {
                "probe_id": probe["probe_id"],
                "feature": feature,
                "ranking_direction": direction,
                "raw_probe_score": raw,
                "oriented_score_higher_is_better": oriented,
                "has_score": not math.isnan(oriented),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    labels = pd.read_csv(LABELS, comment="#")
    intervals = pd.read_csv(INTERVAL_FEATURES)
    diag = pd.read_csv(DIAG_METRICS)
    labels["is_oracle_positive"] = labels["label"].isin(["true_interval", "point_anchor"]).astype(int)

    diag_key = diag.set_index(["feature_group", "feature"])
    score_frames = []
    metric_rows = []
    rank_rows = []
    missing_rows = []
    rng = np.random.default_rng(SEED)

    for group, feature in REPRESENTATIVE_FEATURES:
        if feature not in intervals.columns:
            continue
        drow = diag_key.loc[(group, feature)]
        direction = str(drow["ranking_direction_for_precision_at20"])
        scores = aggregate_probe_scores(labels, intervals, feature, direction)
        scored = labels.merge(scores, on="probe_id", how="left")
        score_frames.append(scored.assign(feature_group=group))

        missing = scored[~scored["has_score"].fillna(False)]
        for _, row in missing.iterrows():
            missing_rows.append(
                {
                    "probe_id": row["probe_id"],
                    "feature_group": group,
                    "feature": feature,
                    "reason": "outside current cheap_signal_v2 feature coverage or no overlapping interval score",
                    "vlm_oracle_label": row["label"],
                }
            )

        eval_df = scored[scored["has_score"].fillna(False)].copy()
        eval_df = eval_df.sort_values(
            ["oriented_score_higher_is_better", "probe_id"],
            ascending=[False, True],
        ).reset_index(drop=True)
        eval_df["rank"] = np.arange(1, len(eval_df) + 1)
        y = eval_df["is_oracle_positive"].to_numpy(int)
        score = eval_df["oriented_score_higher_is_better"].to_numpy(float)
        summary = summarize_metric(y, score, rng)
        metric_rows.append(
            {
                "dataset_source": REFERENCE_SOURCE,
                "analysis_scope": "feature_covered_probes_only",
                "feature_group": group,
                "feature": feature,
                "ranking_direction": direction,
                "n_scored_probes": int(len(eval_df)),
                "n_unscored_probes": int(len(labels) - len(eval_df)),
                "n_oracle_positive_scored": int(y.sum()),
                "n_oracle_negative_scored": int(len(y) - y.sum()),
                "bootstrap_unit": "probe",
                "bootstrap_n": BOOTSTRAP_N,
                "precision_at_20_role": "reference_only_capped_by_positive_count_and_feature_coverage",
                **summary,
            }
        )
        for _, row in eval_df[eval_df["is_oracle_positive"].eq(1)].iterrows():
            rank_rows.append(
                {
                    "dataset_source": REFERENCE_SOURCE,
                    "feature_group": group,
                    "feature": feature,
                    "probe_id": row["probe_id"],
                    "vlm_oracle_label": row["label"],
                    "rank_among_scored_probes": int(row["rank"]),
                    "n_scored_probes": int(len(eval_df)),
                    "hit_at_5": bool(row["rank"] <= 5),
                    "hit_at_10": bool(row["rank"] <= 10),
                    "raw_probe_score": row["raw_probe_score"],
                    "oriented_score_higher_is_better": row["oriented_score_higher_is_better"],
                    "rationale": row.get("rationale", ""),
                }
            )

    metrics = pd.DataFrame(metric_rows)
    ranks = pd.DataFrame(rank_rows)
    missing = pd.DataFrame(missing_rows).drop_duplicates()
    scores = pd.concat(score_frames, ignore_index=True) if score_frames else pd.DataFrame()

    metrics.to_csv(OUT / "probe_signal_metrics.csv", index=False)
    ranks.to_csv(OUT / "probe_positive_rank_cases.csv", index=False)
    missing.to_csv(OUT / "probe_unscored_cases.csv", index=False)
    scores.to_csv(OUT / "probe_signal_scores_long.csv", index=False)

    report = f"""# probe_set_v1 VLM Oracle Signal Evaluation

Reference source: `{REFERENCE_SOURCE}`.

These are VLM-oracle-relative diagnostics, not human-ground-truth metrics. Do not call them true recall or ground truth recall.

## Scope

- Labels: `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`
- Signal table: `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`
- Scored probes: 20/25, because current cheap_signal_v2 feature coverage ends at local 1200s.
- Oracle positives among scored probes: {int(labels[labels['probe_id'].isin(scores[scores['has_score'].fillna(False)]['probe_id'])]['is_oracle_positive'].sum()) if len(scores) else 'NA'}
- Bootstrap: {BOOTSTRAP_N} percentile bootstrap resamples by probe.

## Metric Role

Primary readouts are positive-probe ranks and hit@5/hit@10. AUC and precision@k are auxiliary summaries; precision@20 is reference-only because the positive count and feature coverage cap its useful range.

## Outputs

- `probe_signal_metrics.csv`
- `probe_positive_rank_cases.csv`
- `probe_unscored_cases.csv`
- `probe_signal_scores_long.csv`

## Limitation

Representative features and ranking directions come from the pre-existing 6-event diagnostic design table. This evaluation does not use probe labels to choose features, thresholds, or selectors.
"""
    (OUT / "signal_generalization_report.md").write_text(report, encoding="utf-8")
    print(f"Wrote {OUT}")
    print(metrics[["feature_group", "feature", "auc", "precision_at_5", "positive_coverage_at_5", "positive_coverage_at_10"]].to_string(index=False))


if __name__ == "__main__":
    main()
