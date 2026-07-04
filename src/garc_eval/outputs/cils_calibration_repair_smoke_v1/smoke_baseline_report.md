# Smoke Baseline Report

Primary comparison scope: interval_eval events only.

| method | pilot_policy | calibration_model | budget | tau | interval_recall | interval_recall_iou_0_5 | precision | returned | avg_duration | duplicate_rate | empty_return_rate | expected_precision | diagnostic_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oracle_confirmed_only | baseline_or_diagnostic | none | 80 | nan | 0.166667 | 0.166667 | 1 | 8 | 12.25 | 0.875 | 0 | nan |  |
| oracle_confirmed_only | baseline_or_diagnostic | none | 40 | nan | 0.166667 | 0.166667 | 1 | 2 | 8 | 0.5 | 0 | nan |  |
| oracle_p_answer_counterfactual | baseline_or_diagnostic | oracle_p_answer | 5 | 0.5 | 0.166667 | 0 | 1 | 1 | 32 | 0 | 0 | 1 | DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT |
| oracle_p_answer_counterfactual | baseline_or_diagnostic | oracle_p_answer | 10 | 0.5 | 0.166667 | 0 | 1 | 1 | 32 | 0 | 0 | 1 | DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT |
| oracle_p_answer_counterfactual | baseline_or_diagnostic | oracle_p_answer | 20 | 0.5 | 0.166667 | 0 | 1 | 1 | 32 | 0 | 0 | 1 | DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT |
| oracle_p_answer_counterfactual | baseline_or_diagnostic | oracle_p_answer | 40 | 0.5 | 0.166667 | 0 | 1 | 1 | 32 | 0 | 0 | 1 | DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT |
| oracle_p_answer_counterfactual | baseline_or_diagnostic | oracle_p_answer | 80 | 0.5 | 0.166667 | 0 | 1 | 1 | 32 | 0 | 0 | 1 | DIAGNOSTIC_ONLY_NOT_ALGORITHM_RESULT |
| smoke_repaired_cils | answer_quality_proxy_top | beta_bin_strata_lower | 80 | 0.5 | 0.166667 | 0 | 1 | 1 | 16 | 0 | 0 | nan | nan |
| smoke_repaired_cils | answer_quality_proxy_top | beta_bin_strata_lower | 80 | 0.6 | 0.166667 | 0 | 1 | 1 | 16 | 0 | 0 | nan | nan |
| lattice_oracle_upper_bound | baseline_or_diagnostic | none | 5 | nan | 0 | 0 | 1 | 1 | 2 | 0 | 0 | nan |  |
| lattice_oracle_upper_bound | baseline_or_diagnostic | none | 10 | nan | 0 | 0 | 1 | 1 | 2 | 0 | 0 | nan |  |
| lattice_oracle_upper_bound | baseline_or_diagnostic | none | 20 | nan | 0 | 0 | 1 | 1 | 2 | 0 | 0 | nan |  |
| lattice_oracle_upper_bound | baseline_or_diagnostic | none | 40 | nan | 0 | 0 | 1 | 1 | 2 | 0 | 0 | nan |  |
| lattice_oracle_upper_bound | baseline_or_diagnostic | none | 80 | nan | 0 | 0 | 1 | 1 | 2 | 0 | 0 | nan |  |
| threshold_merge_topk | baseline_or_diagnostic | none | 5 | nan | 0 | 0 | 0 | 1 | 2 | 0 | 0 | nan |  |
| arc_style_prune_refine_simplified | baseline_or_diagnostic | none | 5 | nan | 0 | 0 | 0 | 1 | 12 | 0 | 0 | nan |  |
| threshold_merge_topk | baseline_or_diagnostic | none | 10 | nan | 0 | 0 | 0 | 1 | 2 | 0 | 0 | nan |  |
| arc_style_prune_refine_simplified | baseline_or_diagnostic | none | 10 | nan | 0 | 0 | 0 | 1 | 12 | 0 | 0 | nan |  |
| threshold_merge_topk | baseline_or_diagnostic | none | 20 | nan | 0 | 0 | 0 | 1 | 2 | 0 | 0 | nan |  |
| arc_style_prune_refine_simplified | baseline_or_diagnostic | none | 20 | nan | 0 | 0 | 0 | 1 | 12 | 0 | 0 | nan |  |
| threshold_merge_topk | baseline_or_diagnostic | none | 40 | nan | 0 | 0 | 0 | 1 | 2 | 0 | 0 | nan |  |
| arc_style_prune_refine_simplified | baseline_or_diagnostic | none | 40 | nan | 0 | 0 | 0 | 1 | 12 | 0 | 0 | nan |  |
| threshold_merge_topk | baseline_or_diagnostic | none | 80 | nan | 0 | 0 | 0 | 1 | 2 | 0 | 0 | nan |  |
| arc_style_prune_refine_simplified | baseline_or_diagnostic | none | 80 | nan | 0 | 0 | 0 | 1 | 12 | 0 | 0 | nan |  |
| smoke_repaired_cils | answer_quality_proxy_top | beta_bin_strata_lower | 5 | 0.5 | 0 | 0 | nan | 0 | 0 | 0 | 1 | nan | nan |
| smoke_repaired_cils | answer_quality_proxy_top | beta_bin_strata_lower | 5 | 0.6 | 0 | 0 | nan | 0 | 0 | 0 | 1 | nan | nan |
| smoke_repaired_cils | answer_quality_proxy_top | beta_bin_strata_lower | 5 | 0.7 | 0 | 0 | nan | 0 | 0 | 0 | 1 | nan | nan |
| smoke_repaired_cils | answer_quality_proxy_top | beta_bin_strata_lower | 5 | 0.8 | 0 | 0 | nan | 0 | 0 | 0 | 1 | nan | nan |
| smoke_repaired_cils | answer_quality_proxy_top | beta_bin_strata_lower | 5 | 0.9 | 0 | 0 | nan | 0 | 0 | 0 | 1 | nan | nan |
| smoke_repaired_cils | answer_quality_proxy_top | beta_bin_strata_lower | 10 | 0.5 | 0 | 0 | nan | 0 | 0 | 0 | 1 | nan | nan |

`oracle_p_answer_counterfactual` is diagnostic only and not an algorithm result.
