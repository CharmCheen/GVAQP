# FULL_RUN_REPORT.md — Dataset3 2fps Raw YOLOv8n BBox Materialization

## Input

- Video: `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4`
- Model: `yolov8n` (COCO 80-class)
- Model weights: `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt`
- Sample rate: 2.0 fps
- Run type: full

## Results

| Metric | Value |
|--------|-------|
| Video resolution | 1920 x 1080 |
| Video fps | 30.0 |
| Video duration | 3462.87 s (57.7 min) |
| Total sampled frames | 6926 (unique frame_index after dedup) |
| Frames processed | 6926 |
| Frames failed | 0 |
| Frames with zero detections | 165 (2.4%) |
| Total detections | 44595 |
| Mean detections per frame | 6.44 |
| Wall-clock time | 467.5 s (smoke 14.6s + first full 111s + second full 452.9s, including dedup) |
| Effective processed rate | 12.16 fps (consistent throughout) |

## Run Execution

The full run was executed in three invocations (smoke + two resume continuations) because the initial backgrounded process was terminated by the shell timeout. Resume logic correctly skipped already-processed frames.

| Run | Frames | Detections | Elapsed | Effective fps |
|-----|--------|-----------|---------|---------------|
| Smoke (60s) | 120 | 571 | 14.6 s | 8.21 |
| Full #1 (terminated) | 1350 | 7213 | 111.0 s | 12.16 |
| Full #2 (resume, completed) | 5507 | 36811 | 452.9 s | 12.16 |
| **Combined (dedup)** | **6926** | **44595** | **467.5 s** | **12.16** |

After the run, duplicate `frame_index` entries in the frames CSV (caused by resume appending) were deduplicated, keeping the last occurrence.

## Class Distribution (Top 10)

| class_name | count | pct |
|-----------|-------|-----|
| car | 31072 | 69.7% |
| person | 5208 | 11.7% |
| traffic light | 2828 | 6.3% |
| bus | 1612 | 3.6% |
| truck | 1465 | 3.3% |
| motorcycle | 665 | 1.5% |
| bicycle | 435 | 1.0% |
| kite | 409 | 0.9% |
| clock | 235 | 0.5% |
| stop sign | 169 | 0.4% |

**Vehicle-like** (car + bus + truck + motorcycle): 34814 (78.1%)

## Temporal Coverage

- Time range: 0.00 s to 3462.50 s
- All 347 anchors (center_time_s 5.0 to 3462.866) are within the sampled frame time range
- 6926 / 6926 expected frames sampled = 100% sampling completeness

## GPU

- Device used: `cuda:0` (NVIDIA A800-SXM4-80GB)
- GPU memory peak: ~563 MiB (model only)
- No GPU OOM events

## Output File Sizes

| File | Size |
|------|------|
| raw_yolo_detections_dataset3_2fps.csv | 16 MB |
| raw_yolo_detections_dataset3_2fps.parquet | 3.8 MB |
| yolo_sampled_frames_dataset3_2fps.csv | 288 KB |
| yolo_dataset3_2fps.log | ~80 KB |

## Warnings / Notes

- The scout pipeline (0.2 fps, 1 frame per 5s window, 694 windows) is a different sampling; this 2 fps run is at 10x the temporal density and is the new "raw" evidence.
- No new oracle labels were produced.
- No VLM was called.
- The `frames` CSV had 51 duplicate `frame_index` rows from resume appending; these were removed post-run (last-write-wins). Detections CSV was already unique.
- YOLOv8n confidence is `model.predict(frame, verbose=False, device=0)` without explicit `conf` threshold; all classes and conf levels are saved. Downstream filtering can be applied.

## Sanity Checks

- 0 frames failed out of 6926
- All 22 detection columns present and non-null
- Class distribution is plausible for driving footage
- Time range covers full video (0.0 to 3462.5 s)
- Output file sizes match projection (~12 MB CSV, ~3.5 MB parquet — actually 16MB/3.8MB, slightly larger due to more detections than smoke projected)
- 100% of expected frames sampled
- Vehicle-like detections dominate (78.1%)

## Decision

`RAW_BBOX_FULL_RUN_SUCCESS` — proceed to anchor coverage check.
