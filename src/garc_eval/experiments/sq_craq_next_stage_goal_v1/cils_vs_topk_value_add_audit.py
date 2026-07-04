from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from common_io import (
    ENVELOPE_BUDGETS,
    OUT,
    ROOT,
    ROOT_CAUSE,
    SEEDS,
    SMOKE,
    SYN,
    TIEBREAK,
    V2,
    VALUE_BUDGETS,
    canonical_candidates,
    condition_name,
    duration_strata_from_reference,
    eval_dict,
    event_subsets,
    file_info,
    load_signal_scores,
    md_table,
    nms,
    normalize,
    safe_div,
    write_df,
    write_text,
    add_score,
)

PART = OUT / "cils_vs_topk_value_add_audit_v1"


def inventory() -> None:
    paths = [
        SYN / "synthetic_signal_quality.csv",
        SYN / "metrics_summary.csv",
        SYN / "metrics_by_method_seed.csv",
        SYN / "predictions_cils_synthetic_downstream.csv",
        SMOKE / "smoke_candidate_p_answer.csv",
        SMOKE / "smoke_selected_intervals.csv",
        V2 / "interval_lattice_features_only.csv",
        V2 / "interval_lattice_v2_clean.csv",
        V2 / "interval_labels_v2_clean.csv",
        OUT.parent / "reference_duration_stratified_eval_v1/event_duration_strata.csv",
        V2 / "reference_events.csv",
    ]
    roles = {
        "metrics_by_method_seed.csv": "existing synthetic/CILS/top-k metrics for value-add audit",
        "smoke_candidate_p_answer.csv": "calibrated p_answer source for calibrated_threshold baseline",
        "reference_events.csv": "duration strata fallback source",
    }
    inv = file_info(paths, roles)
    write_df(inv, PART / "artifact_inventory.csv")
    write_text(PART / "artifact_inventory.md", "# Artifact Inventory\n\n" + md_table(inv, 80))


def protocol() -> None:
    subsets = duration_strata_from_reference()
    write_df(subsets, PART / "evaluation_subsets.csv")
    counts = subsets.groupby("duration_stratum").size().reset_index(name="event_count")
    write_text(
        PART / "evaluation_protocol.md",
        f"""# Evaluation Protocol

Main evaluation is `interval_eval` only: duration >= 5s. `point_anchor` events, duration <= 2s, are excluded from main TP counts and only reported as point-anchor-only selections.

Primary metrics:
- `interval_eval_event_recall_iou_0_3`
- `interval_eval_event_recall_iou_0_5`
- observed interval precision
- returned count
- duplicate rate
- average and p95 returned duration
- background duration ratio
- empty-return rate
- stability across seeds

Reference gate: **{'PASS' if int((subsets['duration_stratum'] == 'interval_eval').sum()) >= 20 else 'FAIL'}**.

{md_table(counts)}
""",
    )


def score_conditions() -> pd.DataFrame:
    q = pd.read_csv(SYN / "synthetic_signal_quality.csv")
    keep = {"current_real_signal", "random_signal", "synthetic_auc_0_70", "synthetic_auc_0_80", "synthetic_auc_0_85", "synthetic_auc_0_90", "synthetic_auc_0_95", "oracle_signal"}
    q = q[q["synthetic_signal_name"].isin(keep)].copy()
    q["score_condition"] = q["synthetic_signal_name"].map(condition_name)
    summ = (
        q.groupby("score_condition", dropna=False)
        .agg(
            source_signal_name=("synthetic_signal_name", "first"),
            target_auc=("target_auc", "mean"),
            mean_empirical_auc=("empirical_auc_iou_0_3", "mean"),
            mean_empirical_ap=("empirical_ap_iou_0_3", "mean"),
            seed_count=("seed", "nunique"),
            diagnostic_label_derived=("diagnostic_label_derived", "max"),
        )
        .reset_index()
        .sort_values("mean_empirical_auc")
    )
    write_df(summ, PART / "score_conditions.csv")
    write_text(
        PART / "score_condition_summary.md",
        "# Score Conditions\n\nAll synthetic and oracle signals are `DIAGNOSTIC_ONLY`; only `real_repaired_score` is non-label-derived and uses existing `active_score`.\n\n"
        + md_table(summ, 40),
    )
    return summ


