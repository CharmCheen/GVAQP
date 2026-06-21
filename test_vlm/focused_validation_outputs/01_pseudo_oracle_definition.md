# Pseudo-oracle Definition

The `full conservative VLM scan` is fixed as the pseudo-oracle target for this focused validation.

- A clip is an oracle-positive fixed window iff `conservative_positive == yes/true/1`.
- This definition is only for semantic clip query processing and budget allocation evaluation.
- It is not human ground truth and must not be reported as true traffic-risk recall.
- All recall and precision values in this validation are relative to the VLM pseudo-oracle.

Metric names used in this validation:

- `oracle_clip_recall`
- `oracle_event_recall`
- `oracle_event_precision`
- `vlm_call_saving`
- `budgeted_event_iou`

## Statistics

- total clips: 1000
- positive clips: 61
- negative clips: 939
- positive rate: 0.061
- segment count: 11

## Positive Clips By Segment

| segment_id | clips | positive_clips | positive_rate |
|---|---:|---:|---:|
| realcartest_seg001 | 399 | 36 | 0.090 |
| realcartest_seg005 | 299 | 16 | 0.054 |
| realcartest_5k_seg001 | 7 | 4 | 0.571 |
| realcartest_5k_seg002 | 40 | 2 | 0.050 |
| realcartest_seg003 | 136 | 2 | 0.015 |
| test_seg001 | 9 | 1 | 0.111 |
| realcartest_seg002 | 4 | 0 | 0.000 |
| realcartest_seg004 | 91 | 0 | 0.000 |
| realcartest_seg006 | 12 | 0 | 0.000 |
| realcartest_seg007 | 2 | 0 | 0.000 |
| realcartest_seg008 | 1 | 0 | 0.000 |
