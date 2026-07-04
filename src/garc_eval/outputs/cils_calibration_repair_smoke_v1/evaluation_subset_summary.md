# Evaluation Subset Summary

Duration strata source: `fallback_from_reference_events.csv`.

| eval_subset | events | min_duration | median_duration | max_duration | event_ids |
| --- | --- | --- | --- | --- | --- |
| interval_eval | 6 | 10.7 | 15.7 | 50.7 | realcartest_event_0022,realcartest_event_0028,realcartest_event_0029,realcartest_event_0033,realcartest_event_0034,realcartest_event_0037 |
| point_anchor | 14 | 0.2 | 0.7 | 0.7 | realcartest_event_0023,realcartest_event_0024,realcartest_event_0025,realcartest_event_0026,realcartest_event_0027,realcartest_event_0030,realcartest_event_0031,realcartest_event_0032,realcartest_event_0035,realcartest_event_0036,realcartest_event_0038,realcartest_event_0039,realcartest_event_0040,realcartest_event_0041 |

The primary interval-IoU smoke claim uses only `interval_eval` events (`duration >= 5s`). Point-anchor events are reported separately.
