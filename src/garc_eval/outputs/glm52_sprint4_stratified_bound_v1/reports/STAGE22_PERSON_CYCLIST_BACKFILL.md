# Stage 22: Realcartest Person/Cyclist Feature Backfill

## Objective

Compute person_count_mean on realcartest to enable the cross-video validation
of the person proxy prior (Stage 16 could not do this because realcartest V13.7
proxy features lack person/bike class counts).

## Finding: person_count CANNOT be backfilled without YOLO reprocessing

### What realcartest YOLO extraction saved

The V13.5 YOLO extraction scripts (`20_proxy_feature_extraction.py`,
`21_yolo_only.py`) extract:
- `vehicle_mask = cls in [2, 3, 5, 7]` (car, motorcycle, bus, truck)
- `object_count = len(cls_ids)` (ALL classes, including person=0, bicycle=1)
- Per-class breakdowns were NOT saved — only `vehicle_count` and `object_count`

Person class (COCO 0) and bicycle class (COCO 1) are INCLUDED in `object_count`
but NOT separately counted. The raw YOLO detection results (bounding boxes with
class IDs) were not persisted to CSV — only the aggregated feature table was saved.

### What would be needed

To compute `person_count_mean` on realcartest, we would need to either:
1. Re-run YOLOv8 on realcartest and extract per-class counts (blocked by
   "no YOLO runs" constraint in this sprint)
2. Find saved raw YOLO outputs with per-class detections (not found in the
   repository)

### What we CAN do: non_vehicle_count as a rough proxy

Since `object_count = vehicle_count + person_count + other_count`, we can
compute `non_vehicle_count = object_count - vehicle_count`. This is a rough
proxy for person+bike+other counts.

## Results: non_vehicle_count proxy on realcartest

| query | feature | auroc | n_pos |
| --- | --- | --- | --- |
| pedestrian_event | object_count_mean | 0.7549 | 13 |
| pedestrian_event | non_vehicle_count_mean (proxy) | 0.7707 | 13 |
| pedestrian_event | non_vehicle_count_max (proxy) | 0.7321 | 13 |
| pedestrian_event | yolo_vehicle_mean | 0.7172 | 13 |
| pedestrian_event | score_fusion_geometry_motion | 0.6192 | 13 |
| pedestrian_event | motion_energy_mean | 0.6989 | 13 |
| cyclist_event | object_count_mean | 0.7085 | 13 |
| cyclist_event | non_vehicle_count_mean (proxy) | 0.8257 | 13 |
| cyclist_event | non_vehicle_count_max (proxy) | 0.7925 | 13 |
| cyclist_event | yolo_vehicle_mean | 0.6398 | 13 |
| cyclist_event | score_fusion_geometry_motion | 0.4572 | 13 |
| cyclist_event | motion_energy_mean | 0.4574 | 13 |
| non_vehicle_event | object_count_mean | 0.7398 | 26 |
| non_vehicle_event | non_vehicle_count_mean (proxy) | 0.8086 | 26 |
| non_vehicle_event | non_vehicle_count_max (proxy) | 0.7714 | 26 |
| non_vehicle_event | yolo_vehicle_mean | 0.6847 | 26 |
| non_vehicle_event | score_fusion_geometry_motion | 0.5395 | 26 |
| non_vehicle_event | motion_energy_mean | 0.5808 | 26 |
| all_event | object_count_mean | 0.7382 | 94 |
| all_event | non_vehicle_count_mean (proxy) | 0.6214 | 94 |
| all_event | non_vehicle_count_max (proxy) | 0.6181 | 94 |
| all_event | yolo_vehicle_mean | 0.7109 | 94 |
| all_event | score_fusion_geometry_motion | 0.5768 | 94 |
| all_event | motion_energy_mean | 0.5218 | 94 |

## Cross-video comparison: object_count_mean (the only common feature)

| Query | dataset3 | realcartest | Direction |
|---|---|---|---|
| non_vehicle_event | 0.6384 | 0.7398 | consistent |
| pedestrian_event | 0.6300 | 0.7549 | consistent |
| cyclist_event | 0.6361 | 0.7085 | consistent |
| all_event | 0.6272 | 0.7382 | consistent |

## DECISION

`PERSON_CYCLIST_BACKFILL_BLOCKED_NO_YOLO_DATA`

## Interpretation

1. **The specific person proxy (person_count_mean, AUROC 0.81 on dataset3) CANNOT
   be validated cross-video** because the per-class YOLO counts were never saved
   for realcartest. This is a feature engineering gap, not a research finding.

2. **object_count_mean is cross-video consistent** for non_vehicle_event (strongest
   common feature on both videos). This was already established in Stage 16.

3. **non_vehicle_count (proxy)** = object_count - vehicle_count. On realcartest
   non_vehicle_event AUROC = 0.808620334089503.
   This is similar to object_count_mean, as expected (they're highly correlated).

4. **To unblock this check**: re-run YOLOv8 on realcartest with per-class count
   extraction (person=0, bicycle=1, motorcycle=3). This is YOLO reprocessing
   (not VLM), but is blocked by the "no YOLO runs" constraint in this sprint.

## Guardrail

- Do NOT claim "person proxy generalizes cross-video" — it was not tested.
- Do NOT claim "person proxy fails cross-video" — it was not tested either.
- The non_vehicle_count proxy is NOT the same as person_count — it includes
  other non-vehicle objects (traffic lights, hydrants, etc.) and its AUROC
  is not directly comparable to person_count_mean's AUROC.
- This is an engineering blocker, not a negative research result.

## Outputs

- `tables/stage22_person_cyclist_backfill.csv`
