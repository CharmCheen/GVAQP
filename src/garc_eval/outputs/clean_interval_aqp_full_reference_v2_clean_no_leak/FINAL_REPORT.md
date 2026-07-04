# FINAL REPORT: clean_interval_aqp_full_reference_v2_clean_no_leak

## 1. Executive Summary

V2 ran end-to-end: yes.

Level 1 implementation status: PASS.

Level 2 research judgement: Negative.

Most important findings:

1. Label alignment is explicit: CILS calibrates `answer_iou_0_3`, while `discovery_positive` is diagnostic only.
2. Lattice oracle upper bound IoU@0.3 is 0.550; budgeted proposal recall@200 upper-bound sort is 0.500.
3. Stress tests now separate active scores; random/noisy/inverted no longer collapse to one identical result.

## 2. What Was Broken In V1

- Label mismatch: fixed by `interval_labels_v2_clean.csv` with discovery and answer labels.
- Proposal upper bound: fixed by dense multiscale, peak multiscale, threshold_merge_v2, blindspot, and boundary refined expansions.
- Stress test: fixed by carrying `active_score` into ranking, calibration, and optimization.
- Stratified sampling: fixed by quota-based `quota_stratified` and `uncertainty_stratified`.

## 3. Data And No-Leakage Protocol

Mini-universe/reference/cheap signals are copied from v1. No VLM, YOLO, or large model inference was rerun.

Feature-only path: `interval_lattice_features_only.csv`.

Label table: `interval_labels_v2_clean.csv`.

Leakage audit:

# Sanity Checks V2

- feature_only_has_no_label_columns: PASS (detail=[])
- calibration_uses_answer_label: PASS (detail=['answer_iou_0_3'])
- sample_count_never_exceeds_budget: PASS (detail=)
- quota_policy_present: PASS (detail=)
- stress_best_noisy_random_not_identical: PASS (detail=[{'stress_test': 'best_proxy', 'recall': 0.048, 'precision': 1.0}, {'stress_test': 'low_density_blindspot_proxy', 'recall': 0.0, 'precision': nan}, {'stress_test': 'noisy_proxy', 'recall': 0.002, 'precision': 0.2}, {'stress_test': 'partial_inverted_proxy', 'recall': 0.0, 'precision': nan}, {'stress_test': 'random_proxy', 'recall': 0.0, 'precision': 0.0}])
- random_not_stably_close_to_best: PASS (detail={'best_proxy': 0.048, 'low_density_blindspot_proxy': 0.0, 'noisy_proxy': 0.002, 'partial_inverted_proxy': 0.0, 'random_proxy': 0.0})
- duration_inflation_control: PASS (detail=0.0)


## 4. Proposal Quality

| method | any_overlap_event_recall | center_hit_event_recall | event_recall_iou_0_3 | event_recall_iou_0_5 | answer_overlap_purity_recall | candidate_count | avg_duration | p95_duration | duplicate_rate | background_duration_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| threshold_merge_v2 | 1 | 1 | 0.5 | 0.3 | 0.5 | 2088 | 18.387 | 72 | 0.106322 | 0.800243 |
| boundary_refined_expansion | 0.75 | 0.7 | 0.35 | 0.2 | 0.3 | 735 | 25.9102 | 40 | 0.25034 | 0.707085 |
| dense_multiscale_windows | 1 | 1 | 0.3 | 0.3 | 0.3 | 3570 | 12.2812 | 32 | 0.0630252 | 0.865546 |
| fixed_window | 1 | 1 | 0.3 | 0.3 | 0.3 | 505 | 15.695 | 30 | 0.0772277 | 0.866535 |
| signal_peak_multiscale | 1 | 1 | 0.3 | 0.3 | 0.3 | 4200 | 15.9714 | 32 | 0.110952 | 0.826434 |
| low_density_blindspot_proposals | 0.7 | 0.65 | 0.1 | 0.1 | 0.15 | 841 | 12.9084 | 24 | 0.0225922 | 0.94134 |

## 5. Calibration

Calibration uses answer labels. Summary:

