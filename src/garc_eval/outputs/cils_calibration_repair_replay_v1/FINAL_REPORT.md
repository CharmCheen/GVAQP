# FINAL REPORT: CILS Calibration Repair Replay V1

## 1. Executive Summary

- CILS empty return repaired in replay: **yes**.
- Most effective pilot/calibration policy: **answer_quality_proxy_top + beta_bin_strata_lower**.
- Best interval-eval recall: `0.167` at B=`20`, tau=`0.5`.
- This is a replay / diagnostic result, not a production algorithm result.
- Root cause update: **PILOT_CALIBRATION_REPAIR_HELPS**.

## 2. Inputs And No-Leakage Protocol

Used clean no-leak v2 artifacts. No model inference, no proposal-family changes, no clean v2 output edits. Reference labels are used only for oracle replay lookup and final evaluation. Point-anchor and interval-eval events are reported separately.

## 3. Feature Diagnosis

See `answer_feature_diagnostics.md`. Raw active score is weakly answer-aligned; diagnostic answer-quality proxy uses only feature-only columns.

## 4. Pilot Policy Comparison

| pilot_policy | budget | mean_positive_rate | zero_positive_rate | mean_interval_positive_rate |
| --- | --- | --- | --- | --- |
| answer_quality_proxy_top | 5 | 0 | 1 | 0 |
| answer_quality_proxy_top | 10 | 0 | 1 | 0 |
| answer_quality_proxy_top | 20 | 0.05 | 0 | 0.05 |
| answer_quality_proxy_top | 40 | 0.05 | 0 | 0.05 |
| answer_quality_proxy_top | 80 | 0.125 | 0 | 0.125 |
| epsilon_mixed_answer_proxy | 5 | 0.004 | 0.98 | 0.004 |
| epsilon_mixed_answer_proxy | 10 | 0.026 | 0.74 | 0.026 |
| epsilon_mixed_answer_proxy | 20 | 0.071 | 0 | 0.071 |
| epsilon_mixed_answer_proxy | 40 | 0.063 | 0 | 0.063 |
| epsilon_mixed_answer_proxy | 80 | 0.1085 | 0 | 0.108 |
| hybrid_discovery_boundary | 5 | 0.4 | 0 | 0.4 |
| hybrid_discovery_boundary | 10 | 0.6 | 0 | 0.6 |
| hybrid_discovery_boundary | 20 | 0.3 | 0 | 0.3 |
| hybrid_discovery_boundary | 40 | 0.175 | 0 | 0.175 |
| hybrid_discovery_boundary | 80 | 0.1875 | 0 | 0.1875 |
| quota_stratified_v2 | 5 | 0.092 | 0.54 | 0.092 |
| quota_stratified_v2 | 10 | 0.096 | 0.2 | 0.096 |
| quota_stratified_v2 | 20 | 0.109 | 0.06 | 0.106 |
| quota_stratified_v2 | 40 | 0.1065 | 0.02 | 0.1025 |
| quota_stratified_v2 | 80 | 0.11025 | 0 | 0.10825 |
| top_active_score | 5 | 0 | 1 | 0 |
| top_active_score | 10 | 0 | 1 | 0 |
| top_active_score | 20 | 0 | 1 | 0 |
| top_active_score | 40 | 0.05 | 0 | 0.05 |
| top_active_score | 80 | 0.1 | 0 | 0.1 |
| uniform | 5 | 0.104 | 0.56 | 0.104 |
| uniform | 10 | 0.096 | 0.36 | 0.094 |
| uniform | 20 | 0.105 | 0.1 | 0.104 |
| uniform | 40 | 0.095 | 0 | 0.0935 |
| uniform | 80 | 0.1005 | 0 | 0.09925 |

## 5. Calibration Model Comparison

