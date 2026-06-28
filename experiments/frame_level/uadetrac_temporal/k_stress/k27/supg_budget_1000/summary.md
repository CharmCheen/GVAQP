# Real Frames Experiment Summary

- source: garc_eval/outputs/uadetrac_temporal/k_stress/k27/supg_source.csv
- budget: 1000, gamma: 0.9, delta: 0.05
- trials: 10

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 10 | 0.900000 | 0.050000 | 1000 | 0.300000 | 0.056511 | 0.056513 | 0.898693 | 0.907407 | 7300.400000 | 7358.000000 | 1000.000000 | 0 |
| U-CI-RT | rt | 10 | 0.900000 | 0.050000 | 1000 | 0.000000 | 0.032956 | 0.032946 | 1.000000 | 1.000000 | 13927.500000 | 13932.000000 | 1000.000000 | 0 |
| SUPG-RT | rt | 10 | 0.900000 | 0.050000 | 1000 | 0.000000 | 0.032946 | 0.032946 | 1.000000 | 1.000000 | 13932.000000 | 13932.000000 | 962.900000 | 0 |
| U-NOCI-PT | pt | 10 | 0.900000 | 0.050000 | 1000 | 0.900000 | 0.178333 | 0.000000 | 0.015904 | 0.000000 | 8.200000 | 0.000000 | 1000.000000 | 0 |
| SUPG-PT | pt | 10 | 0.900000 | 0.050000 | 1000 | 0.000000 | 1.000000 | 1.000000 | 0.097386 | 0.100218 | 44.700000 | 46.000000 | - | 0 |

Generated: 2026-05-23T05:22:20.320977