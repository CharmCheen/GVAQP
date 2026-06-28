# FINAL_SUMMARY.md - realcartest proxy materialization v1

## Oracle And Compute Policy

| Key | Value |
|---|---:|
| called_any_vlm | NO |
| called_yolo | YES |
| produced_new_oracle_labels | NO |
| gpu_available | YES |
| gpu_raw | NVIDIA A800-SXM4-80GB, 81920 MiB, 81156 MiB |

## Video

| Key | Value |
|---|---:|
| path | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4 |
| width | 1920 |
| height | 1080 |
| fps | 24.000002 |
| duration_sec | 3987.083 |
| duration_min | 66.45 |

## Window And Label Provenance

- Dataset3 window definition confirmed: anchor_time +/- 5 s, 10s center window, 2 fps raw bbox materialization.
- Realcartest labels: confirmed V13.8 Qwen3-VL-32B-Instruct, V13.6 O_enter_ego_path_v0 prompt, negative-not-abstain rule.
- All evaluation labels remain VLM-oracle-relative, not human truth.

## Materialization

| Key | Value |
|---|---:|
| sample_fps | 2.0 |
| processed_frames | 7975 |
| failed_frames | 0 |
| total_detections | 48331 |
| vehicle_like_detections | 44236 |
| person_detections | 2650 |

## Anchor And Labeled Coverage

| Key | Value |
|---|---:|
| anchor_rows | 399 |
| anchor_rows_with_features | 399 |
| labeled_anchor_rows | 399 |
| positive_anchor_rows | 94 |
| feature_warning_rows | 0 |

## L3 Feasibility

| Key | Value |
|---|---:|
| object_count_mean_auc | 0.756 |
| precision_at_20 | 0.800 |
| recall_at_20 | 0.170 |
| ready_for_strategy7_l3_validation | YES |

## High-Selectivity Scout

- Scout predicates evaluated: 7
- Circular definition warning: NONE
- See `tables/realcartest_high_selectivity_predicate_scout.csv` for per-predicate counts and Qwen-positive rates.

## Autonomous Judgments

- Mapped requested garc_eval/outputs path to src/garc_eval/outputs because this checkout's active garc_eval output tree lives there.
- Used dataset3-confirmed anchor_time +/- 5 s window rather than an unconfirmed default.
- Defined vehicle-like COCO classes as bicycle/car/motorcycle/bus/truck to support the heterogeneous predicate.
- Computed lateral presence from image thirds because no ego-corridor annotations are available in raw bbox materialization.

## Final Decision

`REALCARTEST_PROXY_READY_FOR_SECOND_VIDEO_VALIDATION`

realcartest_proxy_materialization_complete=true