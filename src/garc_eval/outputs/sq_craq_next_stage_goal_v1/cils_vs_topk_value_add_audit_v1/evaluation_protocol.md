# Evaluation Protocol

Main evaluation is `interval_eval` only: duration >= 5s. `point_anchor` events, duration <= 2s, are excluded from main TP counts and only reported as point-anchor-only selections.

Primary metrics:
- `interval_eval_event_recall_iou_0_3`
- `interval_eval_event_recall_iou_0_5`
- observed interval precision
- returned count
- duplicate rate
- average and p95 returned duration
- background duration ratio
- empty-return rate
- stability across seeds

Reference gate: **FAIL**.

| duration_stratum | event_count |
| --- | --- |
| interval_eval | 6 |
| point_anchor | 14 |
