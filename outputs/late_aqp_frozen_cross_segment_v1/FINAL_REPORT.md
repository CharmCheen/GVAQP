# LATE-AQP Frozen Cross-Segment Validation — FINAL REPORT

## Experiment

- **Configuration**: `frozen_config.yaml` (`Frozen-LATE-AQP-v1`)
- **Segments**: `realcartest_2000_3200` (dev/calibration), `realcartest_0_1570` (high), `realcartest_3200_3830` (medium), `realcartest_1630_2000` (low)
- **Budgets**: 5, 10, 20, 40, 80, 120
- **Trials per budget**: 5 random seeds

## Main Result

**Overall verdict: PASS**

### Long-event recall (macro average across unseen segments; source: `center10_vlm_oracle_events.csv`)

| Budget | B6 | B7 | Ours |
|--------|-------|-------|-------|
| 5 | 0.138 | 0.125 | 0.188 |
| 10 | 0.300 | 0.225 | 0.188 |
| 20 | 0.450 | 0.463 | 0.350 |
| 40 | 0.738 | 0.725 | 0.900 |
| 80 | 0.887 | 0.900 | 1.000 |
| 120 | 0.963 | 0.975 | 1.000 |

### Duration-weighted precision (macro average across unseen segments; source: `center10_vlm_oracle_events.csv`)

| Budget | B6 | B7 | Ours |
|--------|-------|-------|-------|
| 5 | 0.097 | 0.178 | 0.338 |
| 10 | 0.111 | 0.178 | 0.336 |
| 20 | 0.115 | 0.186 | 0.202 |
| 40 | 0.099 | 0.151 | 0.182 |
| 80 | 0.089 | 0.112 | 0.127 |
| 120 | 0.089 | 0.102 | 0.104 |

*Recall/precision are oracle-relative to the `center10` VLM labels; they are not formal guarantees.*

## Key Findings

1. Ours wins on long-event recall at 4 of 6 budgets, including the maximum budget B=120 (source: `center10_vlm_oracle_events.csv`).
2. The largest average precision drop vs B7 is -0.2 percentage points (i.e., Ours is at least as precise on average; source: `center10_vlm_oracle_events.csv`).
3. 184 repair-expansion calls were triggered by outside-envelope positives; 48 produced positive duration overlap.
4. The low-density segment still yields positive event recall at some budgets (e.g., B=40 recall=1.000).

## Secondary Analysis

### Budgets where Ours did not win on long-event recall

Macro-averaged long-event recall across the three unseen segments; source: `center10_vlm_oracle_events.csv`.

| Budget | Ours | B6 | B7 | Gap to best baseline |
|--------|------|------|------|----------------------|
| 10 | 0.188 | 0.300 | 0.225 | 0.112 |
| 20 | 0.350 | 0.450 | 0.463 | 0.113 |

### Repair mechanism contribution: Ours-only long-interval hits

- Total repair-expansion calls traced: 184
- Repair rows with `is_ours_only_hit=True` and `event_type=long_interval`: **9**
- Unique long-interval event ids involved: 3

This count is **greater than 0**, indicating that the repair mechanism produced selected intervals hitting long events that neither B6 nor B7 selected in the same segment/budget/trial.

## Deliverables

- `segment_selection_report.md` — segment rationale.
- `repair_trace_logging_spec.md` — causal trace schema.
- `repair_trace_casebook.md` — concrete repair examples.
- `pass_fail_criteria_report.md` — numeric verdict.
- `revised_claims_after_cross_segment.md` — calibrated claims.
- Raw CSVs: `cross_segment_metrics.csv`, `cross_segment_budget_curves.csv`, `cross_segment_long_event_metrics.csv`, `selected_duration_precision_report.csv`, `repair_trace_calls.csv`, `repair_trace_selected_intervals.csv`, `segment_density_report.csv`.

## Next Action

The frozen configuration passes the pre-specified cross-segment checks. Recommended next step: replicate on a second video before claiming broader generalization.
