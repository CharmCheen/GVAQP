# Interval-Eval Event Set

- Event strata source: `fallback from reference_events.csv`
- Total reference events: `20`
- Interval-eval events (`short_interval` or `true_interval`): `6`
- True interval events (`duration >= 5s`): `6`
- Event IDs: `['realcartest_event_0022', 'realcartest_event_0028', 'realcartest_event_0029', 'realcartest_event_0033', 'realcartest_event_0034', 'realcartest_event_0037']`

Duration summary:

| duration_stratum | events | min_duration | median_duration | max_duration |
| --- | --- | --- | --- | --- |
| point_anchor | 14 | 0.2 | 0.7 | 0.7 |
| true_interval | 6 | 10.7 | 15.7 | 50.7 |

These events are the appropriate interval-IoU focus set because point anchors can have overlap/center hits but fail IoU@0.3 due boundary mismatch.
