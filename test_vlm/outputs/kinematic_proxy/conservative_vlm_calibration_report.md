# Conservative VLM Predicate Calibration Report

This report uses a 20-clip calibration subset and a more conservative Qwen3-VL-32B prompt. These are still VLM pseudo labels, not human ground truth.

1. calibration clip count: 20 completed / 20 selected
2. old strict positive count in completed calibration set: 18
3. new conservative positive count: 5
4. new positive rate: 0.250
5. old strict -> conservative no: 13
6. old strict -> conservative uncertain: 0

## Conservative Positives

| clip_id | event_type | evidence |
|---|---|---|
| realcartest_5k_clip00008_s000016000ms_e000021000ms | crossing | A pedestrian with a white bag crosses the road directly in front of the ego vehicle from left to right, starting from the sidewalk and entering the ego vehicle's projected path. The pedestrian is in close proximity to the vehicle's path and |
| realcartest_5k_clip00010_s000020000ms_e000025000ms | crossing | a pedestrian in white shirt and dark pants crosses the road directly in front of the ego vehicle, moving from left to right across the projected path, with clear motion and proximity to the vehicle's trajectory |
| realcartest_5k_clip00011_s000022000ms_e000027000ms | crossing | multiple pedestrians cross the road directly in front of the ego vehicle, moving from left to right across the vehicle's projected path, requiring the vehicle to slow or stop. The crossing is clear and occurs within the lane area, with visi |
| realcartest_5k_clip00012_s000024000ms_e000029000ms | crossing | multiple pedestrians are crossing the road directly in front of the ego vehicle, moving from left to right across the lane; one pedestrian is clearly in the middle of the road at the end of the clip, indicating a direct path conflict. |
| realcartest_5k_clip00005_s000010000ms_e000015000ms | crossing | A pedestrian with a bicycle crosses the road from right to left, entering the ego vehicle's projected path in front of the vehicle. The crossing occurs in the middle of the frame, and the pedestrian is clearly moving across the lane where t |

## Conservative Negative Reasons

| negative_reason | count |
|---|---:|
| normal_following | 9 |
| dense_traffic_only | 4 |
| roadside_static | 2 |

## Judgment

- positive rate is in the 10%-30% target range; this predicate is a plausible full-run candidate.
- Recommend full 102 conservative labeling if this calibration set looks qualitatively acceptable.
