# Reference / Unit Protocol Audit

## Inputs

- Units: `frame_scores_adapter_ready.csv`
- References: `reference_segments_adapter_ready.csv`

## Coverage Summary

| check | value |
|---|---:|
| reference_events | 20 |
| units | 120 |
| oracle_positive_units | 32 |
| references_with_any_overlapping_unit | 20 |
| references_with_positive_unit | 20 |
| positive_units_outside_any_reference | 0 |
| references_shorter_than_2s | 14 |

## Oracle Upper Bounds

| upper_bound_type   |   iou_threshold |   num_segments |   segment_recall |   segment_precision |   segment_f1 |   mean_iou |   matched_pairs |
|:-------------------|----------------:|---------------:|-----------------:|--------------------:|-------------:|-----------:|----------------:|
| evidence-core      |             0.1 |             20 |              0.3 |                 0.3 |          0.3 |   0.638333 |               6 |
| reference-closure  |             0.1 |             20 |              1   |                 1   |          1   |   1        |              20 |
| evidence-core      |             0.2 |             20 |              0.3 |                 0.3 |          0.3 |   0.638333 |               6 |
| reference-closure  |             0.2 |             20 |              1   |                 1   |          1   |   1        |              20 |
| evidence-core      |             0.3 |             20 |              0.3 |                 0.3 |          0.3 |   0.638333 |               6 |
| reference-closure  |             0.3 |             20 |              1   |                 1   |          1   |   1        |              20 |
| evidence-core      |             0.4 |             20 |              0.3 |                 0.3 |          0.3 |   0.638333 |               6 |
| reference-closure  |             0.4 |             20 |              1   |                 1   |          1   |   1        |              20 |
| evidence-core      |             0.5 |             20 |              0.3 |                 0.3 |          0.3 |   0.638333 |               6 |
| reference-closure  |             0.5 |             20 |              1   |                 1   |          1   |   1        |              20 |

## Interpretation

- Every reference event is covered by at least one 10s unit.
- Every reference event contains at least one pseudo-oracle-positive unit.
- No positive unit falls outside all reference events in this mapped universe.
- Evidence-core upper bound at IoU=0.5 is 0.300 recall / 0.300 precision / 0.300 F1.
- Reference-closure diagnostic upper bound at IoU=0.5 is 1.000 recall / 1.000 precision / 1.000 F1.

## Required Answers

- Reference event coverage by unit grid: yes, 20/20 references overlap units.
- Positive units inside references: yes, 20/20 references contain positive units.
- Positive units outside references: no, 0/32 positive units are outside all references.
- Current evaluation is better suited to event detection recall plus boundary quality than boundary-level IoU alone. Many references are point-anchor or sub-2s events while units are 10s bins, so IoU=0.5 penalizes valid detection evidence.
- Baseline pilot decision: RUN_BASELINE_PILOT.

Diagnostic rule result: evidence-core IoU=0.5 remains low while reference coverage and reference-closure are high. This means the protocol should separate event detection recall from boundary quality before formal benchmark use.
