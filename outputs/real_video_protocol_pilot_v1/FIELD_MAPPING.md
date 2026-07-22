# Field Mapping

## `frame_scores_adapter_ready.csv`

| adapter field | source file | source field | conversion |
|---|---|---|---|
| `video_id` | `grid_realcartest_2000_3200.csv` | `video_id` | cast to string |
| `frame_idx` | `grid_realcartest_2000_3200.csv` | `bin_idx` | integer 10s unit index, not raw video frame number |
| `timestamp` | `grid_realcartest_2000_3200.csv` | `t_start` | unit start time in seconds, relative to 2000s source window |
| `proxy_score` | `grid_realcartest_2000_3200.csv` | `prior_score_max` | clipped to [0,1], no new proxy generation |
| `oracle_label` | `grid_realcartest_2000_3200.csv` | `is_positive` | boolean converted to 0/1 pseudo-oracle replay label |
| `start_frame` | `grid_realcartest_2000_3200.csv` | `t_start` | `round(t_start * 10)`, decisecond tick |
| `end_frame` | `grid_realcartest_2000_3200.csv` | `t_end` | `round(t_end * 10) - 1`, inclusive decisecond tick |
| `start_time` | `grid_realcartest_2000_3200.csv` | `t_start` | seconds, relative to selected window |
| `end_time` | `grid_realcartest_2000_3200.csv` | `t_end` | seconds, relative to selected window |

## `reference_segments_adapter_ready.csv`

| adapter field | source file | source field | conversion |
|---|---|---|---|
| `video_id` | `ref_events_realcartest_2000_3200.csv` | `video_id` | cast to string |
| `segment_id` | generated | row number | integer segment id required by adapter loader |
| `start_frame` | `ref_events_realcartest_2000_3200.csv` | `t_start` | `round(t_start * 10)`, decisecond tick |
| `end_frame` | `ref_events_realcartest_2000_3200.csv` | `t_end` | `round(t_end * 10) - 1`, inclusive decisecond tick |
| `start_time` | `ref_events_realcartest_2000_3200.csv` | `t_start` | seconds, relative to selected window |
| `end_time` | `ref_events_realcartest_2000_3200.csv` | `t_end` | seconds, relative to selected window |
| `event_type` | `ref_events_realcartest_2000_3200.csv` | `event_type` | filled with `unknown` if missing |
| `source_event_id` | `ref_events_realcartest_2000_3200.csv` | `event_id` | kept as audit metadata; adapter ignores it |

Leakage boundary: `oracle_label` is used only by replay baselines through budgeted oracle calls and by diagnostic upper-bound/audit tables. It is not used to construct proxy rankings or adapter boundaries.