| pilot_policy | calibration_model | budget | brier | ece | max_p |
| --- | --- | --- | --- | --- | --- |
| top_active_score | beta_bin_strata_lower | 5 | 0.0906765 | 0.0291302 | 0.0714286 |
| answer_quality_proxy_top | beta_bin_strata_lower | 5 | 0.0906786 | 0.0285978 | 0.0714286 |
| epsilon_mixed_answer_proxy | beta_bin_strata_lower | 5 | 0.0907008 | 0.0294866 | 0.08 |
| quota_stratified_v2 | beta_bin_strata_lower | 5 | 0.0908591 | 0.0354037 | 0.268571 |
| answer_quality_proxy_top | isotonic_or_logistic | 5 | 0.0917231 | 0.0430163 | 0.142857 |
| top_active_score | isotonic_or_logistic | 5 | 0.0917231 | 0.0430163 | 0.142857 |
| answer_quality_proxy_top | beta_bin_strata_mean | 5 | 0.09189 | 0.043448 | 0.333333 |
| answer_quality_proxy_top | calibrated_floor_0_25 | 5 | 0.09189 | 0.043448 | 0.333333 |
| answer_quality_proxy_top | calibrated_floor_0_5 | 5 | 0.09189 | 0.043448 | 0.333333 |
| answer_quality_proxy_top | calibrated_floor_1_0 | 5 | 0.09189 | 0.043448 | 0.333333 |
| uniform | beta_bin_strata_lower | 5 | 0.0920766 | 0.0407775 | 0.26 |
| epsilon_mixed_answer_proxy | isotonic_or_logistic | 5 | 0.092377 | 0.0458734 | 0.145714 |
| top_active_score | beta_bin_strata_mean | 5 | 0.0925071 | 0.0449308 | 0.333333 |
| top_active_score | calibrated_floor_0_25 | 5 | 0.0925071 | 0.0449308 | 0.333333 |
| top_active_score | calibrated_floor_0_5 | 5 | 0.0925071 | 0.0449308 | 0.333333 |
| top_active_score | calibrated_floor_1_0 | 5 | 0.0925071 | 0.0449308 | 0.333333 |
| epsilon_mixed_answer_proxy | beta_bin_strata_mean | 5 | 0.09329 | 0.0478038 | 0.34 |
| epsilon_mixed_answer_proxy | calibrated_floor_0_25 | 5 | 0.09329 | 0.0478038 | 0.34 |
| epsilon_mixed_answer_proxy | calibrated_floor_0_5 | 5 | 0.09329 | 0.0478038 | 0.34 |
| epsilon_mixed_answer_proxy | calibrated_floor_1_0 | 5 | 0.0932903 | 0.0478044 | 0.34 |
| answer_quality_proxy_top | hierarchical_beta_pooling | 5 | 0.0976455 | 0.0986174 | 0.333333 |
| top_active_score | hierarchical_beta_pooling | 5 | 0.0997363 | 0.0648325 | 0.333333 |
| hybrid_discovery_boundary | beta_bin_strata_lower | 5 | 0.102906 | 0.113978 | 0.5 |
| quota_stratified_v2 | isotonic_or_logistic | 5 | 0.106764 | 0.108731 | 0.208571 |
| quota_stratified_v2 | beta_bin_strata_mean | 5 | 0.108658 | 0.113962 | 0.486667 |
| quota_stratified_v2 | calibrated_floor_0_25 | 5 | 0.108658 | 0.113962 | 0.486667 |
| quota_stratified_v2 | calibrated_floor_0_5 | 5 | 0.108658 | 0.113962 | 0.486667 |
| quota_stratified_v2 | calibrated_floor_1_0 | 5 | 0.108658 | 0.113962 | 0.486667 |
| uniform | isotonic_or_logistic | 5 | 0.111992 | 0.117302 | 0.217143 |
| uniform | beta_bin_strata_mean | 5 | 0.1123 | 0.118278 | 0.48 |
| uniform | calibrated_floor_0_25 | 5 | 0.1123 | 0.118278 | 0.48 |
| uniform | calibrated_floor_0_5 | 5 | 0.1123 | 0.118278 | 0.48 |
| uniform | calibrated_floor_1_0 | 5 | 0.112319 | 0.118311 | 0.48 |
| epsilon_mixed_answer_proxy | hierarchical_beta_pooling | 5 | 0.11798 | 0.156725 | 0.34 |
| uniform | hierarchical_beta_pooling | 5 | 0.145149 | 0.214217 | 0.467 |
| quota_stratified_v2 | hierarchical_beta_pooling | 5 | 0.146699 | 0.21992 | 0.486667 |
| hybrid_discovery_boundary | beta_bin_strata_mean | 5 | 0.197809 | 0.328551 | 0.666667 |
| hybrid_discovery_boundary | calibrated_floor_0_25 | 5 | 0.197809 | 0.328551 | 0.666667 |
| hybrid_discovery_boundary | calibrated_floor_0_5 | 5 | 0.197809 | 0.328551 | 0.666667 |
| hybrid_discovery_boundary | isotonic_or_logistic | 5 | 0.197936 | 0.328731 | 0.428571 |
| hybrid_discovery_boundary | calibrated_floor_1_0 | 5 | 0.198097 | 0.32895 | 0.666667 |
| hybrid_discovery_boundary | hierarchical_beta_pooling | 5 | 0.253287 | 0.366819 | 0.75 |
| answer_quality_proxy_top | isotonic_or_logistic | 10 | 0.0901452 | 0.0165075 | 0.0833333 |
| top_active_score | isotonic_or_logistic | 10 | 0.0901452 | 0.0165075 | 0.0833333 |
| answer_quality_proxy_top | beta_bin_strata_mean | 10 | 0.0903892 | 0.0177737 | 0.333333 |
| answer_quality_proxy_top | calibrated_floor_0_25 | 10 | 0.0903892 | 0.0177737 | 0.333333 |
| answer_quality_proxy_top | calibrated_floor_0_5 | 10 | 0.0903892 | 0.0177737 | 0.333333 |
| answer_quality_proxy_top | calibrated_floor_1_0 | 10 | 0.0903892 | 0.0177737 | 0.333333 |
| quota_stratified_v2 | beta_bin_strata_lower | 10 | 0.0906706 | 0.028721 | 0.408333 |
| top_active_score | beta_bin_strata_mean | 10 | 0.0907476 | 0.0186957 | 0.333333 |
| top_active_score | calibrated_floor_0_25 | 10 | 0.0907476 | 0.0186957 | 0.333333 |
| top_active_score | calibrated_floor_0_5 | 10 | 0.0907476 | 0.0186957 | 0.333333 |
| top_active_score | calibrated_floor_1_0 | 10 | 0.0907476 | 0.0186957 | 0.333333 |
| epsilon_mixed_answer_proxy | isotonic_or_logistic | 10 | 0.0912354 | 0.0295903 | 0.105 |
| uniform | beta_bin_strata_lower | 10 | 0.0918545 | 0.0376102 | 0.335 |
| epsilon_mixed_answer_proxy | beta_bin_strata_lower | 10 | 0.0924275 | 0.0485226 | 0.160833 |
| epsilon_mixed_answer_proxy | beta_bin_strata_mean | 10 | 0.0932153 | 0.0367897 | 0.42 |
| epsilon_mixed_answer_proxy | calibrated_floor_0_25 | 10 | 0.0932153 | 0.0367897 | 0.42 |
| epsilon_mixed_answer_proxy | calibrated_floor_0_5 | 10 | 0.0932153 | 0.0367897 | 0.42 |
| epsilon_mixed_answer_proxy | calibrated_floor_1_0 | 10 | 0.0932153 | 0.0367897 | 0.42 |

