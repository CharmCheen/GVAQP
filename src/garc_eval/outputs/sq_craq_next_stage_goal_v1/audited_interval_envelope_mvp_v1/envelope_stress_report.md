# Envelope Stress Report

| stress_scenario | candidate_count_budget | outside_positive_candidates | triggered_cannot_certify | selected_interval_count | selected_duration_total | observed_precision_interval_iou_0_3 | observed_precision_interval_iou_0_5 | interval_eval_event_recall_iou_0_3 | interval_eval_event_recall_iou_0_5 | duplicate_rate_iou_0_3 | duplicate_rate_iou_0_5 | avg_duration | p95_duration | background_duration_ratio_iou_0_3 | point_anchor_only_selected_count_iou_0_3 | empty_return | distinct_interval_events_hit_iou_0_3 | distinct_interval_events_hit_iou_0_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| proxy_accurate | 100 | 264 | True | 100 | 2730 | 0.1 | 0.03 | 0.666667 | 0.5 | 0.06 | 0 | 27.3 | 48.4 | 0.92381 | 1 | False | 4 | 3 |
| proxy_accurate | 200 | 22 | True | 200 | 3690 | 0.075 | 0.025 | 1 | 0.833333 | 0.045 | 0 | 18.45 | 32 | 0.921951 | 2 | False | 6 | 5 |
| proxy_randomized | 100 | 207 | True | 100 | 1414 | 0.06 | 0.04 | 0.833333 | 0.666667 | 0.01 | 0 | 14.14 | 32 | 0.87553 | 0 | False | 5 | 4 |
| proxy_randomized | 200 | 42 | True | 200 | 2458 | 0.04 | 0.025 | 1 | 0.833333 | 0.01 | 0 | 12.29 | 32 | 0.921888 | 0 | False | 6 | 5 |
| proxy_blinded_low_density | 100 | 264 | True | 100 | 2730 | 0.1 | 0.03 | 0.666667 | 0.5 | 0.06 | 0 | 27.3 | 48.4 | 0.92381 | 1 | False | 4 | 3 |
| proxy_blinded_low_density | 200 | 22 | True | 200 | 3690 | 0.075 | 0.025 | 1 | 0.833333 | 0.045 | 0 | 18.45 | 32 | 0.921951 | 2 | False | 6 | 5 |
| proxy_hard_negative_boost | 100 | 492 | True | 100 | 2596 | 0 | 0 | 0 | 0 | 0 | 0 | 25.96 | 32.8 | 1 | 1 | False | 0 | 0 |
| proxy_hard_negative_boost | 200 | 332 | True | 200 | 3568 | 0 | 0 | 0 | 0 | 0 | 0 | 17.84 | 32 | 1 | 2 | False | 0 | 0 |
