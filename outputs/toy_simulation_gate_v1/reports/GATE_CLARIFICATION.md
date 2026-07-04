# Toy Simulation Gate v1 Clarification

Date: 2026-07-03

## Immediate Clarifications

- The prior-wrong numbers `full=0.866125`, `top_prior=0.998189`, `uniform=0.922110` are `missing_mass_fraction_mean`, not discovered mass. Lower is better.
- Full planner therefore beats top-prior in the prior-wrong aggregate, but the remaining missing mass is still high.
- The run is not a single world: full mode uses 120 independent repeats per width/scenario, across 3 width modes and 4 prior scenarios.
- `phi_upper_tracks_true_missing_mass = 1.000000` is not enough to certify a useful bound. The upper bound is very loose in many settings.
- `dual_ledger_mhat_uses_only_audit_samples = True` is a structural engineering check. It proves DISCOVER/REPAIR samples are not fed into `M_hat`; it is not, by itself, a statistical validity proof.

## Metric Direction

Source table: `outputs/toy_simulation_gate_v1/tables/planner_budget_curve_summary.csv`

Column: `missing_mass_fraction_mean`

Definition: `1 - found_positive_bins / true_positive_bins` at the given budget. Lower is better.

At budget 160, prior-wrong aggregate in the gate report is the mean over width modes:

| Planner | Mean missing mass | Direction |
|---|---:|---|
| full_planner | 0.866125 | lower is better |
| top_prior_only | 0.998189 | lower is better |
| uniform | 0.922110 | lower is better |

## Budget-160 Scenario Matrix

Each row is `missing_mass_fraction_mean`; lower is better. Source: `tables/planner_budget_curve_summary.csv`.

| Scenario | Width | uniform | top_prior_only | audit_discover | full_planner |
|---|---|---:|---:|---:|---:|
| strong | isolated | 0.923532 | 0.057536 | 0.086572 | 0.091113 |
| strong | narrow | 0.922216 | 0.096890 | 0.179912 | 0.242722 |
| strong | wide | 0.918622 | 0.666962 | 0.757550 | 0.764650 |
| weak | isolated | 0.912140 | 0.677961 | 0.743783 | 0.743911 |
| weak | narrow | 0.920488 | 0.715401 | 0.759494 | 0.628655 |
| weak | wide | 0.918429 | 0.795659 | 0.831331 | 0.752611 |
| wrong | isolated | 0.919670 | 0.996599 | 0.964692 | 0.969308 |
| wrong | narrow | 0.926053 | 0.997983 | 0.968491 | 0.864184 |
| wrong | wide | 0.920608 | 0.999985 | 0.969905 | 0.764884 |
| none | isolated | 0.920186 | 0.926851 | 0.927753 | 0.917687 |
| none | narrow | 0.918856 | 0.919617 | 0.922434 | 0.801366 |
| none | wide | 0.918544 | 0.920750 | 0.921358 | 0.770939 |

Interpretation:

- Prior-wrong: full planner helps for narrow/wide clusters but not isolated positives.
- Strong prior: top-prior-only is better than full planner across all three widths.
- No prior: full planner helps for narrow/wide clusters, mostly via REPAIR after initial discoveries.
- This is not a universal planner PASS. It is evidence for a conditional planner: use repair-heavy behavior when clustered positives are plausible, but avoid overriding a strong good prior.

## Repair Posterior by Width and Scenario

Source: `tables/repair_summary.csv`.

| Width | Scenario | final_repair_q_mean | repair_hit_rate_mean | repair_attempts_mean |
|---|---|---:|---:|---:|
| isolated | none | 0.245278 | 0.003125 | 3.166667 |
| isolated | strong | 0.167500 | 0.003125 | 4.100000 |
| isolated | weak | 0.167778 | 0.004167 | 4.133333 |
| isolated | wrong | 0.366667 | 0.000000 | 1.600000 |
| narrow | none | 0.311280 | 0.291764 | 39.858333 |
| narrow | strong | 0.353889 | 0.338801 | 49.466667 |
| narrow | weak | 0.365322 | 0.355427 | 50.891667 |
| narrow | wrong | 0.311628 | 0.256532 | 29.366667 |
| wide | none | 0.950708 | 0.959560 | 101.858333 |
| wide | strong | 0.951159 | 0.959942 | 102.741667 |
| wide | weak | 0.945737 | 0.954421 | 102.658333 |
| wide | wrong | 0.950238 | 0.959034 | 102.641667 |

Interpretation:

- The monotone shape is mostly present: isolated low, narrow intermediate, wide high.
- The isolated/wrong mean posterior q is 0.366667 because there are few attempts and the Beta prior remains influential; the observed hit rate is 0.
- A better gate should include narrow explicitly and should use confidence intervals or pairwise contrasts, not just a hand-picked mean threshold.

## Phi Bound Tightness

Source: `tables/full_planner_budget_curves.csv` and `tables/phi_summary.csv`.

`phi_upper_covers_true_missing_mass_fraction = 1.000000` over 14,400 checkpoint rows.

But looseness is large:

| Statistic | Mean | p50 | p90 | p95 | Max |
|---|---:|---:|---:|---:|---:|
| `phi_upper - phi_true` | 29.421016 | 13.444048 | 81.961496 | 97.586738 | 212.854924 |
| `abs(phi_estimated - phi_true)` | 0.760045 | 0.581590 | 1.000000 | 1.777778 | 21.222222 |

Interpretation:

- The upper bound is conservative but far too loose to support stopping decisions.
- The original `phi_upper_tracks_true_missing_mass` gate should not be treated as proof that the Phi potential is decision-useful.

## Dual Ledger Scope

Source code:

- `stratified_estimate(...)` consumes `audit_samples`.
- `dual_ledger_ok` checks `final_mhat_audit_samples == audit_calls` for `audit_discover` and `full_planner`.

This proves a structural separation:

- AUDIT samples feed `M_hat`.
- DISCOVER and REPAIR discoveries are tracked separately and do not enter `M_hat`.

This does not prove statistical validity under all adaptive policies. The statistical evidence is still the empirical coverage table, and that coverage is achieved with very wide intervals in sparse isolated worlds.

## Revised Verdict

`FINAL_DECISION: WEAK GO / NEEDS REDESIGN BEFORE REAL-VIDEO ORACLE INVESTMENT`

The toy simulation supports these narrower claims:

- Directionality for prior-wrong aggregate is correct: lower missing mass is better, and full planner beats top-prior in aggregate.
- REPAIR self-correction behaves qualitatively as expected across isolated/narrow/wide clusters.
- Dual-ledger implementation prevents DISCOVER/REPAIR samples from entering `M_hat`.

It does not yet support these stronger claims:

- Phi upper bound is decision-useful.
- Full planner is safe when the prior is strong and correct.
- Repair thresholding is statistically justified rather than manually thresholded.
- Dual-ledger coverage is tight enough to guide stopping.

Recommendation: do not return to real-video oracle spending yet. The next toy iteration should add adaptive gating between top-prior and repair-heavy modes, bound-width gates, and explicit narrow-cluster monotonicity/significance tests.