## 6. Repaired CILS Results

Best replay rows:

| pilot_policy | calibration_model | budget | tau | mean_returned | empty_return_rate | interval_recall | precision | p95_duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| answer_quality_proxy_top | beta_bin_strata_lower | 20 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_lower | 40 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_mean | 20 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_mean | 20 | 0.6 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_mean | 40 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_mean | 40 | 0.6 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | calibrated_floor_0_25 | 20 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | calibrated_floor_0_25 | 20 | 0.6 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | calibrated_floor_0_25 | 40 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | calibrated_floor_0_25 | 40 | 0.6 | 1 | 0 | 0.166667 | 1 | 16 |

Best non-floor replay rows:

| pilot_policy | calibration_model | budget | tau | mean_returned | empty_return_rate | interval_recall | precision | p95_duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| answer_quality_proxy_top | beta_bin_strata_lower | 20 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_lower | 40 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_mean | 20 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_mean | 20 | 0.6 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_mean | 40 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | beta_bin_strata_mean | 40 | 0.6 | 1 | 0 | 0.166667 | 1 | 16 |
| answer_quality_proxy_top | isotonic_or_logistic | 80 | 0.5 | 1 | 0 | 0.166667 | 1 | 16 |
| hybrid_discovery_boundary | beta_bin_strata_lower | 10 | 0.5 | 1 | 0 | 0.166667 | 1 | 32 |
| hybrid_discovery_boundary | beta_bin_strata_lower | 80 | 0.5 | 1 | 0 | 0.166667 | 1 | 32 |
| hybrid_discovery_boundary | beta_bin_strata_lower | 80 | 0.6 | 1 | 0 | 0.166667 | 1 | 32 |

## 7. Baseline Comparison

See `repair_vs_baseline_comparison.csv` and `repair_vs_clean_v2_summary.md`.

## 8. Root Cause Update

PILOT_CALIBRATION_REPAIR_HELPS. If non-floor repaired rows return interval recall, calibration/pilot repair helps. If only diagnostic floor rows return, the root cause remains probability floor / score alignment.

## 9. Research Implication

Selector direction is worth continuing only if non-floor repaired calibration gives nonzero interval-eval recall without long-duration artifacts. True interval reference should remain separate from point anchors. Audited proposal repair remains a relevant baseline.

## 10. Next Actions

1. Promote the best non-floor repaired pilot/calibration replay into a formal no-leak smoke experiment if it has interval recall > 0.
2. Keep true-interval and point-anchor evaluation split in all future CILS reports.
3. Compare against audited proposal repair before treating CILS as the main AQP route.
