# Query Runtime v1 Final Report

Date: 2026-07-03

## Scope

This experiment turns the current dev operating point into a reusable query-to-clip runtime. It does not run VLM/API/YOLO/GPU inference. It uses the fixed default selector family `score_topk + temporal NMS + duration cap`.

## Runtime Configuration

- Query: `dangerous_segments_enter_ego_path_v0`.
- Budget: `40` VLM-equivalent candidate clips.
- Score column: `yolo_vehicle_max`.
- Temporal NMS gap: `20.0` seconds.
- Anchor grid: `experiments/v13/v13_7_multimethod_replay/tables/center10_anchor_grid.csv`.
- Proxy features: `experiments/v13/v13_7_multimethod_replay/tables/center10_proxy_features.csv`.

## Outputs

- Candidate clips: `40`.
- Returned merged intervals: `40`.
- Total returned interval duration: `400.000` seconds.
- Clip export status: `SKIPPED_NO_VIDEO`.

## VLM-Defined Offline Evaluation

Dataset source: `v13_8_center10_oracle`.

- Clip precision `v13_8_center10_oracle`: 0.500.
- Clip recall `v13_8_center10_oracle`: 0.213.
- Clip F1 `v13_8_center10_oracle`: 0.299.
- Pseudo-event recall `v13_8_center10_oracle`: 0.275.

## Sanity Checks

| Check | Status | Details |
|---|---|---|
| selected_unique_clips_equal_budget | PASS | 40 unique clips selected. |
| selector_uses_no_oracle_labels | PASS | Selection occurs before evaluate_manifest(); load_runtime_rows reads only anchor grid and proxy feature CSV. |
| duration_cap_respected | PASS | sum clip duration=400.000s, cap=400.000s. |
| source_video_available_for_clip_export | WARN | No video path provided; wrote interval manifest and ffmpeg commands only. |

## Files

- `tables/candidate_clip_manifest.csv`
- `tables/returned_intervals.csv`
- `tables/runtime_summary.csv`
- `tables/sanity_checks.csv`
- `figures/selected_clip_timeline.svg`
- `ffmpeg_export_commands.sh`

FINAL_DECISION: GO
