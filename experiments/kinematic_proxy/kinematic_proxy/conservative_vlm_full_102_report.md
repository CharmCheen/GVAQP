# Conservative 102-Clip VLM Predicate Full-Run Report

This report uses all 102 clips and a more conservative Qwen3-VL-32B prompt. These are still VLM pseudo labels, not human ground truth.

1. full-run clip count: 102 completed / 102 selected
2. old strict positive count in completed full-run set: 68
3. new conservative positive count: 22
4. new positive rate: 0.216
5. old strict -> conservative no: 46
6. old strict -> conservative uncertain: 0

## Conservative Positives

| clip_id | event_type | evidence |
|---|---|---|
| realcartest_5k_clip00005_s000010000ms_e000015000ms | crossing | a pedestrian with a bicycle crosses the road from right to left, entering the ego vehicle's projected path in front of the vehicle, requiring attention or potential braking to avoid collision. |
| realcartest_5k_clip00006_s000012000ms_e000017000ms | crossing | A cyclist on a yellow bike crosses the ego vehicle's path from the right sidewalk, moving diagonally into the road and entering the ego vehicle's projected path. The cyclist is close to the ego vehicle and appears to be crossing in front of |
| realcartest_5k_clip00007_s000014000ms_e000019000ms | crossing | A cyclist on the right sidewalk begins to ride across the road into the ego vehicle's path, moving from right to left across the frame, entering the roadway near the curb. The cyclist is in close proximity to the ego vehicle's projected pat |
| realcartest_5k_clip00008_s000016000ms_e000021000ms | crossing | a pedestrian with a yellow bag crosses the road from left to right directly in front of the ego vehicle, entering the projected path and requiring attention or braking; the crossing is clear and occurs within the clip. |
| realcartest_5k_clip00009_s000018000ms_e000023000ms | crossing | Pedestrian in black shirt and dark pants crosses directly in front of the ego vehicle from left to right, entering the vehicle's projected path. The pedestrian is mid-crossing at 0:01, and the ego vehicle is stopped or slowing, indicating a |
| realcartest_5k_clip00010_s000020000ms_e000025000ms | crossing | pedestrian crossing the road from left to right, entering the ego vehicle's projected path in front of the vehicle, moving across the intersection within the lane area, with clear visibility and trajectory towards the ego vehicle's path |
| realcartest_5k_clip00011_s000022000ms_e000027000ms | crossing | multiple pedestrians cross the road directly in front of the ego vehicle's path, starting from the sidewalk and entering the roadway, with one pedestrian in dark clothing crossing near the center of the ego vehicle's projected path. The cro |
| realcartest_5k_clip00012_s000024000ms_e000029000ms | crossing | pedestrians cross directly in front of the ego vehicle's path from left to right, entering the lane and walking across the road within the vehicle's projected path, requiring braking or slowing down |
| realcartest_5k_clip00013_s000026000ms_e000031000ms | crossing | a pedestrian wearing a white shirt and dark pants crosses directly in front of the ego vehicle from the right sidewalk into the road, entering the vehicle's projected path. The pedestrian is close to the vehicle and appears to be walking at |
| realcartest_5k_clip00014_s000028000ms_e000033000ms | crossing | a pedestrian in dark clothing crosses directly in front of the ego vehicle from left to right, entering the vehicle's path and requiring immediate attention or braking; the crossing occurs in the middle of the frame and is clearly visible a |
| realcartest_5k_clip00015_s000030000ms_e000035000ms | crossing | a pedestrian crosses directly in front of the ego vehicle from left to right, entering the vehicle's path; the pedestrian is clearly visible and moves across the road within the ego vehicle's forward trajectory, requiring immediate attentio |
| realcartest_5k_clip00036_s000072000ms_e000077000ms | cut_in | A silver minivan on the right side of the frame begins to move forward and sharply cuts into the ego vehicle's lane, entering the projected path from the adjacent lane. The vehicle's front end is clearly turning into the ego lane, creating  |
| realcartest_5k_clip00043_s000086000ms_e000091000ms | cut_in | A silver sedan on the left side of the road begins to turn right and cuts directly into the ego vehicle's path, moving from the left adjacent lane into the ego lane, creating a clear conflict. The vehicle's trajectory and proximity indicate |
| realcartest_5k_clip00044_s000088000ms_e000093000ms | cut_in | A gray BMW sedan is seen making a sharp left turn from the right lane into the ego vehicle's path, cutting directly in front of the ego vehicle. The car starts outside the ego path (in the adjacent lane) and moves into the ego vehicle's lan |
| realcartest_5k_clip00045_s000090000ms_e000095000ms | crossing | a silver SUV is seen making a left turn from the right side of the frame, crossing directly into the ego vehicle's forward path, with visible proximity and trajectory intrusion. The vehicle starts outside the ego path and clearly enters it, |
| realcartest_5k_clip00046_s000092000ms_e000097000ms | crossing | a cyclist on the right side of the road crosses the ego vehicle's path from right to left, entering the lane ahead of the ego vehicle, requiring attention to avoid collision. |
| realcartest_5k_clip00050_s000100000ms_e000105000ms | crossing | A motorcyclist with a yellow basket crosses the ego vehicle's path from right to left, entering the lane directly in front of the ego vehicle, requiring attention or potential braking. The crossing is clear and occurs within the ego vehicle |
| realcartest_5k_clip00051_s000102000ms_e000107000ms | crossing | A delivery scooter with a yellow box crosses directly in front of the ego vehicle from the left side of the frame, entering the ego vehicle's path as the vehicle approaches the intersection. The scooter is clearly in motion and crosses the  |
| realcartest_5k_clip00065_s000130000ms_e000135000ms | crossing | a motorbike with two riders crosses the ego vehicle's path from the right side, entering the lane from the sidewalk or shoulder area, moving diagonally across the road in front of the ego vehicle, requiring attention to avoid collision. |
| realcartest_5k_clip00083_s000166000ms_e000171000ms | cut_in | a three-wheeled cargo vehicle starts in the right lane/shoulder area and moves leftward into the ego vehicle's lane, entering the projected path and reducing lateral distance, indicating a cut-in maneuver that requires attention. |
| realcartest_5k_clip00092_s000184000ms_e000189000ms | crossing | A motorcyclist enters from the left side of the intersection, crosses the ego vehicle's path diagonally, and moves into the lane ahead. The crossing is direct and occurs within the ego vehicle's forward trajectory, requiring attention and p |
| realcartest_5k_clip00093_s000186000ms_e000191000ms | crossing | a motorcyclist with a yellow helmet enters from the left side of the frame, crosses the ego vehicle's path diagonally across the intersection, and moves into the ego lane ahead, requiring attention due to proximity and trajectory. |

## Conservative Negative Reasons

| negative_reason | count |
|---|---:|
| normal_following | 51 |
| dense_traffic_only | 21 |
| roadside_static | 7 |
| insufficient_evidence | 1 |

## Judgment

- positive rate is in the 10%-30% target range; this predicate is a plausible full-run candidate.
- Use this conservative pseudo-GT for budget simulation and policy sweep.
