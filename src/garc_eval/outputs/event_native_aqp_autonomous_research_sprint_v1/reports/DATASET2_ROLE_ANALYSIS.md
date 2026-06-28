# Dataset2 Role Analysis

**Decision:** Dataset2 is a NO-GO for semantic event AQP. It is an in-cabin driver-facing camera, not a forward-facing dashcam.

---

## P0 Scout Findings (already completed)

| property | dataset2 | dataset3 |
|---|---|---|
| resolution | 1280×720 | 1920×1080 |
| fps | 30 | 30 |
| duration | 76.9 min | 57.7 min |
| camera type | **in-cabin driver-facing** | forward-facing dashcam |
| "person" detections | driver hands/body | pedestrians on road |
| near_ego ROI | dashboard, not road | road ahead |
| suitable for O_enter_ego_path_v0 | **NO** | YES |

---

## Why Dataset2 Cannot Support Event-Native AQP

1. **Wrong camera angle:** The camera faces the driver, not the road. The predicate `O_enter_ego_path_v0` requires observing objects entering the ego vehicle's forward driving path. This is impossible with a driver-facing camera.

2. **YOLO "person" detections are the driver:** The driver's hands, body, and face dominate the frame. YOLO detects these as "person" but they are not road users. The proxy signal is meaningless for ego-path intrusion.

3. **Near-ego ROI is dashboard:** The ego-band ROI (0.35-0.65x, 0.45-1.0y) covers the dashboard/steering wheel, not the road. Vehicle/pedestrian counts in this ROI are artifacts of the camera angle.

4. **No road users visible:** Other vehicles, pedestrians, and cyclists are not consistently visible in a driver-facing camera. There is no basis for semantic event detection.

---

## Could Dataset2 Serve a Different Role?

### As a low-selectivity stress test?
No. The issue is not low selectivity — it's that the predicate is inapplicable. There are no true positives to find because the camera doesn't show the road.

### As an audit/certificate test?
No. Audit sampling requires a meaningful oracle. The VLM cannot judge ego-path intrusion from a driver-facing camera.

### As a negative-only video?
Potentially, but with no research value. A video with 0 positives doesn't test AQP algorithms — it just confirms the proxy is useless (which we already know).

---

## Recommendation

**Do not invest VLM budget on dataset2.** The P0 scout gate correctly identified it as NO-GO. The full research effort should focus on:
1. **dataset3** — primary benchmark (40 positives, 27 clusters, this sprint)
2. **realcartest** — V13.8 reference benchmark (94 positives, 51 events)
3. **Future: third video** — a different scene type (highway/night/weather) for generalization

dataset2's only potential use is as a **negative example in the paper** — showing that the scout gate correctly filters unsuitable videos, demonstrating the methodology's robustness.
