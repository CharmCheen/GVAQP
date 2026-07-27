# Failure Analysis

The strongest branch is `P1_L`, but its Recall@20 remains below 0.40 on both videos. It improves over frozen P0 and has AUC above 0.55, so semantic occupancy is a real mechanism signal, but it is insufficient for the frozen Gate.

Gate table:

| preview   | all_checks_pass   | recall_at_20_ge_0_40_both   | enrichment_gt_1_5_both   | nested_lovo_recall_beats_p0_both   | nested_lovo_auc_gt_0_55_both   | beats_shuffled_score_both   | beats_time_index_macro   | preview_cost_ratio_le_0_10   | net_yield_primary_budget_nonnegative_both   | at_least_one_common_budget_positive_both   | leave_best_region_direction_nonnegative_vs_p0_both   |
|:----------|:------------------|:----------------------------|:-------------------------|:-----------------------------------|:-------------------------------|:----------------------------|:-------------------------|:-----------------------------|:--------------------------------------------|:-------------------------------------------|:-----------------------------------------------------|
| P1_L      | False             | False                       | True                     | True                               | True                           | True                        | True                     | True                         | True                                        | True                                       | True                                                 |
| P1_M      | False             | False                       | False                    | True                               | True                           | True                        | True                     | True                         | False                                       | False                                      | False                                                |
| P2        | False             | False                       | False                    | False                              | False                          | True                        | True                     | True                         | False                                       | False                                      | False                                                |

There are 130 feature columns with cross-video Spearman sign conflicts. High-score/no-event and low-score/high-event tables are materialized. Structured P0/P1/P2 disagreement, time confounding, preview cost decomposition, single-region contribution, model-versus-heuristic disagreement, and offline-oracle missed headroom are in `metrics/failure_analysis_metrics.json`.

No new scheduler or allocator is authorized. Any new visible-signal direction remains a `CANDIDATE_HYPOTHESIS`.
