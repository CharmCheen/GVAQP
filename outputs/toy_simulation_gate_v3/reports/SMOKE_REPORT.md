# SD-AQP Synthetic Search v3

Date: 2026-07-03

## Scope

Synthetic-only algorithm search. No video, VLM, repository oracle labels, or probe data.

## Algorithm

SD-AQP first probes the high-prior ranking through DISCOVER calls. If early hit rate is high, it trusts the prior and continues top-prior selection. If low, it switches to AUDIT plus Beta-gated REPAIR. `M_hat` remains audit-ledger only.

## Gate Summary

| Gate | Status | Value | Threshold |
|---|---|---|---|
| full_repeats_at_least_100 | PASS | 8 | >=100 |
| strong_prior_sd_aqp_not_worse_than_top_prior_plus_0.02 | PASS | sd_aqp=0.296642; top_prior=0.296642 | sd_aqp <= top_prior + 0.02 |
| prior_wrong_sd_aqp_beats_top_prior | PASS | sd_aqp=0.893576; top_prior=0.998840 | sd_aqp <= top_prior |
| prior_wrong_sd_aqp_beats_uniform | PASS | sd_aqp=0.893576; uniform=0.902393 | sd_aqp <= uniform |
| repair_q_monotonic_by_width_aggregate | PASS | isolated=0.375000; narrow=0.435795; wide=0.608866 | isolated < narrow < wide |

## Scenario Aggregates

- Strong prior missing mass: SD-AQP `0.297`, top-prior `0.297`, v1 full `0.376`.
- Prior-wrong missing mass: SD-AQP `0.894`, top-prior `0.999`, uniform `0.902`, v1 full `0.845`.
- Repair q aggregate: isolated `0.375`, narrow `0.436`, wide `0.609`.

## Files

- `tables/smoke_budget160_missing_mass_matrix.csv`
- `tables/smoke_planner_budget_curve_summary.csv`
- `tables/smoke_final_planner_summary.csv`
- `tables/smoke_gate_summary.csv`
- `figures/smoke_strong_wrong_missing_mass.svg`

FINAL_DECISION: GO