| budget | policy | brier | ece | auc | positive_rate |
| --- | --- | --- | --- | --- | --- |
| 5 | decision_aware_simple | 0.0917366 | 0.0433952 | 0.503276 | 0 |
| 5 | quota_stratified | 0.126156 | 0.162633 | 0.599533 | 0.128 |
| 5 | top_score | 0.0917231 | 0.0430163 | 0.5 | 0 |
| 5 | uncertainty_stratified | 0.169835 | 0.25532 | 0.583561 | 0.232 |
| 5 | uniform | 0.143819 | 0.205584 | 0.519531 | 0.108 |
| 10 | decision_aware_simple | 0.0890323 | 0.0148184 | 0.524938 | 0 |
| 10 | quota_stratified | 0.127696 | 0.178408 | 0.545345 | 0.107 |
| 10 | top_score | 0.0901452 | 0.0165075 | 0.5 | 0 |
| 10 | uncertainty_stratified | 0.145184 | 0.204996 | 0.555866 | 0.168 |
| 10 | uniform | 0.137074 | 0.192989 | 0.542721 | 0.103 |
| 20 | decision_aware_simple | 0.0890804 | 0.00575819 | 0.523677 | 0.05 |
| 20 | quota_stratified | 0.110981 | 0.130319 | 0.55911 | 0.089 |
| 20 | top_score | 0.0937008 | 0.058537 | 0.488004 | 0 |
| 20 | uncertainty_stratified | 0.124927 | 0.165129 | 0.579485 | 0.132 |
| 20 | uniform | 0.121413 | 0.152981 | 0.568443 | 0.106 |
| 40 | decision_aware_simple | 0.0913235 | 0.0453871 | 0.514336 | 0.125 |
| 40 | quota_stratified | 0.0980384 | 0.0792211 | 0.587674 | 0.09675 |
| 40 | top_score | 0.0910476 | 0.0286385 | 0.501495 | 0.05 |
| 40 | uncertainty_stratified | 0.102341 | 0.0990563 | 0.583973 | 0.12325 |
| 40 | uniform | 0.105712 | 0.107573 | 0.599044 | 0.0975 |
| 80 | decision_aware_simple | 0.0939498 | 0.0602082 | 0.47226 | 0.15 |
| 80 | quota_stratified | 0.0934201 | 0.0628092 | 0.630305 | 0.093125 |
| 80 | top_score | 0.0893108 | 0.015475 | 0.532038 | 0.1 |
| 80 | uncertainty_stratified | 0.0936528 | 0.0453689 | 0.588953 | 0.09 |
| 80 | uniform | 0.103256 | 0.102133 | 0.6191 | 0.098625 |

## 6. Main Results

