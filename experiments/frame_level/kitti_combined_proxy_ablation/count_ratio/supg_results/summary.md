# Real Frames Experiment Summary

- source: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_combined_proxy_ablation/count_ratio/supg_source.csv
- budget: 117, gamma: 0.9, delta: 0.05
- trials: 5

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 5 | 0.900000 | 0.050000 | 117 | 0.200000 | 0.476822 | 0.478125 | 0.933333 | 0.944444 | 317.800000 | 320.000000 | 117.000000 | 0 |
| U-CI-RT | rt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 0.137755 | 0.137755 | 1.000000 | 1.000000 | 1176.000000 | 1176.000000 | 117.000000 | 0 |
| SUPG-RT | rt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 0.137755 | 0.137755 | 1.000000 | 1.000000 | 1176.000000 | 1176.000000 | 109.600000 | 0 |
| U-NOCI-PT | pt | 5 | 0.900000 | 0.050000 | 117 | 1.000000 | 0.694768 | 0.691729 | 0.576543 | 0.567901 | 134.400000 | 133.000000 | 117.000000 | 0 |
| SUPG-PT | pt | 5 | 0.900000 | 0.050000 | 117 | 0.000000 | 1.000000 | 1.000000 | 0.228395 | 0.222222 | 37.000000 | 36.000000 | - | 0 |

Generated: 2026-05-19T09:49:39.294230