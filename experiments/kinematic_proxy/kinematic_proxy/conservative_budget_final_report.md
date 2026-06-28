# Conservative 102-Clip Pseudo-GT Budget Allocation Final Report

This report treats the full conservative Qwen3-VL-32B scan as pseudo-GT. It is not human ground truth.

## Label Shift

- clips: 102
- old strict positives: 68 / 102 = 0.667
- conservative positives: 22 / 102 = 0.216
- old strict positives downgraded by conservative prompt: 46

## Conservative Negative Reasons

| negative_reason | count |
|---|---:|
| normal_following | 51 |
| dense_traffic_only | 21 |
| roadside_static | 7 |
| insufficient_evidence | 1 |

## Conservative Event Type Distribution

| event_type | count |
|---|---:|
| normal_following | 51 |
| dense_traffic_only | 21 |
| crossing | 18 |
| roadside_static | 5 |
| cut_in | 4 |
| none | 3 |

## Low-Budget Results

| variant | best clip recall method | clip recall | random clip recall | best event recall method | event recall | random event recall |
|---|---|---:|---:|---|---:|---:|
| old_strict | top_count | 0.199 | 0.131 | top_kinematic | 0.893 | 0.709 |
| conservative | top_count | 0.398 | 0.128 | temporal_nms_naive | 0.786 | 0.570 |

## Policy Interpretation

- conservative temporal-NMS average event recall across budgets/methods: 0.778
- conservative top_count/top_naive/ensemble_count_naive average clip recall: 0.530/0.318/0.455
- conservative top_kinematic average clip/event recall: 0.205/0.762
- Clip-level and event-level conclusions diverge under conservative pseudo-GT; temporal-aware allocation remains useful.
- Conservative prompt produces a useful rare-ish predicate range for budget allocation.
- Do not resume kinematic-v0 tuning as the main path; prioritize proxy anchors, temporal diversity, and conservative predicate validation.
