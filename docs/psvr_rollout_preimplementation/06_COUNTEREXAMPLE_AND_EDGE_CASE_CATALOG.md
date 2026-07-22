
# Counterexample and edge-case catalog

These are frozen diagnostic scenarios, never primary statistical units. The table is explanatory; exact horizons, region states/costs, latent events, witnesses, emissions, hypothesis membership, and invariants are machine-bound in `outputs/psvr_rollout_preimplementation/TOY_NAMED_SCENARIOS.json`.

| Scenario | Construction | Prediction / invariant |
|---|---|---|
| VERIFY_FIRST_FAILURE | low-quality early frontier, productive unseen burst | always-CONFIRM loses discoverable events |
| SCAN_FIRST_FAILURE | one safe high-value witness, expensive next scan | always-SCAN delays or loses its commit |
| FIXED_PERIODIC_FAILURE | irregular burst/cost timing | fixed cadence mismatches opportunity |
| CAPACITY_MATCHING_LOW_QUALITY_FAILURE | frontier fills with hard negatives | capacity alone over-verifies low quality |
| SINGLE_HIGH_VALUE_FRONTIER | one unique witness, short horizon | symmetric evaluation retains immediate CONFIRM option |
| DUPLICATE_HEAVY_FRONTIER | many witnesses for one event | duplicate reward remains zero |
| LATE_HORIZON_CLOSURE | remaining time near action bounds | shield stops; no unfinished action counted |
| HETEROGENEOUS_CONFIRM_COST | equal success, unequal costs | continuation value may favor cheaper CONFIRM |
| DENSE_HOMOGENEOUS_BASELINE_FAVORABLE | dense equal-quality events | pi0 may match or beat rollout and must be reported |
| BURSTY_SCAN_FAVORABLE | unseen clustered events | SCAN can beat immediate CONFIRM |

Additional edges: zero events, zero candidates, all unsafe witnesses, exhausted iterator, simultaneous creation ties, last action exactly fits (`<=` admissible), duration exceeding a stochastic bound (record miss, never truncate), over-merged group closing two events (count opportunity loss), materialization failure (no commit), false positive (negative surrogate increment), duplicate positive (zero increment), and planning consuming the residual horizon.

Falsification checks: if VERIFY_FIRST and SCAN_FIRST do not reverse the corresponding fixed policy ranking, transition logic is suspect; if over-merge cannot lose an event, grouping is underspecified; if SCAN changes committed output or a dirty positive survives STOP, evidence semantics are invalid.
