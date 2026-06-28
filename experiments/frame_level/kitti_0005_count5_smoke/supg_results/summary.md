# Real Frames Experiment Summary

- source: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_0005_count5_smoke/supg_source.csv
- budget: 30, gamma: 0.9, delta: 0.05
- trials: 5

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.885511 | 0.910448 | 0.942424 | 0.939394 | 70.600000 | 68.000000 | 30.000000 | 0 |
| U-CI-RT | rt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.433143 | 0.428571 | 1.000000 | 1.000000 | 152.400000 | 154.000000 | 30.000000 | 0 |
| SUPG-RT | rt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.428571 | 0.428571 | 1.000000 | 1.000000 | 154.000000 | 154.000000 | 27.400000 | 0 |
| U-NOCI-PT | pt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.911742 | 0.911765 | 0.939394 | 0.939394 | 68.000000 | 68.000000 | 30.000000 | 0 |
| SUPG-PT | pt | 5 | 0.900000 | 0.050000 | 30 | - | - | - | - | - | - | - | - | 5 |

Generated: 2026-05-19T08:26:45.721207