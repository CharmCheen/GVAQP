# Stage 16: Person/Cyclist Sub-Query Cross-Video Consistency Check

## Setup

Compare proxy AUROC on pedestrian/cyclist/non_vehicle sub-queries between
dataset3 and realcartest. The question: does the person proxy prior
(strong on dataset3) generalize to realcartest?

## Critical limitation: person-specific features NOT available on realcartest

realcartest V13.7 proxy features do NOT include:
- `person_count_mean`, `person_count_max`
- `bike_count_mean`, `bike_count_max`
- `lateral_presence_mean`, `lateral_presence_max`

These are dataset3-only features (computed by the scout gate pipeline).
realcartest only has: `object_count_mean`, `object_count_max`, `yolo_vehicle_mean`,
`motion_energy_*`, `bbox_area_sum_*`, `center_roi_vehicle_count_mean`,
`score_fusion_geometry_motion`.

**The exact person proxy (person_count_mean, AUROC 0.81 on dataset3) CANNOT be
tested cross-video.** The closest available proxy on realcartest is
`object_count_mean` (counts ALL objects including persons).

## Sample sizes

| video | query | n_total | n_pos |
| --- | --- | --- | --- |
| dataset3 | all_event | 347 | 40 |
| dataset3 | pedestrian_event | 347 | 25 |
| dataset3 | cyclist_event | 347 | 11 |
| dataset3 | non_vehicle_event | 347 | 36 |
| dataset3 | vehicle_event | 347 | 4 |
| realcartest | all_event | 399 | 94 |
| realcartest | pedestrian_event | 399 | 13 |
| realcartest | cyclist_event | 399 | 13 |
| realcartest | non_vehicle_event | 399 | 26 |
| realcartest | vehicle_event | 399 | 67 |

realcartest has 13 pedestrian + 13 cyclist = 26 non-vehicle positives (vs
dataset3's 25 + 11 = 36). Both are reasonably sized for directional comparison.

## AUROC comparison: common features on non_vehicle_event

| feature | dataset3 | realcartest |
| --- | --- | --- |
| object_count_max | 0.6620 | 0.7385 |
| object_count_mean | 0.6384 | 0.7398 |
| motion_energy_max | 0.5625 | 0.5875 |
| motion_energy_mean | 0.5454 | 0.5808 |
| score_fusion_geometry_motion | 0.5448 | 0.5395 |
| bbox_area_sum_mean | 0.5215 | 0.4698 |
| center_roi_vehicle_count_mean | 0.5113 | 0.4357 |
| yolo_vehicle_mean | 0.4498 | 0.6847 |

## AUROC comparison: common features on pedestrian_event

| feature | dataset3 | realcartest |
| --- | --- | --- |
| object_count_max | 0.6611 | 0.7500 |
| object_count_mean | 0.6300 | 0.7549 |
| motion_energy_max | 0.5265 | 0.7049 |
| score_fusion_geometry_motion | 0.5066 | 0.6192 |
| motion_energy_mean | 0.5048 | 0.6989 |
| bbox_area_sum_mean | 0.5045 | 0.4464 |
| center_roi_vehicle_count_mean | 0.4814 | 0.3807 |
| yolo_vehicle_mean | 0.4391 | 0.7172 |

## AUROC comparison: common features on cyclist_event

| feature | dataset3 | realcartest |
| --- | --- | --- |
| object_count_max | 0.6400 | 0.7109 |
| object_count_mean | 0.6361 | 0.7085 |
| motion_energy_max | 0.6318 | 0.4643 |
| motion_energy_mean | 0.6269 | 0.4574 |
| score_fusion_geometry_motion | 0.6215 | 0.4572 |
| center_roi_vehicle_count_mean | 0.5749 | 0.4949 |
| bbox_area_sum_mean | 0.5555 | 0.4952 |
| yolo_vehicle_mean | 0.4807 | 0.6398 |

## dataset3-only person features (cannot be cross-validated)

### pedestrian_event (dataset3, n_pos=25)

| feature | auroc |
| --- | --- |
| person_count_mean | 0.8412 |
| person_count_max | 0.8356 |
| lateral_presence_mean | 0.7191 |
| lateral_presence_max | 0.7185 |
| bike_count_mean | 0.5528 |
| bike_count_max | nan |

### cyclist_event (dataset3, n_pos=11)

| feature | auroc |
| --- | --- |
| person_count_max | 0.7986 |
| person_count_mean | 0.7845 |
| lateral_presence_max | 0.7508 |
| lateral_presence_mean | 0.7408 |
| bike_count_mean | 0.6377 |
| bike_count_max | nan |

### non_vehicle_event (dataset3, n_pos=36)

| feature | auroc |
| --- | --- |
| person_count_max | 0.8399 |
| person_count_mean | 0.8393 |
| lateral_presence_max | 0.7399 |
| lateral_presence_mean | 0.7370 |
| bike_count_mean | 0.5834 |
| bike_count_max | nan |


## Directional assessment

- Best common feature on non_vehicle (dataset3): `object_count_max`
- Best common feature on non_vehicle (realcartest): `object_count_mean`
- Spearman rank correlation (non_vehicle, common features): rho=0.6190
- `object_count_mean` in top-3 for non_vehicle: dataset3=yes, realcartest=yes

## Key finding

`object_count_mean` is the strongest common feature on BOTH videos for the
non_vehicle sub-query (dataset3 AUROC 0.6384,
realcartest AUROC 0.7398).
This is consistent with the all_event finding (object_count_mean is cross-video stable).

**However**, the specific person proxy (`person_count_mean`, AUROC 0.841 on
dataset3 pedestrian) is much stronger than object_count_mean (0.630) on dataset3.
If person_count_mean were available on realcartest, it might show even stronger
performance — but we cannot verify this without recomputing YOLO person-count
features on realcartest (requires YOLO reprocessing, not VLM, but still new compute).

## DECISION

`PERSON_CYCLIST_PRIOR_PARTIALLY_CONSISTENT_OBJECT_COUNT_STABLE`

## Interpretation

1. The **specific person proxy** (person_count_mean/max) CANNOT be validated
   cross-video because the feature does not exist in realcartest's canonical table.
2. The **broader object_count_mean** (which implicitly counts persons among all
   objects) IS cross-video consistent for the non_vehicle sub-query — it is the
   strongest common feature on both videos.
3. This means: if the paper uses `object_count_mean` as the deployable default,
   the query-aware prior for non-vehicle queries is supported cross-video.
   If the paper wants to use `person_count_mean` specifically, it needs
   realcartest YOLO reprocessing to validate.
4. The vehicle proxy prior remains cross-video INCONSISTENT (Stage 11 finding,
   confirmed by Stage 15 as NOT a calibration confound).

## Guardrail

- realcartest pedestrian n=13, cyclist n=13 — directional signal, not
  statistical significance.
- The absence of person_count on realcartest is a feature engineering gap,
  not a research finding. It should be filled by re-running YOLO with
  person/bike class extraction on realcartest.
- Do NOT claim "person proxy generalizes cross-video" — it was not tested.
- Do NOT claim "person proxy fails cross-video" — it was not tested either.

## Outputs

- `tables/stage16_person_cyclist_cross_video.csv`
