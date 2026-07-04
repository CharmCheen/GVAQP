# Toy Simulation Gate v1 Smoke Report

Date: 2026-07-03

## Scope

This experiment uses synthetic 1D worlds only. It runs no video, no VLM, and no repository oracle/probe labels; the pseudo-oracle is synthetic truth.

## Configuration

- Mode: `smoke`.
- Repeats per scenario/width: `8`.
- Atomic bins per world: `2000`.
- Budget checkpoints: `[20, 40, 80, 120, 160]`.
- Planner budget: `160`.
- Exploration floor eta: `0.1`.
- Phi proxy: `max(0, M_hat - found_positive_bins) / true_positive_bins`, with an upper variant using `M_hat_upper_95`.
- Beta posterior bidding: full planner compares REPAIR `Beta(alpha,beta)` upper-mean bid against next DISCOVER prior probability.
- Dual ledger: `M_hat` is estimated only from AUDIT samples; DISCOVER/REPAIR discoveries are tracked in separate ledgers.

## Gate Summary

| Gate | Status | Value | Threshold |
|---|---|---|---|
| calibration_95ci_min_coverage_at_least_0.90 | PASS | 0.875000 | >=0.900000 |
| isolated_repair_q_naturally_suppressed | PASS | 0.263889 | <=0.300000 |
| wide_cluster_repair_q_stays_active | PASS | 0.953496 | >=0.350000 |
| prior_wrong_full_planner_beats_top_prior | PASS | full=0.864622; top_prior=0.996708; uniform=0.928561 | full_planner_missing_mass <= top_prior_missing_mass |
| phi_upper_tracks_true_missing_mass | PASS | 1.000000 | >=0.900000 |
| dual_ledger_mhat_uses_only_audit_samples | PASS | True | True |

## Key Results

- Minimum empirical 95% interval coverage for stratified `M_hat`: `0.875`.
- Isolated-cluster mean final repair posterior q: `0.264`.
- Wide-cluster mean final repair posterior q: `0.953`.
- Prior-wrong final missing mass: full planner `0.865`, top-prior-only `0.997`, uniform `0.929`.
- Phi upper missing-mass coverage over audit/full checkpoints: `1.000`.
- Full-planner phi estimated-vs-true missing-mass correlation: `0.423`.
- Dual-ledger check, `M_hat` audit samples equal AUDIT calls: `True`.
- Calibration note: isolated worlds pass coverage but have wide intervals because positives are rare; this supports conservative calibration, not tight mass estimation.

## Figures

- `figures/smoke_prior_wrong_missing_mass.svg`
- `figures/smoke_calibration_coverage.svg`
- `figures/smoke_repair_self_correction.svg`
- `figures/smoke_phi_prior_wrong.svg`

## Files

- `tables/smoke_world_summary.csv`
- `tables/smoke_calibration_summary.csv`
- `tables/smoke_planner_budget_curve_summary.csv`
- `tables/smoke_repair_summary.csv`
- `tables/smoke_phi_summary.csv`
- `tables/smoke_dual_ledger_summary.csv`
- `tables/smoke_gate_summary.csv`

FINAL_DECISION: GO
