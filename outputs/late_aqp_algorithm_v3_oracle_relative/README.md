# LATE-AQP Algorithm v3: Oracle-Relative Repair & Audit Schedule

This directory contains the v3 iteration of the LATE-AQP algorithm design.

## Scope

- Define oracle-relative AQP problem statement.
- Instrument repair trace lineage.
- Design and test LATE-AQP v3 audit schedules.
- Design and test repair utility v3.
- Prepare oracle-relative dense calibration plan.
- Revise paper claims ledger.

## Constraints

- No new external baselines.
- No SUPG / ABae implementation.
- No human annotation.
- No new cheap signals.
- No modification of existing labels, prior scores, or reference events.
- No probe_set_v1 used for tuning.
- No new VLM-oracle calls unless `ALLOW_NEW_ORACLE_CALLS=true`.

## Input

- `outputs/exsample_aware_replay/atomic_grid_10s.csv`
- `outputs/exsample_aware_replay/per_method_selected_intervals.csv`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv`
- `outputs/exsample_aware_replay/per_budget_metrics.csv`
- `outputs/late_aqp_h7_long_event_v1/long_event_only_replay_metrics.csv`

## Output files

| File | Purpose |
|------|---------|
| `oracle_relative_problem_statement.md` | Formal oracle-relative AQP definition |
| `repair_trace_schema.md` | Schema for selected-interval lineage |
| `repair_trace_events.csv` | Ours-full selected interval trace for B={10,20,40,80} |
| `repair_trace_casebook.md` | Case-level repair evidence assessment |
| `audit_schedule_v3_spec.md` | Pre-registered v3 audit schedules |
| `audit_schedule_v3_results.csv` | Empirical comparison of schedules |
| `repair_utility_v3_spec.md` | Repair utility variants |
| `repair_utility_v3_results.csv` | Empirical comparison of utilities |
| `oracle_relative_dense_calibration_plan.md` | Dense O_ref calibration design |
| `algorithm_v3_summary.md` | Consolidated v3 algorithm description |
| `revised_claims_ledger.md` | Claim status (can/cannot/next-conditions) |
| `FINAL_REPORT.md` | Human-readable summary |

## Run

```bash
bash outputs/late_aqp_algorithm_v3_oracle_relative/commands.sh
```
