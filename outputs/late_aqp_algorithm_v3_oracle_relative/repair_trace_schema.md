# Repair Trace Schema

Each selected interval in LATE-AQP must carry a lineage record with the following fields.

| Field | Type | Description |
|-------|------|-------------|
| `selected_interval_id` | string | Unique identifier for the selected interval |
| `method` | string | Method name (e.g., `Ours_full_LATE_AQP`) |
| `budget` | int | Oracle budget for this trial |
| `param_config` | string | Parameter configuration (e.g., `e0_top20`) |
| `local_t_start` | float | Start time (seconds, video-local) |
| `local_t_end` | float | End time (seconds, video-local) |
| `selected_duration` | float | `local_t_end - local_t_start` |
| `source_action` | categorical | One of: `initial_envelope_discovery`, `audit_sample`, `audit_triggered_repair`, `repair_expansion`, `boundary_guard`, `boundary_shrink`, `fallback_discovery` |
| `trigger_sample_id` | string | ID of the audit sample that triggered this selection (if any) |
| `trigger_sample_time` | float | Time of the triggering audit sample |
| `trigger_sample_label` | categorical | Label observed at trigger sample: `positive` / `negative` |
| `inside_E0_top10` | bool | Whether the bin is inside the top-10% prior envelope |
| `inside_E0_top20` | bool | Whether the bin is inside the top-20% prior envelope |
| `inside_E0_top30` | bool | Whether the bin is inside the top-30% prior envelope |
| `local_envelope_id` | string | Envelope / cluster ID the bin belongs to |
| `repair_window_start` | float | Start of repair window that produced this bin |
| `repair_window_end` | float | End of repair window that produced this bin |
| `oracle_calls_used` | int | Cumulative oracle calls up to and including this selection |
| `hit_event_id` | string | Reference event ID hit by this interval (if any) |
| `hit_event_type` | categorical | `long_interval` / `point_anchor` / `none` |
| `event_overlap_duration` | float | Duration of overlap with the hit event |
| `boundary_iou` | float | Best IoU with any overlapping reference event |
| `notes` | string | Human-readable notes, or `unknown_not_logged` |

## Trace status for current repository

The existing `per_method_selected_intervals.csv` records `method`, `budget`, `trial`, `bin_idx`, `t_start`, `t_end`, `label`, and `event_id`.
It does **not** record:

- `source_action`
- `trigger_sample_id`
- `trigger_sample_time`
- `trigger_sample_label`
- `local_envelope_id`
- `repair_window_start` / `repair_window_end`
- cumulative `oracle_calls_used`

Therefore, in the reconstructed trace below, these fields are filled with `unknown_not_logged`.
Future LATE-AQP implementations should log the full lineage at selection time.
