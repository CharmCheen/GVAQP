# Video Feature Precompute Runtime v1 Final Report

Date: 2026-07-03

## Scope

This stage runs the fixed default selector family on generated cheap feature tables. It runs no VLM and performs no oracle/probe evaluation.

## Runtime Configuration

- Query: `dangerous_segments_enter_ego_path_v0`.
- Budget: `40` candidate clips.
- Selector: `score_topk + temporal NMS + duration cap`.
- Score column: `yolo_vehicle_max`.
- Temporal NMS gap: `20.0` seconds.
- Anchor grid: `/qiuyeqing/llama_prl/G-ARC/outputs/video_feature_precompute_v1/tables/center10_anchor_grid.csv`.
- Proxy features: `/qiuyeqing/llama_prl/G-ARC/outputs/video_feature_precompute_v1/tables/center10_proxy_features.csv`.

## Outputs

- Candidate clips: `40`.
- Returned merged intervals: `40`.
- Total returned interval duration: `400.000` seconds.
- Clip export status: `OK`.
- ffprobe readability check: `40/40` clips readable, `0` failures.
- Evaluation status: `NO_ORACLE_PROVIDED`.

## Sanity Checks

| Check | Status | Details |
|---|---|---|
| selected_unique_clips_equal_budget | PASS | 40 unique clips selected. |
| selector_uses_no_oracle_labels | PASS | Inputs are generated anchor/proxy CSVs; no oracle/probe files are opened. |
| duration_cap_respected | PASS | sum clip duration=400.000s, cap=400.000s. |
| default_selector_family | PASS | score_topk + temporal NMS + duration cap; CILS not used. |
| physical_clip_export | PASS | OK |

## Files

- `tables/candidate_clip_manifest.csv`
- `tables/returned_intervals.csv`
- `tables/runtime_summary.csv`
- `tables/sanity_checks.csv`
- `figures/selected_clip_timeline.svg`
- `ffmpeg_export_commands.sh`

FINAL_DECISION: GO

<!-- A0_BASELINE_ARCHIVE_V1 -->
## A0 Baseline Archive Addendum

- A0 baseline: `score_topk + temporal NMS + duration cap`, no CILS, no oracle confirmation.
- Budget: `40` candidate clips.
- NMS gap: `20.0` seconds.
- Budget/gap source: carried over from `default_selector_score_sweep_v1` / `query_runtime_v1` dev operating point; not a fairness-tuned CILS comparison setting.
- A0 candidate time distribution status: `PASS`; top 10min bucket fraction `0.250000`.
- Candidate distribution figure: `outputs/video_signal_quality_audit_v1/figures/a0_candidate_time_distribution.svg`.
