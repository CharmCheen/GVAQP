# Ours Vs Baselines Comparison Report

## Scope

This run compares Ours and ARC/SUPG/ABae on the same pilot dataset, same unit CSV, same reference CSV, same budgets, and the repaired event-detection metric protocol. It does not call GPU, VLM, YOLO, training, download, or proxy generation.

## Dataset

- Universe: `realcartest_2000_3200`
- Duration: 20 minutes
- Units: 120 ten-second units
- Reference events: 20 VLM-defined reference events
- Labels: pseudo-oracle unit labels, not human ground truth

## Metric Protocol

The primary metric is `event_detection@overlap_any`. Strict IoU@0.5 is reported as `strict_boundary_iou_0.5` and used only as a boundary diagnostic. `overlap_any` means a predicted segment temporally intersects a VLM-defined reference event; it does not imply accurate boundary localization.

## Method Identities

- ARC: clip refinement baseline, evaluated with threshold sweep 0.1 to 0.5.
- SUPG: recall-target record selection baseline.
- ABae: ABae-inspired stratified budget allocation baseline.
- Ours: `Ours-Frozen-LATE-AQP-v1`, a CSV replay wrapper over the repository's frozen LATE-AQP implementation. It uses proxy scores for ranking/envelope logic and reads pseudo-oracle labels only for budgeted unit calls.
- Oracle-positive evidence-core upper bound: diagnostic upper bound from all positive units, not a budget-respecting baseline.
- Reference-closure diagnostic upper bound: diagnostic only; it uses reference boundaries.

## Main Comparison

Main table file: `main_comparison_table.csv`.

Low-budget rows:

| method                                    |   event_detection_recall_mean |   event_detection_precision_mean |   event_detection_f1_mean |   duplicate_detection_rate_mean |   oracle_calls_mean |   matched_mean_iou_mean |   all_reference_best_iou_mean |   mean_overcoverage_ratio_mean |
|:------------------------------------------|------------------------------:|---------------------------------:|--------------------------:|--------------------------------:|--------------------:|------------------------:|------------------------------:|-------------------------------:|
| Ours-Frozen-LATE-AQP-v1                   |                          0.06 |                           0.3333 |                    0.1014 |                          0      |                 5   |                  0.1462 |                        0.0075 |                         4.621  |
| ARC-refinement                            |                          0.54 |                           0.5095 |                    0.5242 |                          0.0472 |                 5   |                  0.1807 |                        0.1015 |                        29.0792 |
| ARC-proxy-only                            |                          0.5  |                           0.4762 |                    0.4878 |                          0.0476 |                 0   |                  0.188  |                        0.098  |                        30.7997 |
| SUPG-RT-confirmed-only                    |                          0.03 |                           0.4    |                    0.0554 |                          0      |                 4.8 |                  0.0948 |                        0.0075 |                         1.5163 |
| ABae-stratified-confirmed                 |                          0.09 |                           1      |                    0.163  |                          0      |                 5   |                  0.1855 |                        0.0212 |                         8.287  |
| SUPG-RT-all-selected                      |                          0.2  |                           0.7722 |                    0.2623 |                          0      |                 4.8 |                  0.0836 |                        0.0282 |                        30.288  |
| Oracle-positive evidence-core upper bound |                          1    |                           1      |                    1      |                          0      |               120   |                  0.238  |                        0.238  |                        12.2702 |
| Reference-closure diagnostic upper bound  |                          1    |                           1      |                    1      |                          0      |                 0   |                  1      |                        1      |                         1      |
| Ours-Frozen-LATE-AQP-v1                   |                          0.14 |                           0.3667 |                    0.2022 |                          0      |                10   |                  0.3967 |                        0.0577 |                         8.5614 |
| ARC-refinement                            |                          0.54 |                           0.5095 |                    0.5242 |                          0.0472 |                10   |                  0.1825 |                        0.1025 |                        26.1701 |
| ARC-proxy-only                            |                          0.5  |                           0.4762 |                    0.4878 |                          0.0476 |                 0   |                  0.188  |                        0.098  |                        30.7997 |
| SUPG-RT-confirmed-only                    |                          0.09 |                           0.6    |                    0.1552 |                          0      |                 9.6 |                  0.1046 |                        0.0171 |                         6.6981 |
| ABae-stratified-confirmed                 |                          0.17 |                           1      |                    0.2874 |                          0      |                10   |                  0.165  |                        0.0295 |                         8.0007 |
| SUPG-RT-all-selected                      |                          0.09 |                           0.87   |                    0.1551 |                          0      |                 9.6 |                  0.0542 |                        0.0093 |                        30.7243 |
| Oracle-positive evidence-core upper bound |                          1    |                           1      |                    1      |                          0      |               120   |                  0.238  |                        0.238  |                        12.2702 |
| Reference-closure diagnostic upper bound  |                          1    |                           1      |                    1      |                          0      |                 0   |                  1      |                        1      |                         1      |
| Ours-Frozen-LATE-AQP-v1                   |                          0.2  |                           0.4556 |                    0.2778 |                          0      |                20   |                  0.278  |                        0.0556 |                         8.9915 |
| ARC-refinement                            |                          0.45 |                           0.6547 |                    0.5325 |                          0      |                20   |                  0.2159 |                        0.097  |                         9.4474 |
| ARC-proxy-only                            |                          0.5  |                           0.4762 |                    0.4878 |                          0.0476 |                 0   |                  0.188  |                        0.098  |                        30.7997 |
| SUPG-RT-confirmed-only                    |                          0.25 |                           0.9333 |                    0.388  |                          0.0667 |                18.6 |                  0.2194 |                        0.0571 |                         8.0078 |
| ABae-stratified-confirmed                 |                          0.26 |                           0.8929 |                    0.3957 |                          0.1071 |                20   |                  0.1979 |                        0.0498 |                         8.3909 |
| SUPG-RT-all-selected                      |                          0.05 |                           1      |                    0.0952 |                          0      |                18.6 |                  0.0423 |                        0.0056 |                        23.6686 |
| Oracle-positive evidence-core upper bound |                          1    |                           1      |                    1      |                          0      |               120   |                  0.238  |                        0.238  |                        12.2702 |
| Reference-closure diagnostic upper bound  |                          1    |                           1      |                    1      |                          0      |                 0   |                  1      |                        1      |                         1      |

