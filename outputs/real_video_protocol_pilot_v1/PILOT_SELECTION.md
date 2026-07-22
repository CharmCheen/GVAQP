# Pilot Selection

Selected universe: `realcartest_2000_3200`.

Source files:

- Units/proxy/oracle labels: `outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_2000_3200.csv`
- Reference events: `outputs/late_aqp_frozen_cross_segment_v1/ref_events_realcartest_2000_3200.csv`

Selection rationale:

- Has a real-video-derived unit/window table.
- Has existing cheap proxy scores (`prior_score_max`, `prior_score_mean`); no new proxy was generated.
- Has offline pseudo-oracle labels (`is_positive`) suitable for budget-limited replay.
- Has VLM-defined reference events with event boundaries.
- Size is small: 20 minutes, 120 units, within the requested pilot limit.

Caveats:

- The raw source path referenced by historical manifests, `/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4`, is missing on this server.
- This run is therefore a real-video-derived CSV protocol pilot, not a fresh video decoding pilot.
- `dataset3` has the raw video and proxy/labels, but its boundary audit documents degenerate boundaries and no reliable reference event CSV suitable for this adapter evaluation was found.

Pilot summary:

| item | value |
|---|---:|
| duration_seconds | 1200 |
| unit_count | 120 |
| unit_duration_seconds | 10 |
| positive_units | 32 |
| reference_events | 20 |
| proxy_column | prior_score_max |
| frame_axis | decisecond ticks relative to selected 20min window |
