# RUN_LOG.md - realcartest proxy materialization v1

## 2026-06-27T00:00:00Z - Initialization

- Task: Realcartest / V13 cheap-proxy materialization and feasibility audit.
- Output directory decision: user task names `garc_eval/outputs/realcartest_proxy_materialization_v1/`, but this checkout stores active garc_eval outputs under `src/garc_eval/outputs/`. Using `src/garc_eval/outputs/realcartest_proxy_materialization_v1/` to match current repository layout.
- VLM policy: no VLM, LLM, Qwen, GLM, human oracle, prompt tuning, training, downloads, or label generation will be run.
- Current decision tendency: proceed to Phase 0 inventory.

## 2026-06-27T08:48:11Z - Phase 0 complete

- Video: /qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4, 3987.083s, 24.000002 fps, 1920x1080
- Anchors: 399, labels: 399 ({'negative': 305, 'positive': 94})
- Dataset3 window: confirmed: center_time_s +/- 5 s, 10s center window, 2 fps raw bbox materialization
- GPU: YES (NVIDIA A800-SXM4-80GB, 81920 MiB, 81156 MiB)
- Decision: proceed to Phase 1

## 2026-06-27T08:48:35Z - Phase 1 checkpoint

- Processed 50/120 remaining frames for smoke run
- Failed frames so far: 0
- Detections in this invocation so far: 526
- Effective processing fps: 5.586

## 2026-06-27T08:48:39Z - Phase 1 checkpoint

- Processed 100/120 remaining frames for smoke run
- Failed frames so far: 0
- Detections in this invocation so far: 985
- Effective processing fps: 7.616

## 2026-06-27T08:48:41Z - Phase 1 complete

- Smoke processed frames: 120
- Smoke detections: 1153
- Smoke elapsed sec: 14.788
- Estimated full runtime min: 16.38
- Decision: SMOKE_PASS_CONTINUE_FULL_RUN

## 2026-06-27T08:49:20Z - Phase 2 checkpoint

- Processed 500/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 3498
- Effective processing fps: 12.870

## 2026-06-27T08:49:58Z - Phase 2 checkpoint

- Processed 1000/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 6420
- Effective processing fps: 12.978

## 2026-06-27T08:50:34Z - Phase 2 checkpoint

- Processed 1500/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 9835
- Effective processing fps: 13.236

## 2026-06-27T08:51:08Z - Phase 2 checkpoint

- Processed 2000/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 12461
- Effective processing fps: 13.535

## 2026-06-27T08:51:42Z - Phase 2 checkpoint

- Processed 2500/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 17480
- Effective processing fps: 13.798

## 2026-06-27T08:52:16Z - Phase 2 checkpoint

- Processed 3000/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 19828
- Effective processing fps: 13.964

## 2026-06-27T08:52:47Z - Phase 2 checkpoint

- Processed 3500/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 22259
- Effective processing fps: 14.214

## 2026-06-27T08:53:18Z - Phase 2 checkpoint

- Processed 4000/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 25173
- Effective processing fps: 14.427

## 2026-06-27T08:53:50Z - Phase 2 checkpoint

- Processed 4500/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 27361
- Effective processing fps: 14.569

## 2026-06-27T08:54:23Z - Phase 2 checkpoint

- Processed 5000/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 30018
- Effective processing fps: 14.620

## 2026-06-27T08:54:55Z - Phase 2 checkpoint

- Processed 5500/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 33640
- Effective processing fps: 14.689

## 2026-06-27T08:55:26Z - Phase 2 checkpoint

- Processed 6000/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 37905
- Effective processing fps: 14.817

## 2026-06-27T08:55:54Z - Phase 2 checkpoint

- Processed 6500/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 40833
- Effective processing fps: 14.990

## 2026-06-27T08:56:24Z - Phase 2 checkpoint

- Processed 7000/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 43592
- Effective processing fps: 15.109

## 2026-06-27T08:56:55Z - Phase 2 checkpoint

- Processed 7500/7975 remaining frames for full run
- Failed frames so far: 0
- Detections in this invocation so far: 46344
- Effective processing fps: 15.181

## 2026-06-27T08:57:25Z - Phase 2 complete

- Full sampled frames: 7975
- Full processed frames: 7975
- Full failed frames: 0
- Full detections: 48331
- Parquet written: /qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/realcartest_proxy_materialization_v1/tables/raw_yolo_detections_realcartest_2fps.parquet (4280999 bytes)

## 2026-06-27T08:57:33Z - Phase 3 complete

- Anchor features written: 399 rows
- Processed frame coverage: n=399, mean=19.987, std=0.305, min=14.000, p25=20.000, median=20.000, p75=20.000, max=21.000
- L3 fields computable: YES
- Warnings: {'NONE': 399}

## 2026-06-27T08:57:34Z - Phase 4 complete

- Labeled anchors: 399, positives: 94, positive_rate: 0.236
- object_count_mean AUC: 0.756
- High-selectivity rows: 7
- Decision tendency: REALCARTEST_PROXY_READY_FOR_SECOND_VIDEO_VALIDATION

## 2026-06-27T08:57:34Z - Phase 5 complete

- Final decision: REALCARTEST_PROXY_READY_FOR_SECOND_VIDEO_VALIDATION
- FINAL_SUMMARY.md and final_decision.csv written
- realcartest_proxy_materialization_complete=true

## 2026-06-27T08:58:25Z - Phase 3 complete

- Anchor features written: 399 rows
- Processed frame coverage: n=399, mean=19.987, std=0.305, min=14.000, p25=20.000, median=20.000, p75=20.000, max=21.000
- L3 fields computable: YES
- Warnings: {'NONE': 399}

## 2026-06-27T08:58:32Z - Phase 4 complete

- Labeled anchors: 399, positives: 94, positive_rate: 0.236
- object_count_mean AUC: 0.756
- High-selectivity rows: 7
- Decision tendency: REALCARTEST_PROXY_READY_FOR_SECOND_VIDEO_VALIDATION

## 2026-06-27T08:58:32Z - Phase 5 complete

- Final decision: REALCARTEST_PROXY_READY_FOR_SECOND_VIDEO_VALIDATION
- FINAL_SUMMARY.md and final_decision.csv written
- realcartest_proxy_materialization_complete=true
