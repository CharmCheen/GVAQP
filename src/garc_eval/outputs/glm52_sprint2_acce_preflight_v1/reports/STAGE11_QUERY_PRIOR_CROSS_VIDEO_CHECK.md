# Stage 11: Query-Aware Proxy Prior Cross-Video Generalization Check

## Setup

Compare proxy AUROC direction between dataset3 (347 anchors, 40 positives, 4 vehicle)
and realcartest V13.8 (399 anchors, 94 positives, 67 vehicle).

**Critical limitation:** realcartest V13.7 proxy features do NOT include
`person_count_mean`, `person_count_max`, `bike_count_mean`, `lateral_presence_max`,
`bbox_cx_std_mean`. Only vehicle/object/motion/bbox features are available in both
videos. **The person proxy cross-video check CANNOT be performed.**

## Common features compared

score_fusion_geometry_motion, object_count_mean, object_count_max, yolo_vehicle_mean, motion_energy_mean, motion_energy_max, bbox_area_sum_mean, center_roi_vehicle_count_mean

## Vehicle sub-query AUROC comparison (key query)

| feature | dataset3 (n_pos=4) | realcartest (n_pos=67) | direction |
|---|---|---|---|
| score_fusion_geometry_motion | 0.5853 | 0.5822 | same |
| object_count_mean | 0.5095 | 0.7019 | same |
| object_count_max | 0.5058 | 0.6884 | same |
| yolo_vehicle_mean | 0.4625 | 0.6919 | DIFFERENT |
| motion_energy_mean | 0.5510 | 0.4916 | DIFFERENT |
| motion_energy_max | 0.5437 | 0.4915 | DIFFERENT |
| bbox_area_sum_mean | 0.6108 | 0.6387 | same |
| center_roi_vehicle_count_mean | 0.6112 | 0.5744 | same |

## Spearman rank correlation of feature AUROC rankings (vehicle query)

Shared features: 8. Spearman rho = -0.5238 (p=0.1827).
For all_event query: rho = 0.3095 (p=0.4556).

## Key directional test

- `score_fusion_geometry_motion` > `yolo_vehicle_mean` (vehicle_count proxy) on vehicle query?
  - dataset3: 0.5853 > 0.4625 = True
  - realcartest: 0.5822 > 0.6919 = False

## All-event AUROC comparison (sanity check)

| feature | dataset3 (n_pos=40) | realcartest (n_pos=94) |
|---|---|---|
| score_fusion_geometry_motion | 0.5504 | 0.5768 |
| object_count_mean | 0.6272 | 0.7382 |
| object_count_max | 0.6484 | 0.7292 |
| yolo_vehicle_mean | 0.4501 | 0.7109 |
| motion_energy_mean | 0.5471 | 0.5218 |
| motion_energy_max | 0.5619 | 0.5244 |
| bbox_area_sum_mean | 0.5320 | 0.5955 |
| center_roi_vehicle_count_mean | 0.5228 | 0.5349 |

## Person proxy: dataset3-only finding

person_count_mean/max NOT available in realcartest V13.7 proxy features. Person proxy cross-video check CANNOT be performed. The person proxy finding (AUROC 0.81 on dataset3 all_event) remains dataset3-only.

## DECISION

`QUERY_PRIOR_CROSS_VIDEO_INCONSISTENT`

## Interpretation and guardrails

- The vehicle-query direction (`score_fusion > yolo_vehicle_mean`) is
  INCONSISTENT across videos.
- **BUT**: dataset3 vehicle n=4 is too small to trust the direction. The realcartest
  result (n=67) is the stronger signal. If realcartest alone shows score_fusion > 
  vehicle_count, that is the more reliable directional signal.
- Person proxy CANNOT be validated cross-video due to missing features in realcartest.
  The paper must state "person proxy prior is validated on dataset3 only" unless
  person-count features are recomputed for realcartest (requires YOLO reprocessing,
  which is outside the no-new-VLM constraint).
- The all-event Spearman rho=0.3095 shows feature ranking
  consistency across videos at the all-event level.
- Do NOT claim "query-aware proxy prior is a universal rule" from this check alone.

## Outputs

- `tables/stage11_cross_video_auroc.csv`
