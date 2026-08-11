# GEOMETRIC_COVERAGE_GUARDED_MARGINAL_SCAN — Development Specification

```text
PRIMARY_METHOD = GEOMETRIC_COVERAGE_GUARDED_MARGINAL_SCAN
FROZEN_IMPLEMENTATION = M8
TRAINING = NONE
REFERENCE_ACCESS_BY_POLICY = PROHIBITED
```

For each unscanned unit, the deterministic development score is the visible
unit-local candidate mass plus a geometric-dispersion term, divided by the
frozen controlled-warm transition Q90 estimate. This is an interpretable proxy
for marginal new/complete observable gain and distance coverage; it does not
use evaluator-only pseudo-reference labels.

The M8 safe set applies both guards:

```text
GEOMETRIC_GUARD = immediate dispersion >= 0.8 * M0 largest-gap dispersion
RECOVERABILITY_GUARD = remaining estimated budget after admission
                       >= frozen fallback Q90 action cost
```

If no candidate passes the geometric guard, the M0 largest-gap action is used.
The executor uses the frozen transition-cost model for admission and executes
only complete estimated microchunks.

M0–M9 traces and metrics are in `mechanism_ablation/`. They are development
evidence only relative to the frozen pseudo-reference.