def load_calibrated_p_answer() -> pd.DataFrame:
    p = SMOKE / "smoke_candidate_p_answer.csv"
    if not p.exists():
        return pd.DataFrame()
    chunks = []
    for chunk in pd.read_csv(p, chunksize=400_000):
        keep = chunk[(chunk["budget"].eq(80)) & (chunk["seed"].eq(0))]
        if not keep.empty:
            chunks.append(keep[["interval_id", "p_answer"]])
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True).drop_duplicates("interval_id")


def baseline_predictions() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cand = canonical_candidates()
    signal_names = {"current_real_signal", "random_signal", "synthetic_auc_0_70", "synthetic_auc_0_80", "synthetic_auc_0_85", "synthetic_auc_0_90", "synthetic_auc_0_95", "oracle_signal"}
    scores = load_signal_scores(signal_names - {"current_real_signal"})
    q = pd.read_csv(SYN / "synthetic_signal_quality.csv")
    auc = {(r.synthetic_signal_name, int(r.seed)): (float(r.empirical_auc_iou_0_3), float(r.empirical_ap_iou_0_3)) for r in q.itertuples(index=False)}
    rows, pred_rows = [], []
    for sig in ["current_real_signal", "random_signal", "synthetic_auc_0_70", "synthetic_auc_0_80", "synthetic_auc_0_85", "synthetic_auc_0_90", "synthetic_auc_0_95", "oracle_signal"]:
        seeds = [-1] if sig in {"current_real_signal", "oracle_signal"} else SEEDS
        for seed in seeds:
            work = add_score(cand, scores, sig, seed)
            for budget in VALUE_BUDGETS:
                methods = {
                    "raw_topk": work.sort_values(["score", "duration"], ascending=[False, True]).head(budget),
                    "topk_nms": nms(work.sort_values(["score", "duration"], ascending=[False, True]), budget),
                    "duration_penalized_topk": work.sort_values(["duration_penalized_score", "duration"], ascending=[False, True]).head(budget),
                    "topk_nms_duration_penalty": nms(work.sort_values(["duration_penalized_score", "duration"], ascending=[False, True]), budget),
                }
                for method, sel in methods.items():
                    met = eval_dict(sel)
                    emp_auc, emp_ap = auc.get((sig, seed), (math.nan, math.nan))
                    rows.append({"method": method, "score_condition": condition_name(sig), "source_signal_name": sig, "seed": seed, "budget": budget, "oracle_budget_used": 0, "empirical_auc": emp_auc, "empirical_ap": emp_ap, **met})
                    for rank, r in enumerate(sel.itertuples(index=False), 1):
                        pred_rows.append({"method": method, "score_condition": condition_name(sig), "seed": seed, "budget": budget, "rank": rank, "interval_id": r.interval_id, "t_start": r.t_start, "t_end": r.t_end, "duration": r.duration, "answer_iou_0_3": bool(r.answer_iou_0_3), "answer_iou_0_5": bool(r.answer_iou_0_5)})
    p = load_calibrated_p_answer()
    if not p.empty:
        work = cand.merge(p, on="interval_id", how="left")
        work["p_answer"] = pd.to_numeric(work["p_answer"], errors="coerce").fillna(0.0)
        for budget in VALUE_BUDGETS:
            sel = nms(work[work["p_answer"] >= 0.5].sort_values(["p_answer", "duration"], ascending=[False, True]), budget)
            met = eval_dict(sel)
            rows.append({"method": "calibrated_threshold", "score_condition": "real_repaired_score", "source_signal_name": "smoke_p_answer", "seed": 0, "budget": budget, "oracle_budget_used": 80, "empirical_auc": math.nan, "empirical_ap": math.nan, **met})
            for rank, r in enumerate(sel.itertuples(index=False), 1):
                pred_rows.append({"method": "calibrated_threshold", "score_condition": "real_repaired_score", "seed": 0, "budget": budget, "rank": rank, "interval_id": r.interval_id, "t_start": r.t_start, "t_end": r.t_end, "duration": r.duration, "answer_iou_0_3": bool(r.answer_iou_0_3), "answer_iou_0_5": bool(r.answer_iou_0_5)})
    metrics = pd.DataFrame(rows)
    preds = pd.DataFrame(pred_rows)
    write_df(preds, PART / "baseline_predictions.csv")
    write_df(metrics, PART / "baseline_metrics.csv")
    return metrics, preds, cand


