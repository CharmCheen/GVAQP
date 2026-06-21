# Strict VLM Label Variant Diagnostics

This report derives stricter pseudo-GT labels from existing exact 102-clip Qwen3-VL-32B outputs. It does not call VLM again and does not create human ground truth.

## Variant Summary

| variant | valid clips | positives | positive rate |
|---|---:|---:|---:|
| broad | 102 | 96 | 0.941 |
| ego_relevant | 102 | 82 | 0.804 |
| strict | 102 | 68 | 0.667 |
| strict_v2 | 102 | 68 | 0.667 |
| strict_v3 | 102 | 68 | 0.667 |

## Downgrades

- strict -> strict_v2 downgraded clips: 0
  - none
- strict_v2 -> strict_v3 downgraded clips: 0
  - none

## Field Distributions

### Event Type

| event_type | count |
|---|---:|
| cut_in | 38 |
| crossing | 30 |
| dense_traffic_only | 16 |
| close_following | 12 |
| none | 6 |

### Risk Level

| risk_level | count |
|---|---:|
| L2 | 68 |
| L1 | 28 |
| L0 | 6 |

### Confidence

| confidence | count |
|---|---:|
| high | 102 |

## Weak Event Types Inside Strict Positives

- dense_traffic_only / close_following / roadside_static inside strict positives: 0

## Reason Keyword Diagnostics

### broad

- clear interaction keywords: conflict=50, crossing=36, braking=26, sudden braking=17, crosses=5, cut in=4, lane change=4, cuts in=2
- weak / broad keywords: dense traffic=8, parked=8, roadside=2, traffic flow=2, no clear conflict=1, no immediate risk=1

### ego_relevant

- clear interaction keywords: conflict=39, crossing=32, braking=13, crosses=5, sudden braking=5, cut in=4, lane change=3, cuts in=2
- weak / broad keywords: dense traffic=2, parked=1

### strict

- clear interaction keywords: conflict=35, crossing=31, braking=6, crosses=5, cut in=4, lane change=3, cuts in=2, sudden braking=1
- weak / broad keywords: none

### strict_v2

- clear interaction keywords: conflict=35, crossing=31, braking=6, crosses=5, cut in=4, lane change=3, cuts in=2, sudden braking=1
- weak / broad keywords: none

### strict_v3

- clear interaction keywords: conflict=35, crossing=31, braking=6, crosses=5, cut in=4, lane change=3, cuts in=2, sudden braking=1
- weak / broad keywords: none


## Representative strict_v2 / strict_v3 Positives

### strict_v2

- `realcartest_5k_clip00001_s000002000ms_e000007000ms`: crossing L2; 一名骑电动车的行人正在从右侧人行道横穿马路，其路径与 ego 车辆的行驶轨迹存在交叉，构成潜在的横向冲突，属于典型的交叉交通风险。
- `realcartest_5k_clip00002_s000004000ms_e000009000ms`: crossing L2; A pedestrian with an umbrella is crossing the road directly in front of the ego vehicle, entering the driving path. The pedestrian is close to the vehicle's trajectory and may require the ego vehicle to slow down or stop, constituting a cle
- `realcartest_5k_clip00003_s000006000ms_e000011000ms`: crossing L2; A pedestrian with an umbrella and a cyclist are actively crossing the road in front of the ego vehicle, directly intersecting its path. The pedestrian is mid-crossing and close to the ego vehicle's trajectory, indicating a potential conflic
- `realcartest_5k_clip00004_s000008000ms_e000013000ms`: crossing L2; A pedestrian with an umbrella is crossing the road directly in front of the ego vehicle, entering the driving path. The pedestrian is mid-crossing and close to the vehicle's trajectory, creating a potential conflict that requires the ego ve
- `realcartest_5k_clip00005_s000010000ms_e000015000ms`: crossing L2; A cyclist crosses the road directly in front of the ego vehicle, moving from right to left across the driving path, creating a potential conflict. The cyclist is close to the ego vehicle's trajectory and is actively crossing the intersectio
- `realcartest_5k_clip00006_s000012000ms_e000017000ms`: crossing L2; A cyclist is actively crossing the ego vehicle's path from right to left, moving directly into the driving lane in front of the vehicle. This constitutes a clear crossing interaction that directly affects the ego vehicle's future driving pa
- `realcartest_5k_clip00007_s000014000ms_e000019000ms`: crossing L2; A cyclist wearing a helmet crosses the road directly in front of the ego vehicle, entering the vehicle's path from the right sidewalk. The cyclist is moving into the roadway at a close distance, creating a potential conflict with the ego ve
- `realcartest_5k_clip00008_s000016000ms_e000021000ms`: crossing L2; A pedestrian is crossing the road directly in front of the ego vehicle, moving from left to right across the driving path. The pedestrian is within the intersection area and is clearly in the vehicle's immediate path, requiring the ego vehi

