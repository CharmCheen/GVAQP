# Real Frames Experiment Summary

- source: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_combined_proxy_ablation/conf_sum_ratio/supg_source.csv
- budget: 117, gamma: 0.9, delta: 0.05
- trials: 5

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 0.444012 | 0.446429 | 0.937037 | 0.925926 | 342.800000 | 336.000000 | 117.000000 | 0 |
| U-CI-RT | rt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 0.137755 | 0.137755 | 1.000000 | 1.000000 | 1176.000000 | 1176.000000 | 117.000000 | 0 |
| SUPG-RT | rt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 0.137755 | 0.137755 | 1.000000 | 1.000000 | 1176.000000 | 1176.000000 | 109.600000 | 0 |
| U-NOCI-PT | pt | 5 | 0.900000 | 0.050000 | 117 | 0.400000 | 0.883992 | 0.954545 | 0.241975 | 0.172840 | 48.600000 | 28.000000 | 117.000000 | 0 |
| SUPG-PT | pt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 1.000000 | 1.000000 | 0.227160 | 0.216049 | 36.800000 | 35.000000 | - | 0 |

Generated: 2026-05-19T09:49:41.615891