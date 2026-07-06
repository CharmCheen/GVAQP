# Repair-Trace Logging Specification

## Scope
This document defines the causal repair-trace schema used in `repair_trace_calls.csv` and `repair_trace_selected_intervals.csv`.

## Files

### `repair_trace_calls.csv` — one row per oracle/proxy call
| Field | Meaning |
|-------|---------|
| `call_id` | Unique identifier for this call |
| `segment_id` | Video segment being processed |
| `round_id` | Random seed / trial index |
| `budget` | Oracle budget for this run |
| `method` | Method name (only `Frozen-LATE-AQP-v1` logs calls in this version) |
| `action_type` | `audit_outside`, `discovery_initial_envelope`, or `repair_expansion` |
| `selected_unit_id` | Bin id that was audited / selected |
| `local_t_start`, `local_t_end` | Temporal bounds of the unit within the segment |
| `prior_score` | Proxy score that ranked this unit |
| `inside_E0_top20` | Whether the unit was inside the initial top-20 envelope |
| `oracle_label` | `positive` or `negative` according to the frozen oracle |
| `source_of_action` | `V3_two_phase` (fixed for this frozen run) |
| `trigger_call_id` | For repair expansions, the call that triggered the repair |
| `trigger_unit_id` | Bin id of the triggering unit |
| `trigger_label` | Oracle label of the triggering unit |
| `local_envelope_id` | Envelope id for discovery calls |
| `repair_window_start`, `repair_window_end` | Local window searched by a repair expansion |
| `repair_reason` | `audit_outside_positive` if triggered by an outside-envelope positive, else empty |
| `repair_utility_value` | Proxy score used to pick the repair expansion direction |
| `audit_probability`, `inclusion_probability` | Reserved placeholders; logged as `unknown_not_logged` in this version |
| `is_used_for_estimator`, `is_used_for_discovery`, `is_used_for_repair` | Boolean flags for the role of this call |
| `hit_event_id`, `hit_event_type` | Which reference event this unit overlaps, if any |
| `event_overlap_duration` | Duration of overlap with the hit event |
| `selected_interval_id` | Links to `repair_trace_selected_intervals.csv` |
| `notes` | Free-text notes |

### `repair_trace_selected_intervals.csv` — one row per returned interval
| Field | Meaning |
|-------|---------|
| `selected_interval_id` | Unique interval id |
| `segment_id`, `method`, `budget`, `trial` | Run context |
| `local_t_start`, `local_t_end` | Returned interval bounds |
| `duration`, `positive_overlap_duration`, `false_positive_duration` | Duration accounting |
| `oracle_label` | Aggregated label (`positive` if any overlap with a reference event) |
| `source_units` | Semicolon-separated list of unit ids merged into this interval |
| `from_repair` | Whether the interval was produced by a repair expansion |
| `num_repair_units` | Number of repair units merged |
| `hit_event_id`, `hit_event_type` | Best-matching reference event |

## Causal Chain Interpretation
1. An `audit_outside` call observes a unit **outside** the current top-k envelope.
2. If that unit is `oracle_label=positive`, the row is a causal trigger.
3. The trigger creates one or more `repair_expansion` calls inside `repair_window_start..repair_window_end`.
4. Each repair unit is merged into an interval; if `event_overlap_duration>0`, the repair produced a duration gain.
5. `is_used_for_repair=True` marks calls that were consumed by the repair mechanism; they are **not** reused as estimator samples.
