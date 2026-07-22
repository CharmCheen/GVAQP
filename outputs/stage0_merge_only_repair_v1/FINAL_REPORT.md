# Stage 0 Merge-only Repair Ablation Final Report

## 1. Task scope

This task only runs a merge-only repair ablation. It adds no oracle calls, does not change Ours selection, does not run model inference, and does not implement SEHS or any planner.

## 2. Input files

- unit CSV: `outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv`
- reference events: `outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv`
- Ours original segments: `outputs/ours_vs_baselines_realcartest_v1/ours_outputs/ours_frozen_late_aqp_b{B}_s{seed}/segments.csv`
- Ours original oracle_log: `outputs/ours_vs_baselines_realcartest_v1/ours_outputs/ours_frozen_late_aqp_b{B}_s{seed}/oracle_log.csv`
- evaluator scripts: `outputs/real_video_protocol_pilot_v1_metric_repair/scripts/recompute_repaired_metrics.py`, `outputs/ours_vs_baselines_realcartest_v1/scripts/run_ours_vs_baselines.py`
- reports: `outputs/real_video_protocol_pilot_v1/REAL_VIDEO_PROTOCOL_PILOT_REPORT.md`, `outputs/real_video_protocol_pilot_v1_metric_repair/METRIC_REPAIR_REPORT.md`, `outputs/ours_vs_baselines_realcartest_v1/COMPARISON_REPORT.md`

## 3. Method

Ours original merge is read as-is from existing budget-specific `segments.csv` files. `repaired_confirmed_only` seeds events only from queried positive anchors and treats queried negatives as barriers. `repaired_selected_expand` uses the same anchors, then allows at most one-unit selected/proxy boundary expansion without crossing queried negative barriers. Both repaired variants use split-by-default construction: adjacent positive anchors merge only when `G_max`, proxy-valley, negative-barrier, and duration-prior checks all pass. Duplicate suppression uses temporal NMS only for highly overlapping predictions at IoU 0.7.

## 4. Main results

