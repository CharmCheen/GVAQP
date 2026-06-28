# Real Frames Experiment Summary

- source: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_0005_smoke/supg_source.csv
- budget: 30, gamma: 0.9, delta: 0.05
- trials: 5

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 5 | 0.900000 | 0.050000 | 30 | 0.200000 | 0.983063 | 0.984848 | 0.935135 | 0.925676 | 140.800000 | 139.000000 | 30.000000 | 0 |
| U-CI-RT | rt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.967094 | 0.961039 | 0.986486 | 1.000000 | 151.000000 | 154.000000 | 30.000000 | 0 |
| SUPG-RT | rt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.961039 | 0.961039 | 1.000000 | 1.000000 | 154.000000 | 154.000000 | 27.600000 | 0 |
| U-NOCI-PT | pt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.967094 | 0.961039 | 0.986486 | 1.000000 | 151.000000 | 154.000000 | 30.000000 | 0 |
| SUPG-PT | pt | 5 | 0.900000 | 0.050000 | 30 | - | - | - | - | - | - | - | - | 5 |

Generated: 2026-05-19T08:20:54.553567