# Toy Simulation Gate v1 Final Report

## Revised Verdict

The original full run marked all configured gates PASS, but follow-up inspection shows the `GO` label is too strong. See `reports/GATE_CLARIFICATION.md`.

`FINAL_DECISION_REVISED: WEAK GO / NEEDS REDESIGN BEFORE REAL-VIDEO ORACLE INVESTMENT`

Key reasons:

- Prior-wrong numbers are `missing_mass_fraction_mean`, so lower is better; full planner beats top-prior in aggregate, but remaining missing mass is still high.
- Strong-prior scenarios regress against top-prior-only.
- `phi_upper` coverage is 1.0 because the upper bound is extremely loose, not because it is decision-useful.
- Dual-ledger check is structural, not a full statistical proof.

Date: 2026-07-03

## Scope

This experiment uses synthetic 1D worlds only. It runs no video, no VLM, and no repository oracle/probe labels; the pseudo-oracle is synthetic truth.

## Configuration

- Mode: `full`.
- Repeats per scenario/width: `120`.
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
| calibration_95ci_min_coverage_at_least_0.90 | PASS | 0.950000 | >=0.900000 |
| isolated_repair_q_naturally_suppressed | PASS | 0.259908 | <=0.300000 |
| wide_cluster_repair_q_stays_active | PASS | 0.949045 | >=0.350000 |
| prior_wrong_full_planner_beats_top_prior | PASS | full=0.866125; top_prior=0.998189; uniform=0.922110 | full_planner_missing_mass <= top_prior_missing_mass |
| phi_upper_tracks_true_missing_mass | PASS | 1.000000 | >=0.900000 |
| dual_ledger_mhat_uses_only_audit_samples | PASS | True | True |

## Key Results

- Minimum empirical 95% interval coverage for stratified `M_hat`: `0.950`.
- Isolated-cluster mean final repair posterior q: `0.260`.
- Wide-cluster mean final repair posterior q: `0.949`.
- Prior-wrong final missing mass: full planner `0.866`, top-prior-only `0.998`, uniform `0.922`.
- Phi upper missing-mass coverage over audit/full checkpoints: `1.000`.
- Full-planner phi estimated-vs-true missing-mass correlation: `0.641`.
- Dual-ledger check, `M_hat` audit samples equal AUDIT calls: `True`.
- Calibration note: isolated worlds pass coverage but have wide intervals because positives are rare; this supports conservative calibration, not tight mass estimation.

## Figures

- `figures/full_prior_wrong_missing_mass.svg`
- `figures/full_calibration_coverage.svg`
- `figures/full_repair_self_correction.svg`
- `figures/full_phi_prior_wrong.svg`

## Files

- `tables/full_world_summary.csv`
- `tables/full_calibration_summary.csv`
- `tables/full_planner_budget_curve_summary.csv`
- `tables/full_repair_summary.csv`
- `tables/full_phi_summary.csv`
- `tables/full_dual_ledger_summary.csv`
- `tables/full_gate_summary.csv`

FINAL_DECISION_ORIGINAL_CONFIGURED_GATES: GO

FINAL_DECISION_REVISED: WEAK GO / NEEDS REDESIGN BEFORE REAL-VIDEO ORACLE INVESTMENT
