# Pilot Policy Report

Replay uses `50` seeds.

| pilot_policy | budget | trials | mean_positive_rate | mean_interval_positive_rate | zero_positive_pilot_rate | mean_positive_strata_coverage |
| --- | --- | --- | --- | --- | --- | --- |
| answer_quality_proxy_top | 5 | 50 | 0 | 0 | 1 | 0 |
| answer_quality_proxy_top | 10 | 50 | 0 | 0 | 1 | 0 |
| answer_quality_proxy_top | 20 | 50 | 0.05 | 0.05 | 0 | 1 |
| answer_quality_proxy_top | 40 | 50 | 0.05 | 0.05 | 0 | 2 |
| answer_quality_proxy_top | 80 | 50 | 0.125 | 0.125 | 0 | 9 |
| epsilon_mixed_answer_proxy | 5 | 50 | 0.004 | 0.004 | 0.98 | 0.02 |
| epsilon_mixed_answer_proxy | 10 | 50 | 0.026 | 0.026 | 0.74 | 0.26 |
| epsilon_mixed_answer_proxy | 20 | 50 | 0.071 | 0.071 | 0 | 1.4 |
| epsilon_mixed_answer_proxy | 40 | 50 | 0.063 | 0.063 | 0 | 2.52 |
| epsilon_mixed_answer_proxy | 80 | 50 | 0.1085 | 0.108 | 0 | 7.6 |
| hybrid_discovery_boundary | 5 | 50 | 0.4 | 0.4 | 0 | 2 |
| hybrid_discovery_boundary | 10 | 50 | 0.6 | 0.6 | 0 | 6 |
| hybrid_discovery_boundary | 20 | 50 | 0.3 | 0.3 | 0 | 6 |
| hybrid_discovery_boundary | 40 | 50 | 0.175 | 0.175 | 0 | 7 |
| hybrid_discovery_boundary | 80 | 50 | 0.1875 | 0.1875 | 0 | 13 |
| quota_stratified_v2 | 5 | 50 | 0.092 | 0.092 | 0.54 | 0.46 |
| quota_stratified_v2 | 10 | 50 | 0.096 | 0.096 | 0.2 | 0.96 |
| quota_stratified_v2 | 20 | 50 | 0.109 | 0.106 | 0.06 | 2.18 |
| quota_stratified_v2 | 40 | 50 | 0.1065 | 0.1025 | 0.02 | 4.26 |
| quota_stratified_v2 | 80 | 50 | 0.11025 | 0.10825 | 0 | 8.82 |
| top_active_score | 5 | 50 | 0 | 0 | 1 | 0 |
| top_active_score | 10 | 50 | 0 | 0 | 1 | 0 |
| top_active_score | 20 | 50 | 0 | 0 | 1 | 0 |
| top_active_score | 40 | 50 | 0.05 | 0.05 | 0 | 2 |
| top_active_score | 80 | 50 | 0.1 | 0.1 | 0 | 8 |
| uniform | 5 | 50 | 0.104 | 0.104 | 0.56 | 0.52 |
| uniform | 10 | 50 | 0.096 | 0.094 | 0.36 | 0.96 |
| uniform | 20 | 50 | 0.105 | 0.104 | 0.1 | 2.08 |
| uniform | 40 | 50 | 0.095 | 0.0935 | 0 | 3.76 |
| uniform | 80 | 50 | 0.1005 | 0.09925 | 0 | 7.88 |

The original clean-v2-equivalent policy is `top_active_score`. Repaired policies are diagnostic replays, not production algorithms.
