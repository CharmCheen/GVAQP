# INPUT_INVENTORY.md — Dataset3 Raw BBox Materialization Gate

## Dataset3 Video

- **Path**: `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4`
- **Size**: 1,181,062,596 bytes (1.18 GB)
- **Exists**: YES
- **Resolution**: 1920 x 1080
- **FPS**: 30/1 (30.0 fps)
- **Duration**: 3462.866 s (57.7 min)
- **Frame count**: 103,886

## Anchor Table

- **Path**: `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv`
- **Rows**: 347 anchors
- **video_id**: `dataset3`
- **center_time_s range**: 5.0 to 3462.866
- **Qwen-positive**: 40
- **Qwen-negative**: 307
- **Event clusters**: 27 (21 singleton + 6 multi-anchor)
- **Singleton positive anchors**: 21
- **Multi-anchor positive anchors**: 19

Key columns available:
- `anchor_id`, `center_time_s`, `start_time_s`, `end_time_s`
- `oracle_label`, `is_positive`
- `event_cluster_id`, `is_singleton_cluster`, `is_multi_anchor_cluster`
- `object_count_mean`, `object_count_max`
- `score_yolo_count`, `score_yolo_geometry`, `score_motion`
- `score_fusion_geometry_motion`, `score_fusion_ego_lateral`

## L3 Baseline

- Proxy: `object_count_mean` (per-anchor aggregate, ranked in descending order)
- P parameter: 2.0 (per V13.9 default)
- Selection rule: `greedy_maxmin_time` (per V13.9 default)

## YOLOv8n Model

- **Path**: `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt`
- **Size**: 6,549,796 bytes (6.5 MB)
- **COCO classes**: 80

## Python Environment

| Package | Version | Available |
|---------|---------|-----------|
| torch | 2.12.0+cu126 | YES |
| ultralytics | 8.4.51 | YES |
| opencv-python | 4.13.0 | YES |
| pandas | 2.2.2 | YES |
| pyarrow | 24.0.0 | YES (parquet writable) |

## GPU

- **Model**: NVIDIA A800-SXM4-80GB
- **Memory**: 81,920 MiB total, ~1 MiB used (free)
- **Utilization**: 0% (idle)

## Existing Scout Output (Reference)

- **Path**: `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/new_video_scout_gate_v1/tables/window_features_dataset3.csv`
- **Rows**: 694 windows (5s each)
- **Scout sampling**: 1 frame per 5s (0.2 fps) — midpoint frame only
- **Raw bbox data**: NOT SAVED (discarded in pipeline; only window aggregates kept)

## Detection Script Decision

- Need to **create new detection script** (existing `scout_pipeline.py` discards raw bbox; existing `01_detect_track.py` is for realcartest only).
- Script: `scripts/extract_raw_bbox_2fps.py`
- Will support:
  - 2 fps sampling with frame index `int(t * fps)` for deterministic 2fps
  - Resume via frame index checkpoint (skip frames already processed)
  - Per-frame YOLO inference (no batching across frames, but can batch within a frame)
  - Output to parquet (with CSV backup)

## VLM / Oracle

- **No VLM calls.** This is a cheap YOLOv8n materialization, not oracle labeling.
- Qwen reference labels are **read only**, used solely for anchor coverage reporting.
- No new oracle labels are produced.

## Will YOLOv8n Run?

**YES.** All infrastructure is available:
- CUDA-enabled GPU (A800 80GB)
- ultralytics 8.4.51
- torch with CUDA 12.6
- Model weights on disk
- Input video readable via cv2 / decord

## Decision

Proceed to Phase 1 (script implementation) and Phase 2 (60s smoke test).
