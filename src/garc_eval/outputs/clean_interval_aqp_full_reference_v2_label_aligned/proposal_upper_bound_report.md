# Proposal Upper Bound Report

| lattice_oracle_upper_bound_iou_0_3 | lattice_oracle_upper_bound_iou_0_5 | dense_multiscale_oracle_upper_bound_iou_0_3 | candidate_count_total |
| --- | --- | --- | --- |
| 0.55 | 0.3 | 0.3 | 11939 |

Proposal family summary:

| method | any_overlap_event_recall | center_hit_event_recall | event_recall_iou_0_3 | event_recall_iou_0_5 | answer_overlap_purity_recall | candidate_count | avg_duration | p95_duration | duplicate_rate | background_duration_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| threshold_merge_v2 | 1 | 1 | 0.5 | 0.3 | 0.5 | 2088 | 18.387 | 72 | 0.106322 | 0.800243 |
| boundary_refined_expansion | 0.75 | 0.7 | 0.35 | 0.2 | 0.3 | 735 | 25.9102 | 40 | 0.25034 | 0.707085 |
| dense_multiscale_windows | 1 | 1 | 0.3 | 0.3 | 0.3 | 3570 | 12.2812 | 32 | 0.0630252 | 0.865546 |
| fixed_window | 1 | 1 | 0.3 | 0.3 | 0.3 | 505 | 15.695 | 30 | 0.0772277 | 0.866535 |
| signal_peak_multiscale | 1 | 1 | 0.3 | 0.3 | 0.3 | 4200 | 15.9714 | 32 | 0.110952 | 0.826434 |
| low_density_blindspot_proposals | 0.7 | 0.65 | 0.1 | 0.1 | 0.15 | 841 | 12.9084 | 24 | 0.0225922 | 0.94134 |

`oracle_upper_bound_score` is used only in `proposal_recall_curve_v2.csv` for upper-bound analysis, not by CILS.