### strict_v3

- `realcartest_5k_clip00001_s000002000ms_e000007000ms`: crossing L2; 一名骑电动车的行人正在从右侧人行道横穿马路，其路径与 ego 车辆的行驶轨迹存在交叉，构成潜在的横向冲突，属于典型的交叉交通风险。
- `realcartest_5k_clip00002_s000004000ms_e000009000ms`: crossing L2; A pedestrian with an umbrella is crossing the road directly in front of the ego vehicle, entering the driving path. The pedestrian is close to the vehicle's trajectory and may require the ego vehicle to slow down or stop, constituting a cle
- `realcartest_5k_clip00003_s000006000ms_e000011000ms`: crossing L2; A pedestrian with an umbrella and a cyclist are actively crossing the road in front of the ego vehicle, directly intersecting its path. The pedestrian is mid-crossing and close to the ego vehicle's trajectory, indicating a potential conflic
- `realcartest_5k_clip00004_s000008000ms_e000013000ms`: crossing L2; A pedestrian with an umbrella is crossing the road directly in front of the ego vehicle, entering the driving path. The pedestrian is mid-crossing and close to the vehicle's trajectory, creating a potential conflict that requires the ego ve
- `realcartest_5k_clip00005_s000010000ms_e000015000ms`: crossing L2; A cyclist crosses the road directly in front of the ego vehicle, moving from right to left across the driving path, creating a potential conflict. The cyclist is close to the ego vehicle's trajectory and is actively crossing the intersectio
- `realcartest_5k_clip00006_s000012000ms_e000017000ms`: crossing L2; A cyclist is actively crossing the ego vehicle's path from right to left, moving directly into the driving lane in front of the vehicle. This constitutes a clear crossing interaction that directly affects the ego vehicle's future driving pa
- `realcartest_5k_clip00007_s000014000ms_e000019000ms`: crossing L2; A cyclist wearing a helmet crosses the road directly in front of the ego vehicle, entering the vehicle's path from the right sidewalk. The cyclist is moving into the roadway at a close distance, creating a potential conflict with the ego ve
- `realcartest_5k_clip00008_s000016000ms_e000021000ms`: crossing L2; A pedestrian is crossing the road directly in front of the ego vehicle, moving from left to right across the driving path. The pedestrian is within the intersection area and is clearly in the vehicle's immediate path, requiring the ego vehi


## Representative Downgraded Clips

- strict -> strict_v2: no downgraded clips.
- strict_v2 -> strict_v3: no downgraded clips.

## Conclusion

- strict_v2 and strict_v3 do not reach the target 10%-30% positive-rate range. The reason is that the exact VLM output already labels most strict positives as high-confidence L2 cut_in/crossing events; the available structured fields leave little room for post-hoc filtering.
- Current evidence suggests the VLM predicate is still broad for rare-risk retrieval. A re-prompted 32B pass with a more conservative predicate is likely needed if the target workload should be rare.