| method | budget | tau | event_recall_iou_0_3 | event_recall_iou_0_5 | expected_precision | observed_precision | precision_violation_rate | empty_return_rate | avg_returned_duration | p95_returned_duration | duplicate_rate | background_duration_ratio | number_returned |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CILS_full | 5 | 0.5 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 5 | 0.6 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 5 | 0.7 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 5 | 0.8 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 5 | 0.9 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 10 | 0.5 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 10 | 0.6 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 10 | 0.7 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 10 | 0.8 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 10 | 0.9 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 20 | 0.5 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 20 | 0.6 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 20 | 0.7 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 20 | 0.8 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 20 | 0.9 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 40 | 0.5 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 40 | 0.6 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 40 | 0.7 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 40 | 0.8 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 40 | 0.9 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 80 | 0.5 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 80 | 0.6 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 80 | 0.7 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 80 | 0.8 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| CILS_full | 80 | 0.9 | 0 | 0 | 0 | nan | nan | 1 | 0 | 0 | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 5 | 0.5 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 5 | 0.6 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 5 | 0.7 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 5 | 0.8 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 5 | 0.9 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 10 | 0.5 | 0.05 | 0 | 1 | 1 | 0 | 0 | 32 | nan | 0 | 0.25 | 1 |
| arc_style_prune_refine_simplified | 10 | 0.6 | 0.05 | 0 | 1 | 1 | 0 | 0 | 32 | nan | 0 | 0.25 | 1 |
| arc_style_prune_refine_simplified | 10 | 0.7 | 0.05 | 0 | 1 | 1 | 0 | 0 | 32 | nan | 0 | 0.25 | 1 |
| arc_style_prune_refine_simplified | 10 | 0.8 | 0.05 | 0 | 1 | 1 | 0 | 0 | 32 | nan | 0 | 0.25 | 1 |
| arc_style_prune_refine_simplified | 10 | 0.9 | 0.05 | 0 | 1 | 1 | 0 | 0 | 32 | nan | 0 | 0.25 | 1 |
| arc_style_prune_refine_simplified | 20 | 0.5 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 20 | 0.6 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 20 | 0.7 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 20 | 0.8 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 20 | 0.9 | 0 | 0 | 0 | nan | nan | 1 | 0 | nan | 0 | 0 | 0 |
| arc_style_prune_refine_simplified | 40 | 0.5 | 0.05 | 0.05 | 1 | 1 | 0 | 0 | 36 | nan | 0.833333 | 0.18125 | 6 |
| arc_style_prune_refine_simplified | 40 | 0.6 | 0.05 | 0.05 | 1 | 1 | 0 | 0 | 36 | nan | 0.833333 | 0.18125 | 6 |
| arc_style_prune_refine_simplified | 40 | 0.7 | 0.05 | 0.05 | 1 | 1 | 0 | 0 | 36 | nan | 0.833333 | 0.18125 | 6 |
| arc_style_prune_refine_simplified | 40 | 0.8 | 0.05 | 0.05 | 1 | 1 | 0 | 0 | 36 | nan | 0.833333 | 0.18125 | 6 |
| arc_style_prune_refine_simplified | 40 | 0.9 | 0.05 | 0.05 | 1 | 1 | 0 | 0 | 36 | nan | 0.833333 | 0.18125 | 6 |
| arc_style_prune_refine_simplified | 80 | 0.5 | 0.1 | 0.1 | 1 | 1 | 0 | 0 | 24.1818 | nan | 0.818182 | 0.205163 | 11 |
| arc_style_prune_refine_simplified | 80 | 0.6 | 0.1 | 0.1 | 1 | 1 | 0 | 0 | 24.1818 | nan | 0.818182 | 0.205163 | 11 |
| arc_style_prune_refine_simplified | 80 | 0.7 | 0.1 | 0.1 | 1 | 1 | 0 | 0 | 24.1818 | nan | 0.818182 | 0.205163 | 11 |
| arc_style_prune_refine_simplified | 80 | 0.8 | 0.1 | 0.1 | 1 | 1 | 0 | 0 | 24.1818 | nan | 0.818182 | 0.205163 | 11 |
| arc_style_prune_refine_simplified | 80 | 0.9 | 0.1 | 0.1 | 1 | 1 | 0 | 0 | 24.1818 | nan | 0.818182 | 0.205163 | 11 |
| lattice_oracle_upper_bound | 5 | 0.5 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.4 | 0 | 5 |
| lattice_oracle_upper_bound | 5 | 0.6 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.4 | 0 | 5 |
| lattice_oracle_upper_bound | 5 | 0.7 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.4 | 0 | 5 |
| lattice_oracle_upper_bound | 5 | 0.8 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.4 | 0 | 5 |
| lattice_oracle_upper_bound | 5 | 0.9 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.4 | 0 | 5 |
| lattice_oracle_upper_bound | 10 | 0.5 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.7 | 0 | 10 |
| lattice_oracle_upper_bound | 10 | 0.6 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.7 | 0 | 10 |
| lattice_oracle_upper_bound | 10 | 0.7 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.7 | 0 | 10 |
| lattice_oracle_upper_bound | 10 | 0.8 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.7 | 0 | 10 |
| lattice_oracle_upper_bound | 10 | 0.9 | 0.15 | 0 | 1 | 1 | 0 | 0 | 2 | nan | 0.7 | 0 | 10 |
| lattice_oracle_upper_bound | 20 | 0.5 | 0.35 | 0 | 1 | 1 | 0 | 0 | 2.5 | nan | 0.65 | 0 | 20 |
| lattice_oracle_upper_bound | 20 | 0.6 | 0.35 | 0 | 1 | 1 | 0 | 0 | 2.5 | nan | 0.65 | 0 | 20 |
| lattice_oracle_upper_bound | 20 | 0.7 | 0.35 | 0 | 1 | 1 | 0 | 0 | 2.5 | nan | 0.65 | 0 | 20 |
| lattice_oracle_upper_bound | 20 | 0.8 | 0.35 | 0 | 1 | 1 | 0 | 0 | 2.5 | nan | 0.65 | 0 | 20 |
| lattice_oracle_upper_bound | 20 | 0.9 | 0.35 | 0 | 1 | 1 | 0 | 0 | 2.5 | nan | 0.65 | 0 | 20 |
| lattice_oracle_upper_bound | 40 | 0.5 | 0.4 | 0 | 1 | 1 | 0 | 0 | 3.25 | nan | 0.8 | 0 | 40 |
| lattice_oracle_upper_bound | 40 | 0.6 | 0.4 | 0 | 1 | 1 | 0 | 0 | 3.25 | nan | 0.8 | 0 | 40 |
| lattice_oracle_upper_bound | 40 | 0.7 | 0.4 | 0 | 1 | 1 | 0 | 0 | 3.25 | nan | 0.8 | 0 | 40 |
| lattice_oracle_upper_bound | 40 | 0.8 | 0.4 | 0 | 1 | 1 | 0 | 0 | 3.25 | nan | 0.8 | 0 | 40 |
| lattice_oracle_upper_bound | 40 | 0.9 | 0.4 | 0 | 1 | 1 | 0 | 0 | 3.25 | nan | 0.8 | 0 | 40 |
| lattice_oracle_upper_bound | 80 | 0.5 | 0.4 | 0.15 | 1 | 1 | 0 | 0 | 3.925 | nan | 0.9 | 0.00416667 | 80 |
| lattice_oracle_upper_bound | 80 | 0.6 | 0.4 | 0.15 | 1 | 1 | 0 | 0 | 3.925 | nan | 0.9 | 0.00416667 | 80 |
| lattice_oracle_upper_bound | 80 | 0.7 | 0.4 | 0.15 | 1 | 1 | 0 | 0 | 3.925 | nan | 0.9 | 0.00416667 | 80 |
| lattice_oracle_upper_bound | 80 | 0.8 | 0.4 | 0.15 | 1 | 1 | 0 | 0 | 3.925 | nan | 0.9 | 0.00416667 | 80 |
| lattice_oracle_upper_bound | 80 | 0.9 | 0.4 | 0.15 | 1 | 1 | 0 | 0 | 3.925 | nan | 0.9 | 0.00416667 | 80 |
| threshold_merge_topk | 5 | 0.5 | 0 | 0 | 0 | 0 | 1 | 0 | 3.6 | nan | 0 | 1 | 5 |
| threshold_merge_topk | 5 | 0.6 | 0 | 0 | 0 | 0 | 1 | 0 | 3.6 | nan | 0 | 1 | 5 |
| threshold_merge_topk | 5 | 0.7 | 0 | 0 | 0 | 0 | 1 | 0 | 3.6 | nan | 0 | 1 | 5 |
| threshold_merge_topk | 5 | 0.8 | 0 | 0 | 0 | 0 | 1 | 0 | 3.6 | nan | 0 | 1 | 5 |
| threshold_merge_topk | 5 | 0.9 | 0 | 0 | 0 | 0 | 1 | 0 | 3.6 | nan | 0 | 1 | 5 |

