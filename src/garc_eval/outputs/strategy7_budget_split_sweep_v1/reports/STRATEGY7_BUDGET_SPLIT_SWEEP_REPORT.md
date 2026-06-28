# Strategy7 Budget Split Sweep Report

- Timestamp: 2026-06-27T16:38:47Z
- Mode: `full`; seeds per stochastic split: 500.
- No Qwen, GLM, YOLO, GPT, human oracle, frame extraction, downloads, or training were run.
- Split grid size: 14; budgets: [20, 30, 40, 60, 80, 100, 150]; delta: 0.05.
- Baseline split: `L370_S700_U30` = 70% L3, 0% Strategy7, 30% uniform random audit.
- Previous Strategy7 split: `L370_S720_U10` = 70% L3, 20% Strategy7, 10% uniform random audit.
- Decision: `WEAK_GO_PARETO_SPLITS_EXIST`.

## Input Audit

| dataset | rows | positive_count | negative_count | glm_counts | score_column | source_tables | leakage_note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dataset3_clean_pool | 100 | 28 | 72 | {'negative': 72, 'positive': 28} | object_count_mean | see config/experiment_config.yaml | labels/event clusters used only for evaluation and simulated oracle outcomes |
| realcartest_v13 | 399 | 94 | 305 | {'negative': 292, 'positive': 106, 'parse_error': 1} | object_count_mean | see config/experiment_config.yaml | labels/event clusters used only for evaluation and simulated oracle outcomes |

## Split Grid

| split_id | l3_frac | s7_frac | uniform_frac | policy_family |
| --- | --- | --- | --- | --- |
| L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | L3_uniform_only |
| L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | L3_strategy7_uniform |
| L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | L3_strategy7_uniform |
| L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | L3_strategy7_uniform |
| L350_S740_U10 | 0.500000 | 0.400000 | 0.100000 | L3_strategy7_uniform |
| L360_S700_U40 | 0.600000 | 0.000000 | 0.400000 | L3_uniform_only |
| L360_S710_U30 | 0.600000 | 0.100000 | 0.300000 | L3_strategy7_uniform |
| L360_S720_U20 | 0.600000 | 0.200000 | 0.200000 | L3_strategy7_uniform |
| L360_S730_U10 | 0.600000 | 0.300000 | 0.100000 | L3_strategy7_uniform |
| L370_S700_U30 | 0.700000 | 0.000000 | 0.300000 | L3_uniform_only |
| L370_S710_U20 | 0.700000 | 0.100000 | 0.200000 | L3_strategy7_uniform |
| L370_S720_U10 | 0.700000 | 0.200000 | 0.100000 | L3_strategy7_uniform |
| L380_S700_U20 | 0.800000 | 0.000000 | 0.200000 | L3_uniform_only |
| L380_S710_U10 | 0.800000 | 0.100000 | 0.100000 | L3_strategy7_uniform |

## Previous Strategy7 Split Vs Baseline

### Dataset3 Clean Pool

| requested_B | delta_vs_baseline_recall_lower_bound | delta_vs_baseline_l3_missed_recovered | delta_vs_baseline_audit_positives | delta_vs_baseline_width_to_one |
| --- | --- | --- | --- | --- |
| 20.000000 | -0.002295 | 1.904000 | 1.854000 | 0.002295 |
| 30.000000 | -0.003817 | 2.462000 | 2.288000 | 0.003817 |
| 40.000000 | 0.009888 | 3.690000 | 3.590000 | -0.009888 |
| 60.000000 | 0.026478 | 3.172000 | 3.974000 | -0.026478 |
| 80.000000 | 0.030495 | 0.136000 | 2.606000 | -0.030495 |
| 100.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 150.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |

### Realcartest

