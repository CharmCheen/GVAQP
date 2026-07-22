# Metric Repair Report

## Scope

This repair only recomputes evaluation metrics from existing CSV outputs under `outputs/real_video_protocol_pilot_v1`. It does not rerun ARC/SUPG/ABae selection, does not modify baseline algorithms, and does not call GPU, VLM, YOLO, training, download, or model code.

## What Changed

The repaired protocol separates:

- Event detection: whether a predicted segment hits a VLM-defined reference event under a detection rule.
- Boundary quality: how well detected predictions align with reference boundaries.

The old segment IoU@0.5 metric is retained as `strict_boundary_iou_0.5_*`, not as the sole primary metric. The old matched-pair `mean_iou` concept is reported as `matched_mean_iou`, and the new `all_reference_best_iou_mean` includes every reference event, including misses.

Prediction boundaries are canonicalized from `source_frame_ids` back to `frame_scores_adapter_ready.csv` units when possible. This avoids treating proxy-only outputs as unit-index point segments when the input contains 10s unit boundaries.

## Why IoU@0.5 Made The Upper Bound 0.30

The selected universe uses 10s units, while 14/20 reference events are point-anchor or shorter than 2s. A 0.7s reference inside a 10s positive unit has IoU around 0.07 even when there is real temporal overlap. Therefore evidence-core segments can detect the event but fail strict boundary IoU@0.5. This is a granularity mismatch, not proof that the pseudo-oracle evidence is absent.

## Oracle Upper Bound Re-evaluation

| method                                    | detection_rule          |   event_detection_recall |   event_detection_precision |   event_detection_f1 |   matched_mean_iou |   all_reference_best_iou_mean |
|:------------------------------------------|:------------------------|-------------------------:|----------------------------:|---------------------:|-------------------:|------------------------------:|
| Oracle-positive evidence-core upper bound | overlap_any             |                      1   |                         1   |                  1   |             0.238  |                         0.238 |
| Oracle-positive evidence-core upper bound | overlap_min_seconds_1.0 |                      0.3 |                         0.3 |                  0.3 |             0.6383 |                         0.238 |
| Oracle-positive evidence-core upper bound | iou_0.1                 |                      0.3 |                         0.3 |                  0.3 |             0.6383 |                         0.238 |
| Oracle-positive evidence-core upper bound | iou_0.3                 |                      0.3 |                         0.3 |                  0.3 |             0.6383 |                         0.238 |
| Oracle-positive evidence-core upper bound | iou_0.5                 |                      0.3 |                         0.3 |                  0.3 |             0.6383 |                         0.238 |
| Reference-closure diagnostic upper bound  | overlap_any             |                      1   |                         1   |                  1   |             1      |                         1     |
| Reference-closure diagnostic upper bound  | overlap_min_seconds_1.0 |                      0.3 |                         0.3 |                  0.3 |             1      |                         1     |
| Reference-closure diagnostic upper bound  | iou_0.1                 |                      1   |                         1   |                  1   |             1      |                         1     |
| Reference-closure diagnostic upper bound  | iou_0.3                 |                      1   |                         1   |                  1   |             1      |                         1     |
| Reference-closure diagnostic upper bound  | iou_0.5                 |                      1   |                         1   |                  1   |             1      |                         1     |

Oracle-positive evidence-core upper bound:

- `overlap_any` recall/F1: 1.000 / 1.000
- `overlap_min_seconds_1.0` recall/F1: 0.300 / 0.300
- `iou_0.5` recall/F1: 0.300 / 0.300

Reference-closure remains diagnostic only: it uses reference boundaries after knowing a positive unit exists inside the event, so it must not be treated as a baseline.

## Recommended Main Metric

Use `overlap_any` as the formal primary event-detection metric for this 10s-unit pilot. It is the only rule that is invariant to the 0.7s point-anchor references and directly asks whether the returned segment intersects the VLM-defined event.

Use `overlap_min_seconds_1.0` as a sensitivity metric. It is stricter, but it will intentionally miss sub-1s point-anchor events even when a positive 10s unit overlaps them.

Keep `iou_0.1`, `iou_0.3`, and `iou_0.5` as boundary-strict diagnostics, not primary event detection metrics for this unit granularity.

## Boundary Quality Role

Boundary quality should be a secondary metric. The pilot's unit granularity is 10s, while many references are sub-second point anchors. Boundary metrics are still useful to expose overcoverage and duration mismatch, but they should not decide event discovery success until either finer units or reannotated boundary spans are available.

## Baseline Re-evaluation

Best baseline rows under `overlap_min_seconds_1.0`:

| method                    |   max_detection_recall |   max_detection_precision |   max_detection_f1 |   max_strict_boundary_iou_0_5_f1 |   runs |
|:--------------------------|-----------------------:|--------------------------:|-------------------:|---------------------------------:|-------:|
| ABae-stratified-confirmed |                   0.25 |                    1      |             0.2941 |                           0.1765 |      4 |
| ARC-refinement            |                   0.25 |                    0.25   |             0.25   |                           0      |      4 |
| SUPG-RT-confirmed-only    |                   0.15 |                    0.75   |             0.25   |                           0.087  |      4 |
| ARC-proxy-only            |                   0.25 |                    0.2381 |             0.2439 |                           0      |      4 |
| SUPG-RT-all-selected      |                   0.05 |                    1      |             0.0952 |                           0      |      4 |

Full repaired metrics are in `baseline_repaired_metrics.csv`.

## Per-reference Diagnosis

`per_reference_detection_matrix.csv` records oracle upper-bound detection and every baseline/budget detection flag per reference. It should be used to inspect which events are found only by overlap-level detection and which survive stricter IoU thresholds.

## Validation

| status | count |
|---|---:|
| PASS | 31 |
| FAIL | 0 |

Validation covered CSV readability, required columns, budget accounting, and expected method/budget coverage.

## Decision

Decision: `GO_FORMAL_BASELINE_WITH_DETECTION_METRIC`.

Reason: the repaired event-detection protocol recovers the oracle-positive upper bound under overlap-based detection, while strict boundary IoU remains correctly exposed as a secondary quality diagnostic. Formal baseline comparison can proceed if the main table uses event detection recall/F1, preferably `overlap_any`, with boundary quality reported separately.

## Next Steps

1. Use `overlap_any` as the main event detection metric for the 10s-unit formal baseline run.
2. Report `overlap_min_seconds_1.0`, `iou_0.1`, `iou_0.3`, and `strict_boundary_iou_0.5` as sensitivity or boundary diagnostics.
3. If boundary-level claims are needed, generate finer units or reannotate reference spans before using IoU@0.5 as a primary metric.
