# Second-Video Discovery Report

Searched non-`realcartest` videos for a full-VLM evaluation reference and prior scores.

## Candidate summary

| video_id | duration | has_full_vlm_reference | has_prior_scores | can_run_LATE | used_in_main_eval | reason_if_excluded |
|----------|----------|------------------------|------------------|--------------|-------------------|--------------------|
| realcartest | 3987.104 | False | False | False | False | primary video used in realcartest frontier; excluded from cross-video validation |
| realcartest_5k | 208.333333 | False | False | False | False | short derivative clip of realcartest; not an independent second video |
| test | 43.043333 | False | False | False | False | too short for meaningful limited-oracle frontier |
| long_video_dataset3 | 3462.93 | True | True | True | True |  |

## Selected second video

- **video_id**: `long_video_dataset3`
- **duration**: 3462.930 s
- **atomic units**: 347 x 10.0 s bins
- **full-VLM reference**: `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv`
- **prior score**: `score_yolo_count` from canonical anchor table
- **reference events**: 27 (6 long, 21 point-anchor)
- **positive unit density**: 0.0778

## Non-selected candidates

- `realcartest`: primary video used in realcartest frontier; excluded from cross-video validation
- `realcartest_5k`: short derivative clip of realcartest; not an independent second video
- `test`: too short for meaningful limited-oracle frontier