Higher-budget rows:

| method                                    |   event_detection_recall_mean |   event_detection_precision_mean |   event_detection_f1_mean |   duplicate_detection_rate_mean |   oracle_calls_mean |   matched_mean_iou_mean |   all_reference_best_iou_mean |   mean_overcoverage_ratio_mean |
|:------------------------------------------|------------------------------:|---------------------------------:|--------------------------:|--------------------------------:|--------------------:|------------------------:|------------------------------:|-------------------------------:|
| Ours-Frozen-LATE-AQP-v1                   |                          0.55 |                           0.471  |                    0.5072 |                          0      |                50   |                  0.2519 |                        0.1394 |                        23.2001 |
| ARC-refinement                            |                          0.61 |                           0.7638 |                    0.6765 |                          0.0111 |                50   |                  0.2424 |                        0.1474 |                        10.1131 |
| ARC-proxy-only                            |                          0.5  |                           0.4762 |                    0.4878 |                          0.0476 |                 0   |                  0.188  |                        0.098  |                        30.7997 |
| SUPG-RT-confirmed-only                    |                          0.47 |                           0.8851 |                    0.6076 |                          0.1149 |                40.4 |                  0.1984 |                        0.096  |                         9.9407 |
| ABae-stratified-confirmed                 |                          0.59 |                           0.9033 |                    0.7102 |                          0.0967 |                50   |                  0.2497 |                        0.1443 |                        10.3538 |
| SUPG-RT-all-selected                      |                          0.05 |                           1      |                    0.0952 |                          0      |                40.4 |                  0.0423 |                        0.0056 |                        23.6686 |
| Oracle-positive evidence-core upper bound |                          1    |                           1      |                    1      |                          0      |               120   |                  0.238  |                        0.238  |                        12.2702 |
| Reference-closure diagnostic upper bound  |                          1    |                           1      |                    1      |                          0      |                 0   |                  1      |                        1      |                         1      |
| Ours-Frozen-LATE-AQP-v1                   |                          0.47 |                           0.507  |                    0.487  |                          0      |                80   |                  0.1795 |                        0.0887 |                        34.106  |
| ARC-refinement                            |                          0.77 |                           0.8569 |                    0.8029 |                          0.0265 |                80   |                  0.2648 |                        0.198  |                        10.5886 |
| ARC-proxy-only                            |                          0.5  |                           0.4762 |                    0.4878 |                          0.0476 |                 0   |                  0.188  |                        0.098  |                        30.7997 |
| SUPG-RT-confirmed-only                    |                          0.58 |                           0.895  |                    0.6991 |                          0.105  |                57.6 |                  0.2549 |                        0.146  |                         9.5488 |
| ABae-stratified-confirmed                 |                          0.83 |                           0.9561 |                    0.8862 |                          0.0439 |                80   |                  0.2349 |                        0.1915 |                        11.3456 |
| SUPG-RT-all-selected                      |                          0.05 |                           1      |                    0.0952 |                          0      |                57.6 |                  0.0423 |                        0.0056 |                        23.6686 |
| Oracle-positive evidence-core upper bound |                          1    |                           1      |                    1      |                          0      |               120   |                  0.238  |                        0.238  |                        12.2702 |
| Reference-closure diagnostic upper bound  |                          1    |                           1      |                    1      |                          0      |                 0   |                  1      |                        1      |                         1      |
| Ours-Frozen-LATE-AQP-v1                   |                          0.28 |                           0.5364 |                    0.3669 |                          0      |               100   |                  0.1105 |                        0.0356 |                        25.7132 |
| ARC-refinement                            |                          0.85 |                           0.9246 |                    0.8793 |                          0.0265 |                97   |                  0.2628 |                        0.2202 |                        10.9758 |
| ARC-proxy-only                            |                          0.5  |                           0.4762 |                    0.4878 |                          0.0476 |                 0   |                  0.188  |                        0.098  |                        30.7997 |
| SUPG-RT-confirmed-only                    |                          0.62 |                           0.9166 |                    0.7342 |                          0.0834 |                66.2 |                  0.258  |                        0.1576 |                         9.408  |
| ABae-stratified-confirmed                 |                          0.96 |                           0.9895 |                    0.9744 |                          0.0105 |               100   |                  0.246  |                        0.2359 |                        12.1669 |
| SUPG-RT-all-selected                      |                          0.05 |                           1      |                    0.0952 |                          0      |                66.2 |                  0.0423 |                        0.0056 |                        23.6686 |
| Oracle-positive evidence-core upper bound |                          1    |                           1      |                    1      |                          0      |               120   |                  0.238  |                        0.238  |                        12.2702 |
| Reference-closure diagnostic upper bound  |                          1    |                           1      |                    1      |                          0      |                 0   |                  1      |                        1      |                         1      |

