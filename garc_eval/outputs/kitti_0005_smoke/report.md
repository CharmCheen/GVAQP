# KITTI Raw SUPG-Style Real-Frame Smoke Report

## 1. Dataset
- dataset: KITTI Raw
- sequence: 2011_09_26_drive_0005_sync
- URL used: https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0005/2011_09_26_drive_0005_sync.zip
- camera: image_02
- selected frames: 154 / 154
- note: SUPG-style real-frame reproduction, not exact SUPG night-street reproduction

## 2. Environment
- python: 3.10.20
- torch version: 2.12.0+cu126
- cuda availability: True
- GPU name: NVIDIA H20-3e
- ultralytics/cv2 available: ultralytics 8.4.51, cv2 4.10.0

## 3. Frame Metadata
- frame count: 154
- image path root: /qiuyeqing/llama_prl/G-ARC/data/frames/kitti_0005
- timestamp assumption: frame_idx / 10 FPS
- frame_metadata path: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_0005_smoke/frame_metadata.parquet

## 4. Proxy / Oracle
- proxy model: YOLOv8n
- oracle model: YOLOv8x
- target_class: car
- label rule: oracle_score >= 0.5
- label mean / positive rate: 0.961039
- label counts: 148 positive, 6 negative
- proxy min/max: 0.0 / 0.9368776679039

## 5. SUPG Smoke Results
Budget was set to 30 because n=154, using min(200, max(20, n // 5)).

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 5 | 0.900000 | 0.050000 | 30 | 0.200000 | 0.983063 | 0.984848 | 0.935135 | 0.925676 | 140.800000 | 139.000000 | 30.000000 | 0 |
| U-CI-RT | rt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.967094 | 0.961039 | 0.986486 | 1.000000 | 151.000000 | 154.000000 | 30.000000 | 0 |
| SUPG-RT | rt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.961039 | 0.961039 | 1.000000 | 1.000000 | 154.000000 | 154.000000 | 27.600000 | 0 |
| U-NOCI-PT | pt | 5 | 0.900000 | 0.050000 | 30 | 0.000000 | 0.967094 | 0.961039 | 0.986486 | 1.000000 | 151.000000 | 154.000000 | 30.000000 | 0 |
| SUPG-PT | pt | 5 | 0.900000 | 0.050000 | 30 | - | - | - | - | - | - | - | - | 5 |

## 6. Issues
- This is not exact SUPG night-street reproduction.
- KITTI Raw is an image sequence, not a video mp4; frame metadata was built directly from image_02/data/*.png.
- The car positive rate is very high at 0.961039, so this sequence is not suitable as a rare-event experiment.
- U-CI-RT and SUPG-RT returned near-vacuous or vacuous selections: U-CI-RT median selected_n=154, SUPG-RT selected_n=154 for all successful trials.
- SUPG-PT failed in all 5 trials with ValueError: math domain error.
- GPU was used for YOLO materialization via cuda:0.
- materialize dry-run initially failed on video_path: null; the dry-run check was patched to support image-sequence configs.
- The first SUPG run wrote results but failed during plotting because this matplotlib version does not support tick_labels; plotting was patched to fall back to labels, and the rerun completed.
- An auxiliary pandas to_markdown check failed because tabulate is not installed; this did not affect pipeline outputs.

## 7. Next Step
- Increase to a larger KITTI sequence or combine multiple KITTI sequences.
- Then run a 100-trial SUPG-style real-frame experiment.
- Keep searching for exact night-street/jackson if exact paper reproduction is required.