| requested_B | delta_vs_baseline_recall_lower_bound | delta_vs_baseline_l3_missed_recovered | delta_vs_baseline_audit_positives | delta_vs_baseline_width_to_one |
| --- | --- | --- | --- | --- |
| 20.000000 | -0.015127 | 0.098000 | 0.064000 | 0.015127 |
| 30.000000 | -0.027312 | 0.816000 | 0.730000 | 0.027312 |
| 40.000000 | -0.033458 | 1.474000 | 1.340000 | 0.033458 |
| 60.000000 | -0.049327 | 2.098000 | 1.810000 | 0.049327 |
| 80.000000 | -0.044191 | 3.656000 | 3.000000 | 0.044191 |
| 100.000000 | -0.057079 | 4.412000 | 3.910000 | 0.057079 |
| 150.000000 | -0.046446 | 4.232000 | 3.628000 | 0.046446 |

## Pareto Frontier Examples

Rows are Pareto-efficient for mean L3-missed-positive recovery and mean recall lower bound within each dataset/budget.

### Dataset3 Clean Pool

| requested_B | split_id | l3_frac | s7_frac | uniform_frac | mean_recall_lower_bound | mean_l3_topB_missed_positive_recovered_count | mean_audit_positive_count | balanced_recovery_lb_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | L350_S740_U10 | 0.500000 | 0.400000 | 0.100000 | 0.120484 | 6.404000 | 6.476000 | 0.886876 |
| 20 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.127194 | 4.366000 | 4.584000 | 0.789055 |
| 20 | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 0.122001 | 4.876000 | 5.012000 | 0.764115 |
| 30 | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 0.225107 | 7.096000 | 7.324000 | 0.897428 |
| 30 | L350_S740_U10 | 0.500000 | 0.400000 | 0.100000 | 0.204567 | 8.516000 | 8.634000 | 0.862204 |
| 40 | L350_S740_U10 | 0.500000 | 0.400000 | 0.100000 | 0.308474 | 11.506000 | 11.690000 | 0.904773 |
| 40 | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 0.325780 | 9.286000 | 9.628000 | 0.859677 |
| 40 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.330582 | 8.130000 | 8.644000 | 0.818064 |
| 60 | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 0.536806 | 7.136000 | 13.030000 | 0.957148 |
| 60 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.525967 | 7.570000 | 11.728000 | 0.948974 |
| 80 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.746071 | 3.644000 | 15.358000 | 0.942494 |
| 80 | L360_S710_U30 | 0.600000 | 0.100000 | 0.300000 | 0.746071 | 3.644000 | 10.358000 | 0.942494 |
| 80 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.700256 | 3.834000 | 14.056000 | 0.729695 |
| 100 | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 1.000000 | 0.000000 | 13.000000 | 0.000000 |
| 100 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 1.000000 | 0.000000 | 13.000000 | 0.000000 |
| 100 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 1.000000 | 0.000000 | 13.000000 | 0.000000 |
| 150 | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 1.000000 | 0.000000 | 13.000000 | 0.000000 |
| 150 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 1.000000 | 0.000000 | 13.000000 | 0.000000 |
| 150 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 1.000000 | 0.000000 | 13.000000 | 0.000000 |

### Realcartest

| requested_B | split_id | l3_frac | s7_frac | uniform_frac | mean_recall_lower_bound | mean_l3_topB_missed_positive_recovered_count | mean_audit_positive_count | balanced_recovery_lb_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.050092 | 2.626000 | 2.782000 | 0.738062 |
| 20 | L360_S710_U30 | 0.600000 | 0.100000 | 0.300000 | 0.053051 | 2.190000 | 2.260000 | 0.726495 |
| 20 | L360_S700_U40 | 0.600000 | 0.000000 | 0.400000 | 0.054796 | 1.630000 | 1.762000 | 0.661966 |
| 30 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.084182 | 3.246000 | 3.558000 | 0.681279 |
| 30 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.079395 | 3.630000 | 3.890000 | 0.673287 |
| 30 | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.085763 | 2.896000 | 3.266000 | 0.651106 |
| 40 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.115809 | 5.166000 | 5.504000 | 0.710572 |
| 40 | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.124805 | 3.610000 | 4.122000 | 0.669507 |
| 40 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.119870 | 3.880000 | 4.304000 | 0.635658 |
| 60 | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 0.175056 | 8.680000 | 9.276000 | 0.792815 |
| 60 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.182960 | 6.584000 | 7.432000 | 0.694054 |
| 60 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.189370 | 5.488000 | 6.636000 | 0.659044 |
| 80 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.254615 | 8.606000 | 10.288000 | 0.742750 |
| 80 | L360_S720_U20 | 0.600000 | 0.200000 | 0.200000 | 0.255532 | 7.832000 | 8.704000 | 0.697920 |
| 80 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.255549 | 6.888000 | 8.936000 | 0.637573 |
| 100 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.326961 | 10.192000 | 12.016000 | 0.714606 |
| 100 | L360_S720_U20 | 0.600000 | 0.200000 | 0.200000 | 0.334803 | 9.074000 | 9.956000 | 0.691111 |
| 100 | L360_S710_U30 | 0.600000 | 0.100000 | 0.300000 | 0.340592 | 6.492000 | 7.764000 | 0.579544 |
| 150 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.522920 | 11.008000 | 13.714000 | 0.792829 |
| 150 | L360_S710_U30 | 0.600000 | 0.100000 | 0.300000 | 0.524901 | 10.044000 | 11.534000 | 0.764776 |
| 150 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.505093 | 11.720000 | 13.916000 | 0.727236 |

