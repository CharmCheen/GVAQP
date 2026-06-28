# Clip AQP Phase 0 Repair v1 Summary

Output directory:

`test_vlm/outputs/clip_aqp_phase0_v1/repair_v1`

Main reports:

- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/reports/ROOT_CAUSE.md`
- `test_vlm/outputs/clip_aqp_phase0_v1/repair_v1/reports/PHASE0_REPORT_v2.md`

Repair decision:

`REPAIR_DECISION: UNDERPOWERED_NO_CLEAN_GO_NO_GO`

Key findings:

- The original bound defect was a bad cap: `UCB_M_O` was capped by `LCB_Y_O`, allowing an upper bound on missed events to fall below `M_hat_O`.
- The repaired formula enforces `UCB_M_O >= M_hat_O - 1e-9` and `LCB_Y_O <= Y_hat_O + 1e-9`.
- A synthetic test fails on the pre-fix formula and passes on the fixed formula.
- The corrected no-repair audit persists per-block sampled rows in `tables/block_audit_rows_v2.csv`.
- Recomputing trial aggregates from per-block rows matches `tables/block_audit_no_repair_results_v2.csv`.
- The run remains underpowered because the benchmark has 29 pseudo-events; the mandated sample-size caveat is structurally enforced in the v2 report.

This is still a pseudo-oracle, pseudo-event Phase 0 repair read, not a human-ground-truth G-ARC guarantee.
