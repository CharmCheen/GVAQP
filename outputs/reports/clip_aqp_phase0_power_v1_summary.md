# Clip AQP Phase 0.6 Power v1 Summary

Output directory:

`test_vlm/outputs/clip_aqp_phase0_v1/power_v1`

Main report:

`test_vlm/outputs/clip_aqp_phase0_v1/power_v1/reports/POWER_REPORT.md`

Decision:

`POWER_DECISION: EXPAND_BENCHMARK_TO_N_EVENTS`

Key results:

- Repaired input invariants passed: `UCB_M_O >= M_hat_O - 1e-9`, `LCB_Y_O <= Y_hat_O + 1e-9`, and all sampled rows are certification rows with no design/repair usage.
- Certified SRS mode remains mostly vacuous at 50 and 100 pseudo-events.
- Certified SRS becomes mostly non-vacuous around 200 pseudo-events and fully non-vacuous in this simulation by 500 pseudo-events.
- Source/video stratification did not materially improve median LCB tightness because no candidate/proxy-region field exists in `block_audit_rows_v2.csv`.
- Practical bootstrap is much tighter than certified mode, but is diagnostic only and not a certificate.
- Results remain pseudo-event based; clean event boundaries are still needed before making human-ground-truth claims.
