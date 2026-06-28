# FINAL_SUMMARY.md — Dataset3 Raw BBox Materialization Gate

## What Was Done

- Ran YOLOv8n cheap detector at 2 fps on `long_video_dataset3.mp4` (57.7 min, 1920×1080, 30fps)
- Saved 44595 raw bbox detections across 6926 sampled frames to parquet + CSV
- Verified anchor coverage: 347/347 anchors have enough frames for tracking
- All 40 Qwen-positive anchors (including all 21 singleton positives) are covered
- No new oracle labels produced; no VLM called; no existing data modified

## Constraint Compliance

- ✅ YOLOv8n cheap detector used (explicitly allowed)
- ✅ No Qwen / GLM / GPT / VLM / LLM / human oracle called
- ✅ No prompt tuning
- ✅ No model training
- ✅ No new data downloaded
- ✅ No existing raw experiment outputs modified
- ✅ No YOLO output used to rewrite Qwen labels
- ✅ No track-transition replay in this task
- ✅ All outputs written to `garc_eval/outputs/dataset3_raw_bbox_materialization_v1/`

## Key Numbers

| Item | Value |
|------|-------|
| Dataset3 video path | `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4` |
| Sample rate | 2.0 fps |
| Processed frames | 6926 |
| Total detections | 44595 |
| Wall-clock time | ~7.5 min (full run) |
| Effective processed rate | 12.16 fps |
| Failed frames | 0 |
| Frames with zero detections | 165 (2.4%) |
| Vehicle-like detections | 34814 (78.1%) |
| Output files | 16 MB CSV + 3.8 MB parquet |

## Anchor Coverage

| Group | Count | Covered | Coverage |
|-------|-------|---------|----------|
| All anchors | 347 | 347 | 100% |
| Qwen-positive | 40 | 40 | 100% |
| Singleton positives | 21 | 21 | 100% |
| Low-proxy singletons | 9 | 9 | 100% |
| Multi-anchor positives | 19 | 19 | 100% |

Mean 20 frames per anchor window (10s × 2fps = expected). Mean 100 vehicle detections per anchor window.

## Output Files

```
garc_eval/outputs/dataset3_raw_bbox_materialization_v1/
├── FINAL_SUMMARY.md
├── reports/
│   ├── INPUT_INVENTORY.md
│   ├── SMOKE_TEST_REPORT.md
│   ├── FULL_RUN_REPORT.md
│   └── ANCHOR_COVERAGE_REPORT.md
├── tables/
│   ├── raw_yolo_detections_dataset3_2fps.csv          (16 MB)
│   ├── raw_yolo_detections_dataset3_2fps.parquet      (3.8 MB)
│   ├── yolo_sampled_frames_dataset3_2fps.csv          (288 KB)
│   ├── smoke_raw_yolo_detections_60s.csv
│   ├── smoke_sampled_frames_60s.csv
│   └── anchor_detection_coverage_dataset3_2fps.csv
├── logs/
│   ├── yolo_dataset3_2fps.log
│   └── full_run_stdout.log
└── scripts/
    └── extract_raw_bbox_2fps.py
```

## Final Decision

**`RAW_BBOX_READY_FOR_TRACK_TRANSITION`**

All conditions met:
- Full 2 fps raw bbox materialization successful (6926 frames, 44595 detections, 0 failures)
- 100% anchor coverage (347/347 anchors have enough tracking frames)
- 100% Qwen-positive anchor coverage (40/40)
- 100% singleton positive coverage (21/21, including 9 low-proxy singletons)
- Raw bbox fields complete (22 columns including class_id, class_name, confidence, x1/y1/x2/y2, cx/cy, area)
- 2 fps temporal resolution sufficient for transition detection (objects persisting ≥0.5s)

raw_bbox_materialization_complete=true