## Low-budget Comparison

At B=20, Ours has F1=0.2778, ARC-refinement has F1=0.5325, and ABae has F1=0.3957 under `overlap_any`. This answers event discovery, not boundary precision.

## Higher-budget Comparison

At B=100, Ours has F1=0.3669; the oracle-positive evidence-core diagnostic upper bound has F1=1.0000. Compare `mean_overcoverage_ratio_mean` and boundary tables before claiming that a method is localizing better rather than returning longer segments.

## Boundary Quality

Boundary diagnostics are in `boundary_quality_table.csv`. The key columns are `matched_mean_iou_mean`, `all_reference_best_iou_mean`, `strict_boundary_iou_0_5_f1_mean`, and overcoverage. These should be read as secondary metrics because the protocol uses 10s units with many short VLM-defined references.

## Fairness And Leakage Audit

- All methods use `outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv`.
- All methods are evaluated against `outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv`.
- Baseline adapter core selection logic was not modified.
- Ours selection does not read reference segments.
- Ours reads `oracle_label` only for selected budgeted units.
- All budgeted methods are checked for `oracle_calls <= budget`.
- Diagnostic upper bounds are flagged separately and are not budget-respecting baselines.

## Validation

- PASS checks: 2037
- FAIL checks: 0

See `validation_checks.csv`.

## Decision

OURS_NEEDS_METHOD_FIX

## Next Steps

If this comparison is accepted as a protocol smoke benchmark, extend to more videos with the same repaired metric protocol and keep overlap-based event detection separate from boundary quality. Add ablations for the Ours audit, repair expansion, duplicate reduction, and budget allocation phases before making broader claims.
