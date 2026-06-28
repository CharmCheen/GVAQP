# Stage 10: Vehicle Query Geometric Proxy Check

## Setup

Sub-query: `involved_object == 'vehicle' AND is_positive` on dataset3.
This isolates the 4 vehicle-involved positives from the 40 total positives.

**Sample size: n_pos=4, n_neg=343. EXTREMELY SMALL N.**
All results below are **directional signals only**. No statistical significance
can be claimed. These numbers must NOT be used to conclude "P1 geometric hypothesis
is valid/invalid" — only as a direction indicator for Task 2 cross-video check.

## AUROC on vehicle sub-query

| feature | auroc | auprc | n_pos | n_neg | top4_yield | note |
| --- | --- | --- | --- | --- | --- | --- |
| score_fusion_geometry_motion | 0.5853 | 0.0535 | 4 | 343 | 0 |  |
| motion_energy_mean | 0.5510 | 0.0271 | 4 | 343 | 0 |  |
| person_count_max | 0.5346 | 0.0173 | 4 | 343 | 0 |  |
| object_count_mean | 0.5095 | 0.0145 | 4 | 343 | 0 |  |
| vehicle_count_mean | 0.4625 | 0.0133 | 4 | 343 | 0 |  |
| lateral_presence_max | 0.4614 | 0.0159 | 4 | 343 | 0 |  |

## Directional assessment

- Best geometric feature AUROC: 0.5853
- `vehicle_count_mean` AUROC: 0.4625 (baseline comparator)
- Geometric advantage: +0.1228

Threshold for "promising": geometric AUROC > vehicle_count_mean AUROC + 0.05.

## DECISION

`GEOMETRIC_PROXY_PROMISING_LOW_N`

## Guardrail notice

- n=4 positives. A single flip changes AUROC by ~0.25. These numbers are noise-sensitive.
- Do NOT write "geometric proxy works for vehicles" in the paper based on this alone.
- This result only justifies (or not) running the cross-video check in Stage 11.
- If Stage 11 (realcartest, 67 vehicle positives) shows the same direction,
  the combined signal is stronger but still not a formal proof.

## Outputs

- `tables/stage10_vehicle_query_auroc.csv`
