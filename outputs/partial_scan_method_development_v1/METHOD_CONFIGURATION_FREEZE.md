# Development Candidate Configuration Freeze

```text
PRIMARY_METHOD = GEOMETRIC_COVERAGE_GUARDED_MARGINAL_SCAN
IMPLEMENTATION_LEVEL = M8
METHOD_CONFIGURATION = FROZEN_FOR_DEVELOPMENT
```

M8 is the deterministic, non-trained policy implemented in
`scripts/run_partial_scan_mechanism_ablation.py`. It extends M0 through M7 with
a conservative recoverability guard. Its action score uses unit-local visible
candidate mass, geometric dispersion, and frozen controlled-warm transition
Q90 cost. Candidate selection does not consume pseudo-reference events.

The evaluator-only metric is pseudo-reference event exposure relative to the
frozen full-context Oracle pseudo-reference. M9 remains an optional
development mechanism and is not included in the frozen primary candidate.

```text
EXTERNAL_RUNTIME_ISOLATION_ATTESTATION = MISSING
FORMAL_TEST_METHOD_RANKING = BLOCKED_PENDING_RUNTIME_ATTESTATION
TEST_BUDGET_GRID = NOT_FROZEN
TEST_REFERENCES = NOT_SEALED
```

No development result in this directory is a formal benchmark ranking or a
final wall-clock conclusion.
