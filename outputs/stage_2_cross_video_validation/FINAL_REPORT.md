# Stage 2 Cross-video Validation Final Report

## 1. Scope

This is frozen-parameter validation. Pilot results were used for method development; dataset3 windows are validation only. No parameters were tuned.

## 2. Inputs

| window_id          | video_id            |   time_start |   time_end | source_anchor_table                                                                                   | usable   | exclusion_reason   | baseline_output_path   | baseline_availability                        | unit_csv                                                                                                                           | reference_csv                                                                                                                            |   unit_count |   reference_event_count |   positive_unit_count |
|:-------------------|:--------------------|-------------:|-----------:|:------------------------------------------------------------------------------------------------------|:---------|:-------------------|:-----------------------|:---------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------|-------------:|------------------------:|----------------------:|
| dataset3_0_1200    | long_video_dataset3 |            0 |    1200    | src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv | True     |                    |                        | none_for_ARC_SUPG_ABae_Ours_in_stage2_format | /qiuyeqing/llama_prl/G-ARC/outputs/stage_2_cross_video_validation/derived_inputs/dataset3_0_1200_frame_scores_adapter_ready.csv    | /qiuyeqing/llama_prl/G-ARC/outputs/stage_2_cross_video_validation/derived_inputs/dataset3_0_1200_reference_segments_adapter_ready.csv    |          120 |                       6 |                     7 |
| dataset3_1200_2400 | long_video_dataset3 |         1200 |    2400    | src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv | True     |                    |                        | none_for_ARC_SUPG_ABae_Ours_in_stage2_format | /qiuyeqing/llama_prl/G-ARC/outputs/stage_2_cross_video_validation/derived_inputs/dataset3_1200_2400_frame_scores_adapter_ready.csv | /qiuyeqing/llama_prl/G-ARC/outputs/stage_2_cross_video_validation/derived_inputs/dataset3_1200_2400_reference_segments_adapter_ready.csv |          120 |                      12 |                    21 |
| dataset3_2400_3462 | long_video_dataset3 |         2400 |    3462.93 | src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv | True     |                    |                        | none_for_ARC_SUPG_ABae_Ours_in_stage2_format | /qiuyeqing/llama_prl/G-ARC/outputs/stage_2_cross_video_validation/derived_inputs/dataset3_2400_3462_frame_scores_adapter_ready.csv | /qiuyeqing/llama_prl/G-ARC/outputs/stage_2_cross_video_validation/derived_inputs/dataset3_2400_3462_reference_segments_adapter_ready.csv |          107 |                       9 |                    12 |

## 3. Methods

Evaluated MAP-anchor-only + K3 and MAP-anchor-barrier + K3 with frozen K3. Native/strengthened ARC/SUPG/ABae/Ours outputs were unavailable for these dataset3 windows and are explicitly excluded from quantitative comparison.

## 4. Main results

| window_id          | method                  |   event_F1_AUC |   B5_F1 |   B10_F1 |   B20_F1 |   B50_F1 |   B80_F1 |   B100_F1 |   max_duration |   overcoverage_ratio |   overmerge_multiplicity |   iou_0_3 |   iou_0_5 |
|:-------------------|:------------------------|---------------:|--------:|---------:|---------:|---------:|---------:|----------:|---------------:|---------------------:|-------------------------:|----------:|----------:|
| dataset3_0_1200    | MAP-anchor-barrier + K3 |       0.368421 |     0   | 0        |    0     | 0        | 1        |  1        |         5      |             1.52582  |                 0.333333 | 0.0277778 | 0.0277778 |
| dataset3_0_1200    | MAP-anchor-only + K3    |       0.526316 |     0   | 0        |    0     | 0.666667 | 0.8      |  1        |         5      |             1.52582  |                 0.5      | 0         | 0         |
| dataset3_1200_2400 | MAP-anchor-barrier + K3 |       0.574726 |     0   | 0.285714 |    0.375 | 0.526316 | 0.833333 |  0.833333 |        23.3333 |             0.914634 |                 0.833333 | 0.0453216 | 0         |
| dataset3_1200_2400 | MAP-anchor-only + K3    |       0.542145 |     0   | 0.285714 |    0.375 | 0.470588 | 0.761905 |  0.869565 |        23.3333 |             0.79607  |                 0.885185 | 0.0499736 | 0         |
| dataset3_2400_3462 | MAP-anchor-barrier + K3 |       0.704821 |     0.2 | 0.2      |    0.5   | 0.714286 | 0.941176 |  1        |        15      |             1.53631  |                 1        | 0.161998  | 0.161998  |
| dataset3_2400_3462 | MAP-anchor-only + K3    |       0.698629 |     0.2 | 0.2      |    0.5   | 0.714286 | 0.941176 |  0.941176 |        15      |             1.48976  |                 1        | 0.165266  | 0.165266  |

Aggregate:

| method                  |   mean_AUC |   median_AUC |   average_rank | wins_vs_best_strengthened_baseline   | wins_vs_best_native_baseline   |   mean_low_budget_F1_B5_10_20 |   mean_high_budget_F1_B50_80_100 |   mean_overcoverage |   mean_max_duration |   mean_iou_0.5 |
|:------------------------|-----------:|-------------:|---------------:|:-------------------------------------|:-------------------------------|------------------------------:|---------------------------------:|--------------------:|--------------------:|---------------:|
| MAP-anchor-only + K3    |   0.58903  |     0.542145 |        1.66667 | NA_baselines_unavailable             | NA_baselines_unavailable       |                      0.173413 |                         0.796152 |             1.27055 |             14.4444 |      0.0550887 |
| MAP-anchor-barrier + K3 |   0.549323 |     0.574726 |        1.33333 | NA_baselines_unavailable             | NA_baselines_unavailable       |                      0.173413 |                         0.760938 |             1.32559 |             14.4444 |      0.0632586 |

## 5. K3 BB-EM generalization

K3 satisfied duration and negative-barrier sanity checks on all dataset3 windows. Selector-agnostic baseline generalization cannot be validated because ARC/SUPG/ABae/Ours oracle logs and native outputs are unavailable for these windows.

## 6. MAP-anchor-only generalization

MAP-anchor-only can be replayed on all three dataset3 windows with frozen config. Its improvement over strengthened baselines cannot be assessed because strengthened baselines are unavailable.

## 7. MAP-anchor-barrier generalization

MAP-anchor-barrier is replayed as optional high-budget refinement. See boundedness_diagnostics.csv and failure_cases.md for overcoverage/IoU tradeoffs.

## 8. Native ARC comparison

Native ARC is unavailable for dataset3 Stage 2 windows. The pilot caveat remains: native ARC may win B<=10 overlap_any and must be reported honestly where available.

## 9. Failure cases

See `failure_cases.md`. Main limitation: missing native/strengthened baselines for dataset3 windows.

## 10. Decision

CROSS_VIDEO_WEAK_OR_INCONCLUSIVE

## 11. Next step

Collect or locate frozen-format ARC/SUPG/ABae/Ours baseline outputs for these same dataset3 windows, or run only already-approved CPU baseline replay if such scripts are part of the existing protocol. Until then, this Stage 2 result is weak/inconclusive for comparative claims.

Sanity failures: 0.
