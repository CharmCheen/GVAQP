# SMOKE_TEST_REPORT.md - 60s Smoke Test

## Input

- Video: `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4`
- Model: `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt`
- Sample rate: 2.0 fps
- Time limit: 60 seconds

## Results

| Metric | Value |
|--------|-------|
| Total sampled frames (60s @ 2fps) | 120 |
| Frames processed | 120 |
| Frames failed | 0 |
| Frames with zero detections | 13 |
| Total detections | 571 |
| Mean detections per frame | 4.76 |
| Median detections per frame | 4 |
| Max detections per frame | 12 |
| Vehicle-like detections (car+bus+truck+motorcycle) | 538 |
| Wall-clock time | 14.6 s |
| Effective processed rate | 8.21 fps |

## Class Distribution (Top 10)

| class_name | count |
|-----------|-------|
| car | 494 |
| person | 21 |
| bus | 17 |
| truck | 17 |
| motorcycle | 10 |
| traffic light | 8 |
| stop sign | 1 |
| kite | 1 |
| boat | 1 |
| bicycle | 1 |

## GPU / CPU

- GPU: NVIDIA A800-SXM4-80GB
- Device used: `cuda:0` (via `model.predict(..., device=0)`)
- No GPU utilization sampling was performed during the test (not available in ultralytics direct call path)

## Output File Sizes

| File | Size |
|------|------|
| smoke_raw_yolo_detections_60s.csv | 206.6 KB |
| raw_yolo_detections_dataset3_2fps.parquet | 58.7 KB |
| smoke_sampled_frames_60s.csv | 4.3 KB |

## Full-Video Projection

- Total frames to sample: 6926 (3462.87 s × 2 fps)
- Effective rate: 8.21 fps (smoke)
- Estimated full run time: 6926 / 8.21 = 843 s = 14 min
- Estimated full run output: ~12.0 MB CSV, ~3.5 MB parquet
- Acceptable runtime and output size

## Sanity Checks

- YOLO loaded successfully
- Video opened and read at deterministic frame indices
- 0 frame failures out of 120
- All 22 expected detection columns present (video_id, frame_index, timestamp_sec, sample_fps, image_width, image_height, detection_id, class_id, class_name, confidence, x1, y1, x2, y2, cx, cy, bbox_width, bbox_height, bbox_area, model_name, model_weights, source_video_path)
- All 7 expected frame columns present (video_id, frame_index, timestamp_sec, sampled, processed, num_detections, error_message)
- No GPU OOM, no decode errors
- Detection count per frame plausible (mean 4.76, max 12)
- Vehicle-like classes (car, bus, truck, motorcycle) dominate as expected on driving footage
- Smoke outputs copied to `tables/smoke_raw_yolo_detections_60s.csv` and `tables/smoke_sampled_frames_60s.csv`

## Decision

`SMOKE_PASS_CONTINUE_FULL_RUN`

All conditions met:
- YOLO runs correctly
- sampled frames process successfully
- all detection fields populated
- full run time and output size acceptable (~14 min, ~12 MB)
- zero failed frames

Proceed to Phase 3 full run.
