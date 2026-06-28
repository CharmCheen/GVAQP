# Real Frames Experiment Summary

- source: garc_eval/outputs/uadetrac_temporal/k_stress/k28/supg_source.csv
- budget: 1000, gamma: 0.9, delta: 0.05
- trials: 10

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 10 | 0.900000 | 0.050000 | 1000 | 0.800000 | 0.027197 | 0.027178 | 0.862232 | 0.873391 | 7386.500000 | 7485.500000 | 1000.000000 | 0 |
| U-CI-RT | rt | 10 | 0.900000 | 0.050000 | 1000 | 0.000000 | 0.016729 | 0.016724 | 1.000000 | 1.000000 | 13927.500000 | 13932.000000 | 1000.000000 | 0 |
| SUPG-RT | rt | 10 | 0.900000 | 0.050000 | 1000 | 0.000000 | 0.016724 | 0.016724 | 1.000000 | 1.000000 | 13932.000000 | 13932.000000 | 964.600000 | 0 |
| U-NOCI-PT | pt | 10 | 0.900000 | 0.050000 | 1000 | 1.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1000.000000 | 0 |
| SUPG-PT | pt | 10 | 0.900000 | 0.050000 | 1000 | 0.000000 | 1.000000 | 1.000000 | 0.090558 | 0.083691 | 21.100000 | 19.500000 | - | 0 |

Generated: 2026-05-23T05:22:24.045889