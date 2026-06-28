# Stage 15: Corridor Calibration Audit

## Question

Before concluding "geometric features (score_fusion_geometry_motion,
lateral_presence_max) don't generalize cross-video" (Stage 11), check whether
the corridor projection depends on camera calibration parameters (focal length,
mount height, pitch, FOV) and whether dataset3/realcartest used the same or
different parameters.

## Finding: NO camera calibration exists

A thorough codebase search found **zero camera calibration parameters** anywhere
in the repository. There is no:
- Focal length, principal point, or intrinsics matrix
- Mount height, pitch angle, or extrinsics
- FOV specification
- IPM (inverse perspective mapping), homography, or bird's-eye projection
- Vanishing point or horizon line estimation

The "ego-path corridor" / "geometry" features are ALL hardcoded image-plane ROI
fractions:

| Feature | Definition | Calibration |
|---|---|---|
| `score_fusion_geometry_motion` | z(bbox_area_sum_max) + z(motion_energy_max) | Per-video z-score, no geometry |
| `center_roi_vehicle_count` | Vehicles with bbox center in [W/3, 2W/3] × [H/3, 2H/3] | Fixed thirds, no calibration |
| `lateral_presence_max` | Count of objects with cx outside center third | Fixed thirds, no calibration |
| `near_ego_vehicle_count` | Vehicles with cx in [0.35W, 0.65W], cy > 0.45H | Fixed fractions, no calibration |

**There is no geometric projection to calibrate.** The "corridor" is a
middle-thirds bounding box in pixel space, not a camera-projected driving
corridor. The name "ego-path corridor" is a misnomer — it's an image-plane
heuristic, not a 3D geometric projection.

## dataset3 vs realcartest: same hardcoded fractions

Both videos use the SAME hardcoded ROI fractions (thirds for center_roi,
0.35/0.65/0.45 for the ego band). Neither is per-video calibrated. The only
difference is that dataset3 computes additional features (lateral_presence,
near_ego_vehicle_count, bbox_cx_std) that realcartest's canonical table lacks.

## Implication for Stage 11 reversal

Since there is NO camera calibration, there CANNOT be a calibration confound.
The Stage 11 cross-video reversal (score_fusion > vehicle_count on dataset3
but the reverse on realcartest) is NOT caused by different camera parameters.

The reversal is caused by a deeper structural difference:
- `score_fusion_geometry_motion` = z(bbox_area) + z(motion) — measures "big
  moving objects", which is a weak signal that happens to rank above
  vehicle_count on dataset3 (pedestrian/cyclist-dominated, 10% vehicle) but
  below vehicle_count on realcartest (vehicle-dominated, 71% vehicle).
- On a vehicle-dominated video, vehicle_count directly tracks the positive
  class; on a pedestrian-dominated video, vehicle_count is anti-predictive
  (AUROC 0.45) because most positives are NOT vehicles.

This is a **genuine cross-video generalization failure of the feature ranking**,
not a calibration artifact. The feature that works depends on the event mix,
which varies by video.

## Code locations (for reproducibility)

| What | Path |
|---|---|
| realcartest score_fusion | `experiments/v13/v13_7_multimethod_replay/scripts/v13_7_pipeline.py:145` |
| dataset3 score_fusion | `src/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/scripts/build_anchor_plan.py:145` |
| dataset3 lateral_presence | `src/garc_eval/outputs/new_video_scout_gate_v1/scripts/scout_pipeline.py:248-251` |
| dataset3 center_roi | `src/garc_eval/outputs/new_video_scout_gate_v1/scripts/scout_pipeline.py:228-243` |
| realcartest center_roi (fixed) | `experiments/v13/v13_5_pilot/scripts/21_yolo_only.py:80-83` |
| ego band config | `scripts/kinematic_proxy_code/kinematic_proxy/config.yaml:9-12` |

## Realcartest center_roi bug history

V13.5 original had a vertical-center bug (`cy = y2` instead of `(y1+y2)/2`),
fixed in `21_yolo_only.py`. The corrected version feeds V13.7. This bug affected
`center_roi_vehicle_count` on realcartest but was fixed before the canonical
table was built. It does NOT affect `score_fusion_geometry_motion` (which uses
bbox_area and motion, not center_roi).

## DECISION

`CORRIDOR_CALIBRATION_CONFOUND_RULED_OUT`

There is no camera calibration to confound. The Stage 11 cross-video reversal
is a genuine feature-ranking generalization failure caused by different event
mixes (pedestrian-dominated vs vehicle-dominated), not by calibration differences.

## Guardrail

- This audit does NOT validate the geometric features as useful — it only rules
  out one specific confound (calibration mismatch).
- The "ego-path corridor" naming is misleading; these are image-plane ROI
  heuristics, not geometric projections. The paper should use accurate naming
  (e.g., "center-region object density" not "ego-path corridor").
- A true camera-calibrated ego-path projection (IPM + lane estimation) would be
  a different feature entirely and is not implemented in this codebase.
