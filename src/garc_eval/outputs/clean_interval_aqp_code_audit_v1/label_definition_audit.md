# Label Definition And Alignment Audit

Verdict: **PASS**

Calibration target in `calibration_trials_v2.csv`: `['answer_iou_0_3']`

| check | pass | mismatches |
| --- | --- | --- |
| answer_iou_0_3_equals_event_hit_iou_0_3 | True | 0 |
| answer_iou_0_5_equals_event_hit_iou_0_5 | True | 0 |
| independent_iou_0_3_matches | True | 0 |
| independent_iou_0_5_matches | True | 0 |

The independent recomputation uses temporal IoU = intersection / union, event overlap ratio = intersection / event duration, interval purity = intersection / interval duration, and duration inflation = interval duration / matched event duration.