|   budget | method                   |   event_detection@overlap_any_precision |   event_detection@overlap_any_recall |   event_detection@overlap_any_F1 |   unique_reference_event_recall |   predicted_segment_count |   prediction_count_error |   avg_segment_duration |   max_segment_duration |   overmerge_multiplicity |   matched_mean_iou |   iou_0.3 |   iou_0.5 |   overcoverage_ratio |
|---------:|:-------------------------|----------------------------------------:|-------------------------------------:|---------------------------------:|--------------------------------:|--------------------------:|-------------------------:|-----------------------:|-----------------------:|-------------------------:|-------------------:|----------:|----------:|---------------------:|
|        5 | ours_original            |                                  0.3333 |                                 0.06 |                           0.1014 |                            0.06 |                       3.8 |                     16.2 |                13.3333 |                     22 |                   0.3333 |             0.1462 |    0      |    0      |               0.3745 |
|        5 | repaired_confirmed_only  |                                  1      |                                 0.06 |                           0.1126 |                            0.06 |                       1.2 |                     18.8 |                18      |                     18 |                   1      |             0.1508 |    0      |    0      |               0.1498 |
|        5 | repaired_selected_expand |                                  1      |                                 0.06 |                           0.1126 |                            0.06 |                       1.2 |                     18.8 |                36      |                     38 |                   1      |             0.2589 |    0      |    0      |               0.2996 |
|       10 | ours_original            |                                  0.3667 |                                 0.14 |                           0.2022 |                            0.14 |                       7.6 |                     12.4 |                13.3333 |                     30 |                   0.3667 |             0.3967 |    0.1297 |    0.0571 |               0.7491 |
|       10 | repaired_confirmed_only  |                                  1      |                                 0.14 |                           0.2451 |                            0.14 |                       2.8 |                     17.2 |                17.3333 |                     30 |                   1      |             0.4014 |    0.1573 |    0.0696 |               0.3596 |
|       10 | repaired_selected_expand |                                  1      |                                 0.14 |                           0.2451 |                            0.14 |                       2.8 |                     17.2 |                35.3333 |                     50 |                   1      |             0.2691 |    0.1573 |    0      |               0.7491 |
|       20 | ours_original            |                                  0.4556 |                                 0.2  |                           0.2778 |                            0.2  |                       8.8 |                     11.2 |                22.7778 |                     50 |                   0.4556 |             0.278  |    0.1389 |    0.0695 |               1.4981 |
|       20 | repaired_confirmed_only  |                                  0.8    |                                 0.2  |                           0.32   |                            0.2  |                       5   |                     15   |                18      |                     40 |                   1      |             0.359  |    0.16   |    0.16   |               0.6742 |
|       20 | repaired_selected_expand |                                  0.8    |                                 0.2  |                           0.32   |                            0.2  |                       5   |                     15   |                33.6    |                     60 |                   1      |             0.3823 |    0.224  |    0.08   |               1.2584 |
|       50 | ours_original            |                                  0.471  |                                 0.55 |                           0.5072 |                            0.66 |                      23.4 |                      3.4 |                21.4078 |                    100 |                   0.5657 |             0.2519 |    0.221  |    0.129  |               3.7453 |
|       50 | repaired_confirmed_only  |                                  0.9273 |                                 0.64 |                           0.7568 |                            0.66 |                      13.8 |                      6.2 |                15.4264 |                     40 |                   1.0308 |             0.2747 |    0.2835 |    0.2126 |               1.588  |
|       50 | repaired_selected_expand |                                  0.9273 |                                 0.64 |                           0.7568 |                            0.66 |                      13.8 |                      6.2 |                24.9963 |                     50 |                   1.0308 |             0.2804 |    0.2243 |    0.1419 |               2.5768 |
|       80 | ours_original            |                                  0.507  |                                 0.47 |                           0.487  |                            0.77 |                      18.6 |                      1.8 |                43.2847 |                    210 |                   0.8326 |             0.1795 |    0.1243 |    0.0519 |               5.9925 |
|       80 | repaired_confirmed_only  |                                  0.939  |                                 0.77 |                           0.8459 |                            0.77 |                      16.4 |                      3.6 |                15.4926 |                     40 |                   1      |             0.2713 |    0.3297 |    0.2748 |               1.9026 |
|       80 | repaired_selected_expand |                                  0.939  |                                 0.77 |                           0.8459 |                            0.77 |                      16.4 |                      3.6 |                18.0515 |                     50 |                   1      |             0.3018 |    0.3297 |    0.2748 |               2.2172 |
|      100 | ours_original            |                                  0.5364 |                                 0.28 |                           0.3669 |                            1    |                      10.4 |                      9.6 |                97.4747 |                    478 |                   1.9495 |             0.1105 |    0.0258 |    0      |               7.4906 |
|      100 | repaired_confirmed_only  |                                  0.9524 |                                 1    |                           0.9756 |                            1    |                      21   |                      1   |                15.2381 |                     40 |                   1      |             0.2352 |    0.2927 |    0.2927 |               2.397  |
|      100 | repaired_selected_expand |                                  0.9524 |                                 1    |                           0.9756 |                            1    |                      21   |                      1   |                16.1905 |                     50 |                   1      |             0.2451 |    0.2927 |    0.2927 |               2.5468 |

## 5. B=100 diagnosis

1. Original Ours shows destructive overmerge: B=100 mean max duration is 478.000s and overmerge_multiplicity is 1.949.
2. Repaired best variant is `repaired_confirmed_only` with avg/max duration 15.238s / 40.000s.
3. B=100 F1 changes from 0.367 to 0.976.
4. Prediction count error changes from 9.600 to 1.000.
5. Overmerge_multiplicity changes from 1.949 to 1.000.
6. Best variant: `repaired_confirmed_only`.
7. Repair oversplit indication: no.

## 6. Sensitivity

B=100 sensitivity summary:

| method                   |   budget |   f1_min |   f1_max |   avg_duration_min |   avg_duration_max |   overmerge_min |   overmerge_max |   rows |
|:-------------------------|---------:|---------:|---------:|-------------------:|-------------------:|----------------:|----------------:|-------:|
| repaired_confirmed_only  |      100 |   0.9756 |   0.9756 |            15.2381 |            15.2381 |               1 |               1 |     24 |
| repaired_selected_expand |      100 |   0.9756 |   0.9756 |            16.1905 |            16.1905 |               1 |               1 |     24 |

Sensitivity spans `G_max` in {1, 2}, `D_core_max` in {30s, 40s}, `D_seg_max` in {50s, 60s}, and `low_proxy_quantile` in {0.2, 0.3, 0.4}. Full results are in `sensitivity_results.csv`.

## 7. Decision

MERGE_REPAIR_GO_FOR_SEHS_V0

Sanity failures: 0. Sanity warnings: 0. Full sanity results are in `sanity_checks.md`.

## 8. Next step

Implement only the minimal temporal event-hypothesis planner next, to validate low-budget unique event discovery.