Improvement counts:

| baseline | improved_budget_points_tau_0_6_0_7 |
| --- | --- |
| threshold_merge_topk | 0 |
| arc_style_prune_refine_simplified | 0 |

## 7. Stress Tests

Stress/ablation diagnostic trials per cell: 20. Main, baseline, and calibration trials per cell: 100.

| stress_test | recall | precision |
| --- | --- | --- |
| best_proxy | 0.048 | 1 |
| low_density_blindspot_proxy | 0 | nan |
| noisy_proxy | 0.002 | 0.2 |
| partial_inverted_proxy | 0 | nan |
| random_proxy | 0 | 0 |

## 8. Ablation

| ablation | recall | precision | returned |
| --- | --- | --- | --- |
| CILS_full | 0 | nan | 0 |
| fused_signal | 0 | nan | 0 |
| no_boundary_quality | 0 | nan | 0 |
| no_calibration_raw_score | 0.05 | 1 | 1 |
| no_duration_penalty | 0 | nan | 0 |
| no_lattice_fixed_windows | 0.002 | 0.5 | 0.08 |
| no_overlap_control | 0 | nan | 0 |
| primary_signal_only | 0 | nan | 0 |

## 9. Research Interpretation

Current bottleneck: calibration/precision and answer-compatible interval ranking, not proposal coverage alone.

CILS research value: shift effort to proposal/reference or cheap-signal quality before more CILS.

The v2 lattice improves the candidate-space question, but answer-level precision remains hard under the current cheap signals and simple beta-bin calibration.

## 10. Next Actions

1. Add a calibration split that reserves budget for answer-quality validation rather than only top-score probing.
2. Improve answer-compatible boundary scoring, especially for short VLM events where IoU is brittle.
3. Test a second mini-universe only after the calibration violation rate improves on this one.
