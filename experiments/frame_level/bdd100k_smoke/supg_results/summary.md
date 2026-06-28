# Real Frames Experiment Summary

- source: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/bdd100k_smoke/supg_source.csv
- budget: 1000, gamma: 0.9, delta: 0.05
- trials: 5

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 5 | 0.900000 | 0.050000 | 1000 | 0.600000 | 0.368933 | 0.384312 | 0.888105 | 0.884073 | 2470.200000 | 2282.000000 | 1000.000000 | 0 |
| U-CI-RT | rt | 5 | 0.900000 | 0.050000 | 1000 | 0.000000 | 0.099200 | 0.099200 | 1.000000 | 1.000000 | 10000.000000 | 10000.000000 | 1000.000000 | 0 |
| SUPG-RT | rt | 5 | 0.900000 | 0.050000 | 1000 | 0.000000 | 0.178704 | 0.168559 | 0.981048 | 0.987903 | 5522.400000 | 5814.000000 | 946.000000 | 0 |
| U-NOCI-PT | pt | 5 | 0.900000 | 0.050000 | 1000 | 0.800000 | 0.700450 | 0.861272 | 0.189315 | 0.208669 | 216.600000 | 238.000000 | 1000.000000 | 0 |
| SUPG-PT | pt | 5 | 0.900000 | 0.050000 | 1000 | 0.000000 | 1.000000 | 1.000000 | 0.273589 | 0.273185 | 271.400000 | 271.000000 | - | 0 |

Generated: 2026-05-20T02:56:13.009915