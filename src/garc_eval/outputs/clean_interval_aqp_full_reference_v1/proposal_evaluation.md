# Proposal Evaluation

Full-reference use: evaluation only.

| method | proposal_recall_iou_0_3 | proposal_recall_iou_0_5 | number_of_intervals | avg_duration | median_duration | duplicate_rate | background_duration_ratio | positive_unit_fraction | budgeted_recall@5 | budgeted_precision@5 | budgeted_recall@10 | budgeted_precision@10 | budgeted_recall@20 | budgeted_precision@20 | budgeted_recall@40 | budgeted_precision@40 | budgeted_recall@80 | budgeted_precision@80 | budgeted_recall@120 | budgeted_precision@120 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fixed_window | 0.3 | 0.3 | 505 | 15.695 | 10 | 0.0772277 | 0.866535 | 0.133465 | 0 | 0 | 0 | 0 | 0.05 | 0.1 | 0.1 | 0.25 | 0.1 | 0.1375 | 0.15 | 0.125 |
| multi_signal_union | 0.2 | 0.1 | 81 | 6.66667 | 4 | 0 | 0.889915 | 0.110085 | 0.1 | 0.4 | 0.1 | 0.2 | 0.15 | 0.15 | 0.15 | 0.075 | 0.2 | 0.05 | 0.2 | 0.0493827 |
| peak_expand | 0.2 | 0.1 | 186 | 20.3871 | 22 | 0.172043 | 0.760217 | 0.239783 | 0 | 0 | 0 | 0 | 0.05 | 0.25 | 0.1 | 0.325 | 0.15 | 0.2 | 0.15 | 0.166667 |
| threshold_merge | 0.2 | 0.2 | 354 | 8.85876 | 6 | 0.0649718 | 0.869211 | 0.130789 | 0.1 | 0.4 | 0.1 | 0.3 | 0.1 | 0.2 | 0.2 | 0.225 | 0.2 | 0.1625 | 0.2 | 0.141667 |
| valley_split | 0.25 | 0.05 | 94 | 14.1489 | 6 | 0.0106383 | 0.890337 | 0.109663 | 0.1 | 0.4 | 0.1 | 0.2 | 0.2 | 0.2 | 0.25 | 0.15 | 0.25 | 0.075 | 0.25 | 0.0638298 |
