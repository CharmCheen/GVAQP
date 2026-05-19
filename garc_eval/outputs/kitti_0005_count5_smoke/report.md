# KITTI Raw Count-Based SUPG-Style Real-Frame Smoke Report

## 1. Context
- source smoke: KITTI Raw 2011_09_26_drive_0005_sync, image_02
- original predicate: contains_car(frame)
- original positive rate: 0.961039 (148 / 154), too high for a rare-event SUPG-style experiment
- data reuse: no new data downloaded; reused existing frame metadata, proxy scores, and oracle scores

## 2. Predicate
- new predicate: count_car(frame) >= 5
- target_class: car
- oracle label rule: oracle_count >= 5
- proxy score rule: min(proxy_count / 5, 1.0)
- attempted count_threshold=3 first; positive rate was 0.655844, still above the 50% target range

## 3. Frame Table
- frame count: 154
- frames.parquet: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_0005_count5_smoke/frames.parquet
- supg_source.csv: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/kitti_0005_count5_smoke/supg_source.csv
- frames.parquet retains: proxy_score_raw, proxy_count, oracle_score, oracle_count, predicate-specific proxy_score, label

## 4. Label / Proxy Distribution
- label mean / positive rate: 0.428571
- label counts: 66 positive, 88 negative
- proxy score min/max: 0.0 / 1.0
- proxy score mean: 0.715584
- proxy score quartiles: p25=0.4, p50=0.8, p75=1.0

## 5. SUPG Smoke Results
- budget: 30
- gamma: 0.9
- delta: 0.05
- trials: 5

| method | qtype | trials | gamma | delta | budget | failure_rate | mean_precision | median_precision | mean_recall | median_recall | mean_selected_n | median_selected_n | mean_sampled_n | error_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U-NOCI-RT | rt | 5 | 0.9 | 0.05 | 30 | 0.0 | 0.8855114928546494 | 0.9104477611940298 | 0.9424242424242424 | 0.9393939393939394 | 70.6 | 68.0 | 30.0 | 0 |
| U-CI-RT | rt | 5 | 0.9 | 0.05 | 30 | 0.0 | 0.4331428571428571 | 0.42857142857142855 | 1.0 | 1.0 | 152.4 | 154.0 | 30.0 | 0 |
| SUPG-RT | rt | 5 | 0.9 | 0.05 | 30 | 0.0 | 0.42857142857142855 | 0.42857142857142855 | 1.0 | 1.0 | 154.0 | 154.0 | 27.4 | 0 |
| U-NOCI-PT | pt | 5 | 0.9 | 0.05 | 30 | 0.0 | 0.9117421296876959 | 0.9117647058823529 | 0.9393939393939394 | 0.9393939393939394 | 68.0 | 68.0 | 30.0 | 0 |
| SUPG-PT | pt | 5 | 0.9 | 0.05 | 30 | - | - | - | - | - | - | - | - | 5 |

## 6. Issues
- This is still SUPG-style real-frame smoke, not exact SUPG night-street reproduction.
- KITTI Raw is an image sequence pipeline, not mp4 extraction.
- count_car >= 5 gives a usable positive rate for smoke testing, but proxy scores are saturated for many frames because proxy_count / 5 clips at 1.0.
- U-CI-RT is near-vacuous: median selected_n=154.
- SUPG-RT is vacuous: selected_n=154 in every successful trial.
- SUPG-PT still fails in all 5 trials with ValueError: math domain error.
- Current setup is suitable for exercising the real-frame SUPG pipeline and count predicate, but not yet a strong rare-event benchmark because SUPG-RT still degenerates to full selection.

## 7. Next Step
- Try a larger or combined KITTI sequence with count_car >= 5 or a higher count threshold.
- Inspect SUPG-PT math-domain failure separately before using PT results.
- Run 100 trials only after the predicate and sequence produce non-vacuous RT/PT behavior.