## Recommended Split Counts

The balanced score is a diagnostic ranking after Pareto filtering, not a deployable tuned policy.

| dataset | split_id | l3_frac | s7_frac | uniform_frac | selected_budget_count | mean_balanced_score | mean_recall_lower_bound | mean_l3_missed_recovered |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dataset3_clean_pool | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 2 | 0.927288 | 0.380957 | 7.116000 |
| dataset3_clean_pool | L350_S740_U10 | 0.500000 | 0.400000 | 0.100000 | 2 | 0.895825 | 0.214479 | 8.955000 |
| dataset3_clean_pool | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 1 | 0.942494 | 0.746071 | 3.644000 |
| realcartest_v13 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 3 | 0.737390 | 0.219065 | 5.626667 |
| realcartest_v13 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 3 | 0.722643 | 0.232462 | 7.988000 |
| realcartest_v13 | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 1 | 0.792815 | 0.175056 | 8.680000 |

## Target Budget Summary

Full target table is in `tables/target_lower_bound_budget_table.csv`.

| dataset | split_id | l3_frac | s7_frac | uniform_frac | target_lower_bound_gamma | min_effective_budget_mean_reaches_gamma | min_requested_budget_mean_reaches_gamma | min_effective_budget_95pct_seeds_reach_gamma | min_requested_budget_95pct_seeds_reach_gamma | max_mean_recall_lower_bound | max_certificate_rate_for_gamma |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dataset3_clean_pool | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.100000 | 20 | 20 | 20 | 20 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.100000 | 20 | 20 | 20 | 20 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.100000 | 20 | 20 | 20 | 20 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 0.100000 | 20 | 20 | 20 | 20 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S740_U10 | 0.500000 | 0.400000 | 0.100000 | 0.100000 | 20 | 20 | 20 | 20 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.200000 | 40 | 40 | 40 | 40 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.200000 | 30 | 30 | 40 | 40 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.200000 | 30 | 30 | 40 | 40 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 0.200000 | 30 | 30 | 40 | 40 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S740_U10 | 0.500000 | 0.400000 | 0.100000 | 0.200000 | 30 | 30 | 40 | 40 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.300000 | 60 | 60 | 60 | 60 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.300000 | 40 | 40 | 60 | 60 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.300000 | 40 | 40 | 60 | 60 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 0.300000 | 40 | 40 | 60 | 60 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S740_U10 | 0.500000 | 0.400000 | 0.100000 | 0.300000 | 40 | 40 | 60 | 60 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.500000 | 80 | 80 | 80 | 80 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.500000 | 80 | 80 | 80 | 80 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.500000 | 60 | 60 | 80 | 80 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S730_U20 | 0.500000 | 0.300000 | 0.200000 | 0.500000 | 60 | 60 | 80 | 80 | 1.000000 | 1.000000 |
| dataset3_clean_pool | L350_S740_U10 | 0.500000 | 0.400000 | 0.100000 | 0.500000 | 80 | 80 | 80 | 80 | 1.000000 | 1.000000 |
| realcartest_v13 | L360_S710_U30 | 0.600000 | 0.100000 | 0.300000 | 0.100000 | 40 | 40 | 60 | 60 | 0.524901 | 1.000000 |
| realcartest_v13 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.100000 | 40 | 40 | 60 | 60 | 0.522920 | 1.000000 |
| realcartest_v13 | L360_S700_U40 | 0.600000 | 0.000000 | 0.400000 | 0.100000 | 40 | 40 | 60 | 60 | 0.515153 | 1.000000 |
| realcartest_v13 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.100000 | 40 | 40 | 60 | 60 | 0.505093 | 1.000000 |
| realcartest_v13 | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.100000 | 40 | 40 | 40 | 40 | 0.503969 | 1.000000 |
| realcartest_v13 | L360_S710_U30 | 0.600000 | 0.100000 | 0.300000 | 0.200000 | 80 | 80 | 80 | 80 | 0.524901 | 1.000000 |
| realcartest_v13 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.200000 | 80 | 80 | 80 | 80 | 0.522920 | 1.000000 |
| realcartest_v13 | L360_S700_U40 | 0.600000 | 0.000000 | 0.400000 | 0.200000 | 80 | 80 | 80 | 80 | 0.515153 | 1.000000 |
| realcartest_v13 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.200000 | 80 | 80 | 80 | 80 | 0.505093 | 1.000000 |
| realcartest_v13 | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.200000 | 80 | 80 | 80 | 80 | 0.503969 | 1.000000 |
| realcartest_v13 | L360_S710_U30 | 0.600000 | 0.100000 | 0.300000 | 0.300000 | 100 | 100 | 150 | 150 | 0.524901 | 1.000000 |
| realcartest_v13 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.300000 | 100 | 100 | 150 | 150 | 0.522920 | 1.000000 |
| realcartest_v13 | L360_S700_U40 | 0.600000 | 0.000000 | 0.400000 | 0.300000 | 100 | 100 | 150 | 150 | 0.515153 | 1.000000 |
| realcartest_v13 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.300000 | 100 | 100 | 150 | 150 | 0.505093 | 1.000000 |
| realcartest_v13 | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.300000 | 100 | 100 | 150 | 150 | 0.503969 | 1.000000 |
| realcartest_v13 | L360_S710_U30 | 0.600000 | 0.100000 | 0.300000 | 0.500000 | 150 | 150 |  |  | 0.524901 | 0.696000 |
| realcartest_v13 | L350_S710_U40 | 0.500000 | 0.100000 | 0.400000 | 0.500000 | 150 | 150 |  |  | 0.522920 | 0.656000 |
| realcartest_v13 | L360_S700_U40 | 0.600000 | 0.000000 | 0.400000 | 0.500000 | 150 | 150 |  |  | 0.515153 | 0.598000 |
| realcartest_v13 | L350_S720_U30 | 0.500000 | 0.200000 | 0.300000 | 0.500000 | 150 | 150 |  |  | 0.505093 | 0.466000 |
| realcartest_v13 | L350_S700_U50 | 0.500000 | 0.000000 | 0.500000 | 0.500000 | 150 | 150 |  |  | 0.503969 | 0.484000 |

## Interpretation

- More Strategy7 audit generally increases L3-missed-positive recovery, but it can weaken the exact hypergeometric certificate by reducing the uniform random sample.
- The useful AQP region is therefore not the maximum-disagreement split; it is the Pareto frontier where targeted recovery is bought without sacrificing too much random-audit mass.
- Selection policy uses only proxy scores, timestamps, anchor ids, and existing GLM labels. Existing VLM-defined positives and event ids are used only for evaluation and simulated oracle outcomes.
- Current exact certificate remains clip-level and assumes the uniform audit is sampled uniformly from the residual population.

## Limitations

- This is a replay over existing pseudo-oracle/VLM-defined labels, not human truth.
- The split grid is intentionally coarse; it identifies Pareto regions, not a final optimized policy.
- Dataset3 clean pool has N=100, so B=150 is clipped to B=100 and should not be interpreted as a true 150-call regime.
- Disagreement audit is not certified as a random stratum here; that is the next algorithmic task.
