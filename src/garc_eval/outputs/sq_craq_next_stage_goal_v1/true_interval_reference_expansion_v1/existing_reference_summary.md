# Existing Reference Summary

Current reference is insufficient for interval-IoU evaluation because only `6` events qualify as true interval events.

| event_subset | event_count | mean_duration | min_duration | max_duration |
| --- | --- | --- | --- | --- |
| interval_eval | 6 | 20.7 | 10.7 | 50.7 |
| point_anchor | 14 | 0.664286 | 0.2 | 0.7 |

Point-anchor events must be excluded from main interval TP counts.
