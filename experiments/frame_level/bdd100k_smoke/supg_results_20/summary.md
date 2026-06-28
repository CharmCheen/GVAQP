# Real Frames Experiment Summary

- source: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/supg_source.csv
- budget: 1000, gamma: 0.9, delta: 0.05
- trials: 20

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 20 | 0.900000 | 0.050000 | 1000 | 0.500000 | 0.342842 | 0.354941 | 0.902974 | 0.899698 | 2723.250000 | 2514.500000 | 1000.000000 | 0 |
| U-CI-RT | rt | 20 | 0.900000 | 0.050000 | 1000 | 0.000000 | 0.099200 | 0.099200 | 1.000000 | 1.000000 | 10000.000000 | 10000.000000 | 1000.000000 | 0 |
| SUPG-RT | rt | 20 | 0.900000 | 0.050000 | 1000 | 0.000000 | 0.195889 | 0.183428 | 0.972530 | 0.976310 | 5048.150000 | 5280.000000 | 944.900000 | 0 |
| U-NOCI-PT | pt | 20 | 0.900000 | 0.050000 | 1000 | 0.800000 | 0.487450 | 0.833842 | 0.139819 | 0.098286 | 160.900000 | 100.000000 | 1000.000000 | 0 |
| SUPG-PT | pt | 20 | 0.900000 | 0.050000 | 1000 | 0.000000 | 1.000000 | 1.000000 | 0.273841 | 0.273185 | 271.650000 | 271.000000 | - | 0 |

Generated: 2026-05-20T02:56:53.565674