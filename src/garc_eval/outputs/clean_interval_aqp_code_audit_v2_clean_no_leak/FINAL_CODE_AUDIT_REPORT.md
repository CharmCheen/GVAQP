# Final Code Audit Report

## Executive Summary

- Overall verdict: **WARNING**
- v2 results are trustworthy? **yes**
- BLOCKER present: **no**
- v2 Level 2 Negative credible? **yes**
- CILS max recall 0 credible? **yes**
- Lattice upper bound 0.55 credible? **yes** (`recomputed=0.550`)
- Reference mismatch conclusion still holds? **yes: independent metrics support limited answer-compatible proposal coverage under clean no-leak artifacts.**

## Critical Findings

| severity | area | finding | evidence | impact |
| --- | --- | --- | --- | --- |
| INFO | Artifact inventory | At least one CSV is empty. | selected_intervals_by_trial_v2_clean.csv |  |
| WARNING | Baseline fairness | oracle_confirmed_only uses answer labels during replay/confirmation and must be interpreted as budgeted oracle-replay, not a cheap baseline. | pipeline static audit |  |
| WARNING | Baseline fairness | arc_style_prune_refine_simplified uses answer labels during replay/confirmation and must be interpreted as budgeted oracle-replay, not a cheap baseline. | pipeline static audit |  |
| WARNING | Baseline fairness | arc_plus_uniform_outside_audit_simplified uses answer labels during replay/confirmation and must be interpreted as budgeted oracle-replay, not a cheap baseline. | pipeline static audit |  |

## Artifact Inventory

See `artifact_inventory.md` and `artifact_inventory.csv`.

## Label Leakage Audit

See `label_leakage_audit.md`. The clean feature-only lattice is audited against forbidden reference-derived fields.

## Label Definition And Alignment Audit

See `label_definition_audit.md` and `label_consistency_checks.csv`. Calibration uses `answer_iou_0_3`; independent temporal IoU labels match the v2 label table.

## Metric Recompute Audit

See `metric_recompute_audit.md`, `metric_diff.csv`, and `per_event_recomputed_best_candidate.csv`. Independent recomputation supports the reported lattice upper-bound scale and the empty CILS selected-set result.

## Oracle Budget And Replay Audit

See `oracle_budget_audit.md` and `oracle_budget_usage.csv`. Calibration replay respects the oracle budget.

## Calibration Audit

See `calibration_audit.md` and `calibration_recompute.csv`. Empty return sets are separated from precision satisfaction; top-score calibration keeps CILS probabilities below the main tau grid.

## CILS Selector Audit

See `cils_selector_audit.md`, `cils_candidate_score_distribution.csv`, and `cils_rejection_reasons.csv`. The empty return is explained by precision-threshold rejection under low calibrated `p_answer`, not by a recomputed metric bug.

## Baseline Fairness Audit

See `baseline_fairness_audit.md` and `baseline_input_comparison.csv`. Upper bounds are named as upper bounds; simplified oracle-replay baselines need careful wording.

## Stress Test Audit

See `stress_test_audit.md`, `stress_score_distribution.csv`, and `stress_result_diff.csv`. Stress variants differ in score and result distributions.

## Synthetic Unit Tests

See `unit_test_results.md` and `synthetic_test_cases.py`.

## Impact On Research Conclusions

The clean v2 Negative is **trustworthy as a clean no-leak artifact-level Level 2 Negative**. The CILS zero-recall behavior appears real for this artifact and is explained by calibrated precision-threshold rejection. The reference mismatch / limited answer-compatible lattice coverage signal is directionally supported by independent metrics.

Next experiment gate for `reference_duration_stratified_eval_v1`: **yes, with the documented warnings**.

## Recommended Next Actions

1. Preserve the whitelist-only feature schema in future v2 variants.
2. Treat CILS zero recall as a clean calibration/selector failure signal, not a perception benchmark claim.
3. Proceed to `reference_duration_stratified_eval_v1` only if this audit has no BLOCKER.
