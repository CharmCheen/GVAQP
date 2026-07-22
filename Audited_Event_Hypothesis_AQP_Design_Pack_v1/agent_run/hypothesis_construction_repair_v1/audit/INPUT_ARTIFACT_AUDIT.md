# Input Artifact Audit

## Strongest supported finding

The frozen strict benchmark is internally compatible (`cbbv2_514c0d360fd5b2a4b5fe`), contains 347 units, 39 positive and 308 negative cached observations, and 26 VLM-defined pseudo-events. Planner inputs contain no oracle/reference columns.

## Missing named artifacts

- `garc_eval/bcm_aqp` is absent. H0 reproduction uses the sealed source `bcm_aqp_experiment_v2/scripts/run_bcm_aqp_v2.py` (SHA-256 `1f64599f5ccb95e57de1d235d2dbebd654ed9490e6836c226c72fbea30e96b1a`), matching the independent-review hash.
- The failed experiment has no `analysis/` or `diagnostics/` directory.
- No preserved all-candidate-score trace exists. This repair reconstructs it by deterministic read-only H0 replay and labels it derived.

No similarly named artifact was silently substituted. Evaluator-only oracle/reference tables are excluded from planner state and loaded only after traces freeze.
