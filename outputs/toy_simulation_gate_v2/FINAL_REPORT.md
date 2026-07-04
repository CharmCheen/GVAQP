# Toy Simulation Gate v2 Strict Audit

Date: 2026-07-03

## Scope

This is a strict posthoc audit of `toy_simulation_gate_v1`. It reads synthetic v1 CSV outputs only; it runs no video, VLM, repository oracle labels, or probe data.

## Metric Direction

`missing_mass_fraction_mean = 1 - found_positive_bins / true_positive_bins`; lower is better. The prior-wrong numbers in v1 are missing mass, not discovered mass.

## Strict Gate Summary

| Gate | Status | Value | Threshold |
|---|---|---|---|
| metric_direction_explicit_missing_mass_lower_is_better | PASS | missing_mass_fraction_mean | documented |
| full_repeats_at_least_100 | PASS | 120 | >=100 |
| mhat_min_coverage_at_least_0.90 | PASS | 0.950000 | >=0.900000 |
| phi_upper_coverage_at_least_0.90 | PASS | 1.000000 | >=0.900000 |
| phi_upper_p50_width_at_most_2.0 | FAIL | 13.437477 | <=2.000000 |
| strong_prior_full_not_worse_than_top_prior | FAIL | full=0.366162; top_prior=0.273796 | full <= top_prior |
| prior_wrong_full_beats_top_prior_aggregate | PASS | full=0.866125; top_prior=0.998189 | full <= top_prior |
| prior_wrong_full_beats_uniform_aggregate | PASS | full=0.866125; uniform=0.922110 | full <= uniform |
| repair_q_monotonic_by_width_aggregate | PASS | isolated=0.236806; narrow=0.335530; wide=0.949461 | isolated < narrow < wide |
| repair_q_monotonic_by_width_each_scenario | FAIL | False | all scenarios True |
| dual_ledger_structural_separation | PASS | True | mhat_audit_samples_mean == audit_calls_mean |

## Key Findings

- Full repeats per calibration cell: `120`.
- Prior-wrong aggregate missing mass: full `0.866125`, top-prior `0.998189`, uniform `0.922110`.
- Strong-prior aggregate missing mass: full `0.366162`, top-prior `0.273796`.
- Phi upper coverage: `1.000000`, but p50 `phi_upper - phi_true` is `13.437477`.
- Repair aggregate q: isolated `0.236806`, narrow `0.335530`, wide `0.949461`.
- Repair monotonic in every scenario: `False`.
- Dual-ledger check is structural: `True`; it does not prove tight statistical validity.

## Interpretation

The prior-wrong direction is resolved: full planner improves over top-prior in aggregate because the metric is remaining missing mass. However, the stricter audit fails because strong-prior cases regress, Phi upper bounds are too loose to guide stopping, and repair monotonicity is not clean in every scenario.

## Files

- `tables/budget160_missing_mass_matrix.csv`
- `tables/scenario_planner_aggregate.csv`
- `tables/phi_bound_width_summary.csv`
- `tables/repair_q_by_width_scenario.csv`
- `tables/repair_q_monotonic_by_scenario.csv`
- `tables/strict_gate_summary.csv`
- `figures/prior_wrong_missing_mass_matrix.svg`
- `figures/strong_prior_regression.svg`
- `figures/repair_q_width_aggregate.svg`

FINAL_DECISION: NO-GO
