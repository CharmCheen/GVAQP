# KITTI Combined Proxy Score Ablation Report

## 1. Background
- combined KITTI N=1176
- K=15
- label mean=13.78%
- original count_ratio proxy had 16 unique scores
- SUPG-RT under count_ratio selected all 1176 records

## 2. Proxy Score Rules
- count_ratio: min(proxy_count / K, 1.0)
- conf_sum_ratio: min(proxy_conf_sum / K, 1.0)
- conf_top5_ratio: min(proxy_conf_top5_sum / K, 1.0)
- soft_count_exp: 1 - exp(-proxy_conf_sum / K)
- count_conf_hybrid: clip(0.7 * min(proxy_count / K, 1.0) + 0.3 * proxy_max_conf, 0, 1)
- rank_percentile: rank percentile of proxy_conf_sum in [0, 1]; this is a ranking ablation, not a calibrated probability

## 3. Diagnostics
| rule | n | label_mean | proxy_unique_count | proxy_saturated_count | rt_supg_failure_rate | rt_supg_mean_precision | rt_supg_mean_recall | rt_supg_mean_selected_n | rt_supg_vacuous | pt_supg_error_count | pt_supg_mean_precision | pt_supg_mean_recall | u_noci_rt_failure_rate | u_noci_rt_mean_precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| count_ratio | 1176 | 0.137755 | 16 | 126 | 0.0 | 0.137755 | 1.0 | 1176.0 | True | 0 | 1.0 | 0.228395 | 0.2 | 0.476822 |
| conf_sum_ratio | 1176 | 0.137755 | 1102 | 0 | 0.0 | 0.137755 | 1.0 | 1176.0 | True | 0 | 1.0 | 0.227160 | 0.0 | 0.444012 |
| conf_top5_ratio | 1176 | 0.137755 | 1102 | 0 | 0.0 | 0.137755 | 1.0 | 1176.0 | True | 0 | 1.0 | 0.160494 | 0.2 | 0.336067 |
| soft_count_exp | 1176 | 0.137755 | 1102 | 0 | 0.0 | 0.137755 | 1.0 | 1176.0 | True | 0 | 1.0 | 0.222222 | 0.0 | 0.444012 |
| count_conf_hybrid | 1176 | 0.137755 | 1102 | 0 | 0.0 | 0.137755 | 1.0 | 1176.0 | True | 0 | 1.0 | 0.202469 | 0.2 | 0.460719 |
| rank_percentile | 1176 | 0.137755 | 1102 | 1 | 0.0 | 0.137755 | 1.0 | 1176.0 | True | 0 | 1.0 | 0.209877 | 0.0 | 0.444012 |

All rules kept the same label mean because the oracle label rule remained oracle_count >= 15. The continuous confidence-based rules substantially improved proxy score granularity, but none made SUPG-RT non-vacuous: every rule still selected all 1176 records.

SUPG-PT did not error for any rule. It remained high precision but low recall across the ablation.

## 4. Recommendation
No rule satisfies the main objective of making SUPG-RT non-vacuous.

If a proxy rule must be carried forward for additional data experiments, use count_conf_hybrid. It improves proxy granularity from 16 to 1102 unique values, removes saturation, keeps SUPG-PT error-free, and preserves some U-NOCI-RT failure as a no-guarantee baseline contrast. This recommendation is conditional: it did not fix SUPG-RT on the current combined KITTI set.

## 5. Next Step
- Do not run 20 or 100 trials on this exact ablation result.
- Add more KITTI sequences or switch to a larger traffic video/frame dataset.
- Re-run the same ablation on the larger dataset; only move to 20 trials if SUPG-RT no longer selects all records.
