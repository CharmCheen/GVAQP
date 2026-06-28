# INPUT_INVENTORY.md - realcartest proxy materialization v1

## Video

| Key | Value |
|---|---:|
| exists | YES |
| path | /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4 |
| size_bytes | 832786075 |
| width | 1920 |
| height | 1080 |
| fps | 24.000002 |
| frame_count | 95690 |
| duration_sec | 3987.083 |
| duration_min | 66.45 |

## Anchor And Label Tables

| Key | Value |
|---|---:|
| anchor_table_exists | YES |
| anchor_table_path | /qiuyeqing/llama_prl/G-ARC/experiments/v13/v13_7_multimethod_replay/tables/center10_anchor_grid.csv |
| anchor_rows | 399 |
| anchor_timestamp_mappable | 399 |
| anchor_time_min | 5.0 |
| anchor_time_max | 3985.0 |
| label_table_exists | YES |
| label_table_path | /qiuyeqing/llama_prl/G-ARC/experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv |
| label_rows | 399 |
| positive_labels | 94 |
| negative_labels | 305 |
| event_table_exists | YES |
| event_rows | 51 |

## Dataset3 Window Definition

- confirmed: center_time_s +/- 5 s, 10s center window, 2 fps raw bbox materialization
- Evidence: dataset3 ANCHOR_COVERAGE_REPORT.md and anchor_detection_coverage_dataset3_2fps.csv, which report center_time_s +/- 5 s and about 20 frames per anchor.
- This run will reuse anchor_time +/- 5 s as the only anchor feature window standard.

## Realcartest Label Provenance

- confirmed: V13.8 report states Qwen3-VL-32B-Instruct, V13.6 prompt, O_enter_ego_path_v0, negative-not-abstain rule, all 399 center10 anchors.
- Labels are VLM-oracle-relative, not human truth.

## YOLO And Compute Environment

| Key | Value |
|---|---:|
| yolov8n_weight_exists | YES |
| yolov8n_weight_path | /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt |
| yolov8n_weight_size_bytes | 6549796 |
| gpu_available | YES |
| gpu_raw | NVIDIA A800-SXM4-80GB, 81920 MiB, 81156 MiB |
| need_run_yolo | YES - no existing realcartest full raw bbox 2fps table was found in the requested output directory. |

| Package | Available | Version | Error |
|---|---|---:|---|
| torch | YES | 2.12.0+cu126 |  |
| cv2 | YES | 4.13.0 |  |
| ultralytics | YES | 8.4.51 |  |
| pandas | YES | 2.2.2 |  |
| numpy | YES | 2.2.6 |  |
| pyarrow | YES | 24.0.0 |  |
| sklearn | YES | 1.7.2 |  |

## Camera / View Metadata

- No explicit camera mount metadata found beyond dashcam-style realcartest filename/path and V13 reports.

## Oracle Call Policy

- This task will not call any VLM, Qwen, GLM, LLM, human oracle, or prompt-tuning workflow.
- Existing Qwen labels are read only and used solely for feasibility evaluation.

## Phase 0 Decision

PASS - proceed to 60-second YOLO smoke test.
