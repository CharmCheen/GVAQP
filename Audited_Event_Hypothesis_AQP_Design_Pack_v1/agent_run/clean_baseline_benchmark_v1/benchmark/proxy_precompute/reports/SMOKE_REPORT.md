# Video Feature Precompute v1 Smoke Report

Date: 2026-07-03

## Scope

This stage converts an input video into the cheap feature CSVs consumed by `query_runtime_v1`. It runs no VLM, reads no oracle labels, and reads no probe labels.

## Summary

- `video_path`: `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4`.
- `video_id`: `long_video_dataset3`.
- `source_duration_seconds`: `3462.930`.
- `effective_duration_seconds`: `3462.930`.
- `coarse_5s_rows`: `693`.
- `center10_rows`: `347`.
- `yolo_status`: `COMPLETE_693_ok_0_skip_0_fail_device_cuda`.
- `elapsed_seconds`: `199.697`.
- `output_table_dir`: `/qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/benchmark/proxy_precompute/full`.
- `score_timeline_figure`: `/qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/benchmark/proxy_precompute/figures/full_score_timeline.svg`.

## Sanity Checks

| Check | Status | Details |
|---|---|---|
| video_readable | PASS | duration=3462.930s |
| coarse_grid_nonempty | PASS | rows=693 |
| center10_grid_nonempty | PASS | rows=347 |
| required_runtime_score_column_present | PASS | score column yolo_vehicle_max |
| proxy_table_has_no_oracle_fields | PASS | none |
| yolo_completed_or_explicitly_skipped | PASS | COMPLETE_693_ok_0_skip_0_fail_device_cuda |

## Figure

- Score timeline: `/qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/benchmark/proxy_precompute/figures/full_score_timeline.svg`.

FINAL_DECISION: GO