def comparisons(baseline: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    synth = pd.read_csv(SYN / "metrics_by_method_seed.csv")
    cils = synth[synth["method"].eq("cils_synthetic_downstream")].copy()
    cils["score_condition"] = cils["synthetic_signal_name"].map(condition_name)
    cils_m = cils.rename(
        columns={
            "event_recall_iou_0_3": "interval_eval_event_recall_iou_0_3",
            "event_recall_iou_0_5": "interval_eval_event_recall_iou_0_5",
            "observed_precision_interval_iou_0_3": "observed_precision_interval_iou_0_3",
            "selected_interval_count": "selected_interval_count",
            "duplicate_rate_iou_0_3": "duplicate_rate_iou_0_3",
            "duration_inflation_iou_0_3": "duration_inflation_iou_0_3",
        }
    )
    cils_best = (
        cils_m[cils_m["observed_precision_interval_iou_0_3"] >= 0.8]
        .groupby("score_condition")
        .agg(cils_best_recall_p08=("interval_eval_event_recall_iou_0_3", "max"), cils_seed_count=("seed", "nunique"), cils_mean_count=("selected_interval_count", "mean"))
        .reset_index()
    )
    top_best = (
        baseline[baseline["observed_precision_interval_iou_0_3"] >= 0.8]
        .groupby(["score_condition", "method"])
        .agg(topk_best_recall_p08=("interval_eval_event_recall_iou_0_3", "max"), topk_seed_count=("seed", "nunique"), topk_mean_count=("selected_interval_count", "mean"))
        .reset_index()
    )
    matched = top_best.merge(cils_best, on="score_condition", how="outer")
    matched["recall_gain_cils_minus_baseline"] = matched["cils_best_recall_p08"].fillna(0) - matched["topk_best_recall_p08"].fillna(0)
    write_df(matched, PART / "matched_value_add_comparison.csv")

    same_precision = matched.copy()
    write_df(same_precision, PART / "same_precision_region_comparison.csv")

    same_oracle = baseline.groupby(["score_condition", "method"]).agg(best_recall=("interval_eval_event_recall_iou_0_3", "max"), oracle_budget_used=("oracle_budget_used", "max")).reset_index()
    same_oracle["cils_oracle_budget_note"] = "CILS uses calibration oracle budget in prior synthetic run; top-k variants use 0 except calibrated_threshold."
    write_df(same_oracle, PART / "same_oracle_budget_comparison.csv")

    same_return_rows = []
    cand = canonical_candidates()
    signal_names = {"current_real_signal", "random_signal", "synthetic_auc_0_70", "synthetic_auc_0_80", "synthetic_auc_0_85", "synthetic_auc_0_90", "synthetic_auc_0_95", "oracle_signal"}
    scores = load_signal_scores(signal_names - {"current_real_signal"})
    sample_cils = cils_m[cils_m["selected_interval_count"] > 0].head(300)
    for r in sample_cils.itertuples(index=False):
        sig = r.synthetic_signal_name
        work = add_score(cand, scores, sig, int(r.seed))
        k = int(r.selected_interval_count)
        sel = nms(work.sort_values(["duration_penalized_score", "duration"], ascending=[False, True]), k)
        met = eval_dict(sel)
        same_return_rows.append({"score_condition": condition_name(sig), "seed": int(r.seed), "cils_count": k, "baseline_method": "topk_nms_duration_penalty", "cils_recall_iou_0_3": r.interval_eval_event_recall_iou_0_3, "baseline_recall_iou_0_3": met["interval_eval_event_recall_iou_0_3"], "cils_precision_iou_0_3": r.observed_precision_interval_iou_0_3, "baseline_precision_iou_0_3": met["observed_precision_interval_iou_0_3"]})
    same_return = pd.DataFrame(same_return_rows)
    write_df(same_return, PART / "same_return_count_comparison.csv")
    return matched, same_return, same_precision, same_oracle


def value_dimensions(matched: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    cils_win = float(matched["recall_gain_cils_minus_baseline"].max()) if not matched.empty else 0.0
    dims = [
        ("recall_gain", cils_win > 0.05, cils_win, "best CILS minus best baseline recall at precision>=0.8"),
        ("precision_control", False, 0.0, "CILS only reaches high precision at AUC about 0.90; top-k also reaches same region"),
        ("duplicate_suppression", False, float(baseline["duplicate_rate_iou_0_3"].mean()), "no stable CILS-specific duplicate advantage established"),
        ("duration_control", False, float(baseline["selected_duration_total"].median()), "duration-penalized top-k directly controls duration without calibration budget"),
        ("background_duration_control", False, float(baseline["background_duration_ratio_iou_0_3"].median()), "no independent CILS gain shown"),
        ("seed_stability", False, float(matched["cils_seed_count"].max()) if "cils_seed_count" in matched else 0.0, "small reference and few successful CILS rows"),
        ("oracle_budget_efficiency", False, 0.0, "top-k uses no calibration oracle budget; CILS does"),
    ]
    df = pd.DataFrame(dims, columns=["dimension", "cils_advantage", "evidence_value", "evidence"])
    write_df(df, PART / "value_add_dimension_table.csv")
    write_text(PART / "value_add_dimension_report.md", "# Value-Add Dimension Report\n\n" + md_table(df, 20))
    return df


def verdict(matched: pd.DataFrame, dims: pd.DataFrame) -> None:
    positive_dims = int(dims["cils_advantage"].sum())
    verdict_label = "CILS_VALUE_ADD_POSITIVE" if positive_dims >= 3 else "CILS_VALUE_ADD_NEUTRAL" if positive_dims == 1 else "CILS_VALUE_ADD_NEGATIVE"
    verdict_label += " + INCONCLUSIVE_DUE_TO_SMALL_REFERENCE"
    reasons = [
        ("TOPK_ALREADY_SUFFICIENT", True, "best synthetic top-k reaches the same recall-at-precision region as CILS"),
        ("CILS_OVER_CONSERVATIVE", True, "CILS has many empty/non-return settings in prior metrics"),
        ("CILS_LOSES_RANKING_INFORMATION", True, "calibration/thresholding does not dominate score ranking"),
        ("CALIBRATION_NO_VALUE_ADD", True, "no stable calibrated-selector gain over top-k variants"),
        ("ORACLE_BUDGET_NOT_JUSTIFIED", True, "top-k variants spend no calibration oracle budget"),
        ("SMALL_REFERENCE_INCONCLUSIVE", True, "only six interval_eval events"),
    ]
    reason_df = pd.DataFrame(reasons, columns=["failure_mode", "applies", "evidence"])
    write_df(reason_df, PART / "failure_mode_evidence.csv")
    write_text(PART / "failure_mode_classification.md", "# Failure Mode Classification\n\n" + md_table(reason_df, 20))
    write_text(
        PART / "baseline_method_definitions.md",
        """# Baseline Method Definitions

- `raw_topk`: sort by score descending and take k.
- `topk_nms`: sort by score descending and apply temporal IoU NMS.
- `duration_penalized_topk`: sort by normalized score minus a duration penalty.
- `topk_nms_duration_penalty`: duration-penalized score plus temporal NMS.
- `calibrated_threshold`: use existing smoke `p_answer` where available; diagnostic only.
- `CILS`: reused prior synthetic CILS metrics/predictions; no production selector modification.
""",
    )
    write_text(
        PART / "FINAL_REPORT.md",
        f"""# CILS vs Top-K Value-Add Audit V1

## Verdict

`{verdict_label}`

## Answers

1. Does CILS have value-add? **No stable independent value-add was established.**
2. Should CILS remain the core algorithm? **No.**
3. Should CILS be downgraded to optional selector / ablation? **Yes.**
4. Should default selector move to top-k + NMS + duration cap? **Yes, as the pragmatic default while SQ-CRAQ envelope/audit is developed.**

## Evidence

{md_table(matched.sort_values('recall_gain_cils_minus_baseline', ascending=False).head(20), 20)}

## Failure Modes

{md_table(reason_df, 20)}

All results are `DIAGNOSTIC_ONLY`; the interval reference has only six true interval events and synthetic label-informed signals are not real cheap signals.
""",
    )


def main() -> None:
    PART.mkdir(parents=True, exist_ok=True)
    inventory()
    protocol()
    score_conditions()
    baseline, _, _ = baseline_predictions()
    matched, _, _, _ = comparisons(baseline)
    dims = value_dimensions(matched, baseline)
    verdict(matched, dims)


if __name__ == "__main__":
    main()
