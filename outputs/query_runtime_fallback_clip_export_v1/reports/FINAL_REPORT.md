# Query Runtime Fallback Clip Export v1 Final Report

Date: 2026-07-03

## Scope

This export materializes physical MP4 clips for the subset of frozen `query_runtime_v1` selections whose local times fit the available fallback video with `local_to_media_offset_seconds = 2000.0`. It does not rerank, retune, run VLM, run YOLO, or change the selector.

This is a partial physical preview export, not a full V13 source-video export, because `try_or_no/videos/realcartest.mp4` is absent in this workspace.

## Results

- Runtime candidate clips: `40`.
- Eligible for fallback export: `20`.
- Exported OK: `20`.
- Skipped out of fallback range: `20`.
- Exported total duration: `200.000` seconds.
- ffprobe exported duration range: `10.347` to `10.347` seconds.
- Fallback video duration: `3462.930499` seconds.

## Sanity Checks

| Check | Status | Details |
|---|---|---|
| selector_output_not_modified | PASS | Exporter reads outputs/query_runtime_v1/tables/candidate_clip_manifest.csv and does not change selector settings. |
| fallback_video_exists | PASS | /qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4 |
| all_eligible_clips_exported | PASS | ok=20, eligible=20, failed=0. |
| partial_export_scope_declared | PASS | skipped_out_of_fallback_range=20. |
| exported_clips_are_ffprobe_readable | PASS | validated=20 exported clips. |

## Files

- `tables/fallback_clip_export_manifest.csv`
- `tables/fallback_clip_export_summary.csv`
- `tables/exported_clip_validation.csv`
- `tables/sanity_checks.csv`
- `figures/fallback_export_timeline.svg`
- `clips/`
- `ffmpeg_commands_executed.sh`

FINAL_DECISION: WEAK GO
