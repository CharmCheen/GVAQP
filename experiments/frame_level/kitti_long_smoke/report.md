# KITTI Long Sequence SUPG-Style Smoke Report

## Dataset
- selected sequence: none
- reason: all requested candidate sequences had fewer than 500 image_02 frames
- camera: image_02
- max_frames: 1000
- no YOLO materialization or SUPG smoke was run for kitti_long_smoke

| sequence | download URL | zip bytes | total frames found | status |
| --- | --- | ---: | ---: | --- |
| 2011_09_26_drive_0014_sync | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0014/2011_09_26_drive_0014_sync.zip | 1261710548 | 314 | rejected: fewer than 500 frames |
| 2011_09_26_drive_0018_sync | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0018/2011_09_26_drive_0018_sync.zip | 1115646800 | 270 | rejected: fewer than 500 frames |
| 2011_09_26_drive_0051_sync | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0051/2011_09_26_drive_0051_sync.zip | 1702327445 | 438 | rejected: fewer than 500 frames |

## Count Threshold Calibration
- calibration input: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_0005_smoke/oracle_scores.parquet
- calibration CSV: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_0005_count_calibration.csv
- calibration JSON: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_0005_count_calibration.json
- selected K on KITTI 0005: 13
- selected positive rate on KITTI 0005: 0.142857
- selected_by: target

| k | positive_rate | positive_count |
| ---: | ---: | ---: |
| 1 | 0.993506 | 153 |
| 2 | 0.883117 | 136 |
| 3 | 0.655844 | 101 |
| 4 | 0.493506 | 76 |
| 5 | 0.428571 | 66 |
| 6 | 0.396104 | 61 |
| 7 | 0.344156 | 53 |
| 8 | 0.324675 | 50 |
| 9 | 0.298701 | 46 |
| 10 | 0.272727 | 42 |
| 11 | 0.227273 | 35 |
| 12 | 0.188312 | 29 |
| 13 | 0.142857 | 22 |
| 14 | 0.045455 | 7 |
| 15 | 0.025974 | 4 |
| 16 | 0.012987 | 2 |
| 17 | 0.000000 | 0 |
| 18 | 0.000000 | 0 |
| 19 | 0.000000 | 0 |
| 20 | 0.000000 | 0 |

## Proxy / Oracle
- not run for kitti_long_smoke because no candidate passed the 500-frame selection rule
- intended proxy: YOLOv8n
- intended oracle: YOLOv8x
- intended predicate: count_car >= K
- intended proxy_score rule: min(proxy_count/K, 1.0)
- intended label rule: oracle_count >= K

## SUPG Results
- summary.csv: not generated
- SUPG-RT selected all: not evaluated
- SUPG-PT failed: not evaluated
- non-vacuous result: not evaluated

## Judgment
pipeline-only smoke: count-threshold calibration tool was validated on KITTI 0005, but long-sequence SUPG smoke was stopped by the frame-count rule.

usable non-degenerate SUPG smoke: no.

unsuitable benchmark: yes, for the specified three candidates under the minimum 500-frame requirement.

## Next Step
- Switch to a KITTI Raw sequence with at least 500 image_02 frames, or combine multiple accepted KITTI sequences into one frame table.
- Once a longer sequence is available, run YOLO materialization, calibrate K on that sequence, then run 5-trial smoke.
- If non-degenerate, increase trials to 20, then 100.
