# Final Code Audit Report

## Executive Summary

- Overall verdict: **BLOCKER**
- v2 results are trustworthy? **no**
- BLOCKER present: **yes**
- v2 Level 2 Negative credible? **no**
- CILS max recall 0 credible? **yes as an artifact behavior, no as a final research conclusion**
- Lattice upper bound 0.55 credible? **yes** (`recomputed=0.550`)
- Reference mismatch conclusion still holds? **partial: metric recomputation supports limited answer-compatible proposal coverage, but the leakage BLOCKER prevents treating v2 as clean evidence.**

## Critical Findings

| severity | area | finding | evidence | impact |
| --- | --- | --- | --- | --- |
| INFO | Artifact inventory | At least one CSV is empty. | selected_intervals_by_trial_v2.csv |  |
| BLOCKER | Label leakage | features-only lattice contains reference-derived fields. | any_overlap, best_iou, center_hit, duration_inflation, event_overlap_ratio, interval_purity | Optimization input can carry held-out answer/evaluation information. |
| FAIL | Calibration | Recomputed Brier scores differ from v2. | \| budget \| seed \| policy \| sample_positive_rate_x \| mean_p_answer_x \| min_p_answer \| max_p_answer \| brier_recomputed \| ece_5bin_recomputed \| answer_label \| num_oracle_calls \| sample_count_le_budget \| sample_positive_rate_y \| mean_p_answer_y \| brier \| ece \| auc \| ap \| brier_diff \| \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| --- \| \| 5 \| 0 \| decision_aware_simple \| 0 \| 0.14309 \| 0.142857 \| 0.166667 \| 0.0916796 \| 0.0432496 \| answer_iou_0_3 \| 5 \| True \| 0 \| 0.143236 \| 0.0917366 \| 0.0433952 \| 0.503276 \| 0.0870071 \| 5.70265e-05 \| \| 5 \| 0 \| quota_stratified \| 0.4 \| 0.448761 \| 0.2 \| 0.75 \| 0.222729 \| 0.34892 \| answer_iou_0_3 \| 5 \| True \| 0.4 \| 0.447144 \| 0.222019 \| 0.347304 \| 0.654705 \| 0.165206 \| 0.000710696 \| \| 5 \| 1 \| decision_aware_simple \| 0 \| 0.14309 \| 0.142857 \| 0.166667 \| 0.0916796 \| 0.0432496 \| answer_iou_0_3 \| 5 \| True \| 0 \| 0.143236 \| 0.0917366 \| 0.0433952 \| 0.503276 \| 0.0870071 \| 5.70265e-05 \| \| 5 \| 1 \| quota_stratified \| 0 \| 0.176957 \| 0.142857 \| 0.25 \| 0.0960884 \| 0.0771158 \| answer_iou_0_3 \| 5 \| True \| 0 \| 0.175717 \| 0.0955389 \| 0.0758762 \| 0.546211 \| 0.151641 \| 0.00054946 \| \| 5 \| 1 \| uncertainty_stratified \| 0 \| 0.231251 \| 0.142857 \| 0.333333 \| 0.106949 \| 0.13141 \| answer_iou_0_3 \| 5 \| True \| 0 \| 0.230468 \| 0.106756 \| 0.130627 \| 0.649335 \| 0.162039 \| 0.000193274 \| |  |
| WARNING | Baseline fairness | oracle_confirmed_only uses answer labels during replay/confirmation and must be interpreted as budgeted oracle-replay, not a cheap baseline. | pipeline static audit |  |
| WARNING | Baseline fairness | arc_style_prune_refine_simplified uses answer labels during replay/confirmation and must be interpreted as budgeted oracle-replay, not a cheap baseline. | pipeline static audit |  |
| WARNING | Baseline fairness | arc_plus_uniform_outside_audit_simplified uses answer labels during replay/confirmation and must be interpreted as budgeted oracle-replay, not a cheap baseline. | pipeline static audit |  |

## Artifact Inventory

See `artifact_inventory.md` and `artifact_inventory.csv`.

## Label Leakage Audit

See `label_leakage_audit.md`. The decisive finding is that the features-only lattice contains reference-derived fields.

## Label Definition And Alignment Audit

See `label_definition_audit.md` and `label_consistency_checks.csv`. Calibration uses `answer_iou_0_3`; independent temporal IoU labels match the v2 label table.

## Metric Recompute Audit

See `metric_recompute_audit.md`, `metric_diff.csv`, and `per_event_recomputed_best_candidate.csv`. Independent recomputation supports the reported lattice upper-bound scale and the empty CILS selected-set result.

## Oracle Budget And Replay Audit

See `oracle_budget_audit.md` and `oracle_budget_usage.csv`. Calibration replay respects the oracle budget.

## Calibration Audit

See `calibration_audit.md` and `calibration_recompute.csv`. Empty return sets are counted as precision violations; top-score calibration keeps CILS probabilities below the main tau grid.

## CILS Selector Audit

See `cils_selector_audit.md`, `cils_candidate_score_distribution.csv`, and `cils_rejection_reasons.csv`. The empty return is explained by precision-threshold rejection under low calibrated `p_answer`, not by a recomputed metric bug.

## Baseline Fairness Audit

See `baseline_fairness_audit.md` and `baseline_input_comparison.csv`. Upper bounds are named as upper bounds; simplified oracle-replay baselines need careful wording.

## Stress Test Audit

See `stress_test_audit.md`, `stress_score_distribution.csv`, and `stress_result_diff.csv`. Stress variants differ in score and result distributions.

## Synthetic Unit Tests

See `unit_test_results.md` and `synthetic_test_cases.py`.

## Impact On Research Conclusions

The v2 Negative should **not** be treated as a clean Level 2 research conclusion until the feature-only leakage is fixed and the audit is rerun. The CILS zero-recall behavior appears real for the current artifact, but it is only an artifact-level selector/calibration failure. The reference mismatch / limited answer-compatible lattice coverage signal is directionally supported by independent metrics, but remains contaminated by the trust-boundary violation.

Do **not** enter `reference_duration_stratified_eval_v1` as a research-valid next experiment from this v2 state. First regenerate a truly label-free features-only lattice, rerun v2, then rerun this audit.

## Recommended Next Actions

1. Fix v2 artifact generation so `interval_lattice_features_only.csv` is produced before label joins or from an allowlisted feature schema.
2. Rerun v2 and rerun `bash src/garc_eval/experiments/clean_interval_aqp_code_audit_v1/run_audit.sh`.
3. Only if the rerun has no BLOCKER, proceed to `reference_duration_stratified_eval_v1`.
