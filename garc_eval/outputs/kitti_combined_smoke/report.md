# KITTI Combined SUPG-Style Real-Frame Smoke Report

## 1. Dataset
- sequences:
  - 2011_09_26_drive_0005_sync
  - 2011_09_26_drive_0014_sync
  - 2011_09_26_drive_0018_sync
  - 2011_09_26_drive_0051_sync
- per-sequence frame count:
  - 2011_09_26_drive_0005_sync: 154
  - 2011_09_26_drive_0014_sync: 314
  - 2011_09_26_drive_0018_sync: 270
  - 2011_09_26_drive_0051_sync: 438
- total frame count: 1176
- camera: image_02
- note: SUPG-style real-frame reproduction, not exact SUPG night-street reproduction

## 2. Count Threshold Calibration
- selected_k: 15
- selected positive rate: 0.137755
- selected_by: target
- calibration table path: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_combined_smoke/count_calibration.csv
- calibration JSON path: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_combined_smoke/count_calibration.json

## 3. Proxy / Oracle
- proxy: YOLOv8n
- oracle: YOLOv8x
- predicate: count_car >= 15
- proxy_score: min(proxy_count/K, 1.0)
- label: oracle_count >= K

## 4. SUPG Source
- n: 1176
- label mean: 0.137755
- label counts: 1014 negative, 162 positive
- proxy score min/max: 0.0 / 1.0
- proxy_score unique count: 16

## 5. SUPG Results
| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| U-NOCI-RT | rt | 5 | 0.9 | 0.05 | 117 | 0.2 | 0.47682169401887586 | 0.478125 | 0.9333333333333332 | 0.9444444444444444 | 317.8 | 320.0 | 117.0 | 0 |
| U-CI-RT | rt | 5 | 0.9 | 0.05 | 117 | 0.0 | 0.1377551020408163 | 0.1377551020408163 | 1.0 | 1.0 | 1176.0 | 1176.0 | 117.0 | 0 |
| SUPG-RT | rt | 5 | 0.9 | 0.05 | 117 | 0.0 | 0.1377551020408163 | 0.1377551020408163 | 1.0 | 1.0 | 1176.0 | 1176.0 | 109.6 | 0 |
| U-NOCI-PT | pt | 5 | 0.9 | 0.05 | 117 | 1.0 | 0.6947679858924494 | 0.6917293233082706 | 0.5765432098765432 | 0.5679012345679012 | 134.4 | 133.0 | 117.0 | 0 |
| SUPG-PT | pt | 5 | 0.9 | 0.05 | 117 | 0.0 | 1.0 | 1.0 | 0.22839506172839502 | 0.2222222222222222 | 37.0 | 36.0 | - | 0 |

## 6. Judgment
Classification: pipeline-only smoke.

The dataset meets the size and positive-rate criteria: n=1176 and label mean=13.8%. However, SUPG-RT selected all 1176 records in every trial, so it is not a usable non-degenerate SUPG smoke under the requested criteria.

## 7. Issues
- This is not exact SUPG night-street reproduction.
- The dataset combines multiple KITTI Raw sequences for frame-level evaluation.
- SUPG-PT did not fail with math domain error in this combined run.
- U-CI-RT and SUPG-RT are vacuous: both have median_selected_n=1176.
- proxy_score has 16 unique values because count-based proxy scores are discretized by K=15.

## 8. Next Step
- Add more KITTI sequences or use a larger traffic dataset to reduce RT degeneracy.
- If a later run is non-degenerate, run 20 trials first, then 100 trials.
