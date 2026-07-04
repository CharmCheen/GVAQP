# Evaluation Subsets

Duration strata source: `fallback from reference_events.csv`.

| eval_subset | events | min_duration | median_duration | max_duration |
| --- | --- | --- | --- | --- |
| interval_eval | 6 | 10.7 | 15.7 | 50.7 |
| point_anchor | 14 | 0.2 | 0.7 | 0.7 |

Interval-IoU main replay metrics use only `interval_eval` events. Point-anchor events are reported separately with overlap/center/containment style metrics.
