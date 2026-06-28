# Real Frames Experiment Summary

- source: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_combined_proxy_ablation/count_conf_hybrid/supg_source.csv
- budget: 117, gamma: 0.9, delta: 0.05
- trials: 5

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 5 | 0.900000 | 0.050000 | 117 | 0.200000 | 0.460719 | 0.462733 | 0.920988 | 0.919753 | 324.800000 | 322.000000 | 117.000000 | 0 |
| U-CI-RT | rt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 0.137755 | 0.137755 | 1.000000 | 1.000000 | 1176.000000 | 1176.000000 | 117.000000 | 0 |
| SUPG-RT | rt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 0.137755 | 0.137755 | 1.000000 | 1.000000 | 1176.000000 | 1176.000000 | 108.600000 | 0 |
| U-NOCI-PT | pt | 5 | 0.900000 | 0.050000 | 117 | 1.000000 | 0.453714 | 0.672414 | 0.158025 | 0.067901 | 36.200000 | 13.000000 | 117.000000 | 0 |
| SUPG-PT | pt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 1.000000 | 1.000000 | 0.202469 | 0.197531 | 32.800000 | 32.000000 | - | 0 |

Generated: 2026-05-19T09:49:47.567962