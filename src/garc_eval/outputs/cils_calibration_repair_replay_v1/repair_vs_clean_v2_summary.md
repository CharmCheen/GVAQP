# Repair Vs Clean V2 Summary

Top repaired replay rows by interval-eval recall:

| pilot_policy | calibration_model | budget | tau | interval_recall | precision | returned | duration | duplicate | empty_return_rate | method |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| answer_quality_proxy_top | beta_bin_strata_lower | 20 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | beta_bin_strata_lower | 40 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | beta_bin_strata_mean | 20 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | beta_bin_strata_mean | 20 | 0.6 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | beta_bin_strata_mean | 40 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | beta_bin_strata_mean | 40 | 0.6 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_0_25 | 20 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_0_25 | 20 | 0.6 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_0_25 | 40 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_0_25 | 40 | 0.6 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_0_5 | 20 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_0_5 | 20 | 0.6 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_0_5 | 40 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_0_5 | 40 | 0.6 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_1_0 | 20 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_1_0 | 20 | 0.6 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_1_0 | 40 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | calibrated_floor_1_0 | 40 | 0.6 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| answer_quality_proxy_top | isotonic_or_logistic | 80 | 0.5 | 0.166667 | 1 | 1 | 16 | 0 | 0 | repaired_cils_replay |
| hybrid_discovery_boundary | beta_bin_strata_lower | 10 | 0.5 | 0.166667 | 1 | 1 | 32 | 0 | 0 | repaired_cils_replay |

Clean v2 CILS has zero returned intervals for every budget/tau. Baseline comparisons are diagnostic because repaired CILS is a replay, not a production algorithm result.
