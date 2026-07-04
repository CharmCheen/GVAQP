# AQP Algorithm Research Report: SD-AQP v3

Date: 2026-07-03

## Executive Conclusion

SD-AQP v3 is a meaningful algorithmic improvement over the rejected v2 full planner, but it is not yet a complete top-conference-ready AQP algorithm.

The main contribution is a self-diagnosing controller:

- use early DISCOVER calls to test whether the cheap prior is trustworthy;
- preserve top-prior behavior when the prior is strong;
- switch to AUDIT + Beta-gated REPAIR when high-prior discoveries fail;
- keep `M_hat` structurally dual-ledger: only AUDIT samples feed the estimator.

This fixes the most damaging v2 failure: the old full planner destroyed strong-prior performance. However, the current v3 is conservative in prior-wrong clustered cases and underperforms the aggressive v1 full planner there.

## What Changed From v2

v2 strict audit rejected the previous `GO` for three reasons:

| v2 failure | SD-AQP v3 response | Status |
|---|---|---|
| Strong-prior full planner worse than top-prior. | Early DISCOVER trust probe; if hit rate is high, continue top-prior. | Fixed in full synthetic run. |
| Prior-wrong direction unclear. | Reports `missing_mass_fraction_mean`; lower is better. | Fixed in reports/tables. |
| Repair monotonicity and Phi looseness insufficient. | Repair q tracked; Phi is not claimed as a useful stopping bound. | Partially addressed; not solved. |

## Full Synthetic Result

Source: `outputs/toy_simulation_gate_v3/tables/budget160_missing_mass_matrix.csv`

Metric: `missing_mass_fraction_mean = 1 - found_positive_bins / true_positive_bins`; lower is better.

### Scenario Aggregates

| Scenario | uniform | top-prior | v1 full | SD-AQP v3 | Readout |
|---|---:|---:|---:|---:|---|
| strong | 0.921 | 0.272 | 0.372 | 0.272 | SD-AQP preserves good prior. |
| weak | 0.918 | 0.738 | 0.708 | 0.766 | SD-AQP too conservative; v1 full slightly better. |
| wrong | 0.923 | 0.998 | 0.864 | 0.906 | SD-AQP beats weak baselines but trails aggressive v1 full. |
| none | 0.917 | 0.918 | 0.831 | 0.815 | SD-AQP improves over v1 full in aggregate. |

### Gate Summary

Source: `outputs/toy_simulation_gate_v3/tables/gate_summary.csv`

| Gate | Status | Value |
|---|---|---|
| full repeats >= 100 | PASS | 120 |
| strong prior not worse than top-prior + 0.02 | PASS | SD-AQP 0.272433; top-prior 0.272433 |
| prior-wrong beats top-prior | PASS | SD-AQP 0.905801; top-prior 0.997801 |
| prior-wrong beats uniform | PASS | SD-AQP 0.905801; uniform 0.922661 |
| repair q monotonic aggregate | PASS | isolated 0.394930; narrow 0.438775; wide 0.611177 |

## Why This Is Not Yet Enough

1. Prior-wrong recovery is still weak.
   SD-AQP v3 beats top-prior and uniform, but v1 full is better in prior-wrong aggregate: 0.864 vs 0.906. The trust probe saves strong prior but costs too much in wrong-prior worlds before repair takes over.

2. Weak-prior behavior is under-optimized.
   SD-AQP often treats weak prior as trustworthy and follows top-prior, while v1 full's repair mode helps in narrow/wide weak worlds.

3. Phi is still diagnostic, not a stopping certificate.
   v3 intentionally avoids claiming the v2 `phi_upper` as decision-useful. A publishable algorithm needs a tighter operational uncertainty measure or a clear theorem-free empirical stopping rule.

4. The planner is still hand-thresholded.
   `trust_hit_rate_threshold = 0.05` is reasonable for the current synthetic world but not yet derived or robustly swept.

## Next Algorithmic Step

The next candidate should be SD-AQP v4 with sequential prior diagnosis:

1. **Early negative stopping for prior trust probe**  
   Stop probing high-prior atoms early if the first 10-20 DISCOVER calls have zero or near-zero hits. This should save budget in prior-wrong worlds.

2. **Aggressive override mode**  
   Once the prior is diagnosed as wrong, stop comparing REPAIR against high prior decoys. Allocate to AUDIT + REPAIR until the repair posterior collapses.

3. **Three-mode controller**  
   Use:
   - TRUST_PRIOR for strong prior,
   - HEDGE for weak/uncertain prior,
   - OVERRIDE_PRIOR for wrong prior.

4. **Bound-width-aware audit**  
   Do not claim `phi_upper` as a pass/fail certificate. Instead report:
   - estimator coverage,
   - empirical bound width,
   - downstream decision regret.

5. **Threshold sweep**  
   Sweep trust threshold, early-stop window, and repair bid temperature over synthetic worlds. Do not tune on `probe_set_v1`.

## Current Recommendation

Do not return to real-video oracle spending yet.

SD-AQP v3 is a promising algorithmic direction because it fixes strong-prior regression while keeping dual-ledger separation. The next milestone is v4: match v1 full in prior-wrong clustered settings without regressing strong-prior cases.

FINAL_RESEARCH_STATUS: PROMISING BUT INCOMPLETE
