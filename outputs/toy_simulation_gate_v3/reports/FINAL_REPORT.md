# SD-AQP Synthetic Search v3

Date: 2026-07-03

## Scope

Synthetic-only algorithm search. No video, VLM, repository oracle labels, or probe data.

## Algorithm

SD-AQP first probes the high-prior ranking through DISCOVER calls. If early hit rate is high, it trusts the prior and continues top-prior selection. If low, it switches to AUDIT plus Beta-gated REPAIR. `M_hat` remains audit-ledger only.

## Gate Summary

| Gate | Status | Value | Threshold |
|---|---|---|---|
| full_repeats_at_least_100 | PASS | 120 | >=100 |
| strong_prior_sd_aqp_not_worse_than_top_prior_plus_0.02 | PASS | sd_aqp=0.272433; top_prior=0.272433 | sd_aqp <= top_prior + 0.02 |
| prior_wrong_sd_aqp_beats_top_prior | PASS | sd_aqp=0.905801; top_prior=0.997801 | sd_aqp <= top_prior |
| prior_wrong_sd_aqp_beats_uniform | PASS | sd_aqp=0.905801; uniform=0.922661 | sd_aqp <= uniform |
| repair_q_monotonic_by_width_aggregate | PASS | isolated=0.394930; narrow=0.438775; wide=0.611177 | isolated < narrow < wide |

## Scenario Aggregates

- Strong prior missing mass: SD-AQP `0.272`, top-prior `0.272`, v1 full `0.372`.
- Prior-wrong missing mass: SD-AQP `0.906`, top-prior `0.998`, uniform `0.923`, v1 full `0.864`.
- Repair q aggregate: isolated `0.395`, narrow `0.439`, wide `0.611`.

## Files

- `tables/full_budget160_missing_mass_matrix.csv`
- `tables/full_planner_budget_curve_summary.csv`
- `tables/full_final_planner_summary.csv`
- `tables/full_gate_summary.csv`
- `figures/full_strong_wrong_missing_mass.svg`

FINAL_DECISION: GO
