# Stage 12: Task D AUROC Independent Audit

## Audit procedure

1. Re-loaded canonical dataset3 table from source.
2. Label encoding verified: `positive=1, negative=0` (asserted no NaN).
3. Sub-query masks rebuilt explicitly:
   - `all_event`: `is_positive`
   - `pedestrian_event`: `involved_object == 'pedestrian' AND is_positive`
   - `cyclist_event`: `involved_object == 'cyclist' AND is_positive`
   - `vehicle_event`: `involved_object == 'vehicle' AND is_positive`
   - `non_vehicle_event`: `(involved_object in ['pedestrian','cyclist']) AND is_positive`
4. AUROC computed with scipy `rankdata` (Mann-Whitney U, tie-aware).

## Sample sizes

| query | n_total | n_pos | n_neg |
| --- | --- | --- | --- |
| all_event | 347 | 40 | 307 |
| pedestrian_event | 347 | 25 | 322 |
| cyclist_event | 347 | 11 | 336 |
| vehicle_event | 347 | 4 | 343 |
| non_vehicle_event | 347 | 36 | 311 |

## Recomputed AUROC

| feature | all_event | cyclist_event | non_vehicle_event | pedestrian_event | vehicle_event |
| --- | --- | --- | --- | --- | --- |
| person_count_max | 0.8137 | 0.7986 | 0.8399 | 0.8356 | 0.5346 |
| person_count_mean | 0.8132 | 0.7845 | 0.8393 | 0.8412 | 0.5346 |
| lateral_presence_max | 0.7144 | 0.7508 | 0.7399 | 0.7185 | 0.4614 |
| object_count_mean | 0.6272 | 0.6361 | 0.6384 | 0.6300 | 0.5095 |
| bike_count_mean | 0.5839 | 0.6377 | 0.5834 | 0.5528 | 0.5700 |
| score_fusion_geometry_motion | 0.5504 | 0.6215 | 0.5448 | 0.5066 | 0.5853 |
| motion_energy_mean | 0.5471 | 0.6269 | 0.5454 | 0.5048 | 0.5510 |
| vehicle_count_mean | 0.4501 | 0.4807 | 0.4498 | 0.4391 | 0.4625 |

## Discrepancy check (threshold: 0.005)

No discrepancies found. All recomputed values match Sprint 1 Task D within 0.005.

## DECISION

`TASKD_AUROC_CONFIRMED`

## Guardrail notes

- The `vehicle_event` query has n_pos=4. AUROC on 4 positives is extremely
  high-variance (a single flip changes AUROC by ~0.25). The 0.535 vs 0.585
  difference between person_count and score_fusion on vehicle_event is
  NOT meaningful at this sample size.
- The `non_vehicle_event` query (n_pos=36) is the largest sub-query and
  the most reliable. person_count proxies AUROC 0.84 here is well-supported.
- `vehicle_count_mean` is anti-predictive on all queries (AUROC < 0.5),
  consistent with the known reversed direction.

## Outputs

- `tables/stage12_auroc_audit.csv`
