# Envelope MVP Summary

| envelope_baseline | candidate_count_budget | mean_recall_iou_0_3 | mean_recall_iou_0_5 | mean_candidate_count | mean_total_duration | mean_coverage_per_duration | mean_miss_upper | cannot_certify_rate | audit_oracle_budget | coverage_per_duration |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E0_threshold_merge | 20 | 0.5 | 0.166667 | 20 | 1772 | 0.5 | 0.203023 | 1 | 1 | 0.000282167 |
| E0_threshold_merge | 50 | 0.333333 | 0.333333 | 50 | 1956 | 0.333333 | 0.13821 | 1 | 1 | 0.000170416 |
| E0_threshold_merge | 100 | 0.333333 | 0 | 100 | 2580 | 0.333333 | 0.171356 | 1 | 1 | 0.000129199 |
| E0_threshold_merge | 200 | 0.333333 | 0 | 200 | 3124 | 0.333333 | 0.13821 | 1 | 1 | 0.000106701 |
| E0_threshold_merge | 400 | 0.5 | 0.333333 | 325 | 3628 | 0.5 | 0.233596 | 1 | 1 | 0.000137817 |
| E1_top_score_envelope | 20 | 0.666667 | 0.5 | 20 | 374 | 0.666667 | 0.263305 | 1 | 1 | 0.00178253 |
| E1_top_score_envelope | 50 | 0.333333 | 0.166667 | 50 | 2028 | 0.333333 | 0.171356 | 1 | 1 | 0.000164366 |
| E1_top_score_envelope | 100 | 0.333333 | 0.166667 | 100 | 2700 | 0.333333 | 0.13821 | 1 | 1 | 0.000123457 |
| E1_top_score_envelope | 200 | 0 | 0 | 200 | 3690 | 0 | 0.0633422 | 0 | 1 | 0 |
| E1_top_score_envelope | 400 | 0 | 0 | 400 | 4792 | 0 | 0.066536 | 0 | 1 | 0 |
| E2_dense_lattice_upper | 20 | 0 | 0 | 20 | 410 | 0 | 0.0633422 | 0 | 1 | 0 |
| E2_dense_lattice_upper | 50 | 0 | 0 | 50 | 744 | 0 | 0.0633422 | 0 | 1 | 0 |
| E2_dense_lattice_upper | 100 | 0 | 0 | 100 | 1244 | 0 | 0.0633422 | 0 | 1 | 0 |
| E2_dense_lattice_upper | 200 | 0 | 0 | 200 | 2160 | 0 | 0.0783949 | 0 | 1 | 0 |
| E2_dense_lattice_upper | 400 | 0 | 0 | 400 | 4374 | 0 | 1 | 1 | 1 | 0 |
| E3_craq_stratified_repair | 20 | 0.383333 | 0.133333 | 15.7 | 196.9 | 0.383333 | 0.17712 | 0.95 | 20 | 0.00194684 |
| E3_craq_stratified_repair | 50 | 0.191667 | 0.0666667 | 33.25 | 1841.8 | 0.191667 | 0.118941 | 0.8 | 20 | 0.000104065 |
| E3_craq_stratified_repair | 100 | 0.158333 | 0.0583333 | 55.95 | 2075.9 | 0.158333 | 0.10138 | 0.7 | 20 | 7.62721e-05 |
| E3_craq_stratified_repair | 200 | 0.025 | 0.025 | 108.15 | 2796.8 | 0.025 | 0.069267 | 0.15 | 20 | 8.93879e-06 |
| E3_craq_stratified_repair | 400 | 0 | 0 | 242 | 4048 | 0 | 0.0633422 | 0 | 20 | 0 |
