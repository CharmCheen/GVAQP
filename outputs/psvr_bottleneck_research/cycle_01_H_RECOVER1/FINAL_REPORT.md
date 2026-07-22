# H-RECOVER1 recoverability audit

`H-RECOVER1 = COMPLETE`

## Scientific uncertainty

Does failure occur before scan exposure, during candidate generation/retention, during
VERIFY ordering/budgeting, or after an oracle-positive materialization?

## Frozen diagnostic

This evaluator reuses 72/72 H-EXPOSE2 R3 durable traces and performs zero physical calls.
All sequence generators consume only public unit metadata and frozen action counts. Every
label/event-derived output is marked `evaluator_only`.

## Candidate-generation ceiling

- positive_unit_to_proxy_rate: 1.000000
- positive_proxy_to_candidate_rate: 1.000000
- positive_candidate_to_frontier_rate: 1.000000
- positive_frontier_survival_rate: 1.000000

## Task bottlenecks

- **V0_Q1**: FRONTIER_OR_VERIFY_ORDER_LIMITED (secondary VERIFY_BUDGET_LIMITED, confidence high).
- **V0_Q2**: SCAN_EXPOSURE_LIMITED (secondary VERIFY_BUDGET_LIMITED, confidence moderate).
- **V1_Q1**: SCAN_EXPOSURE_LIMITED (secondary VERIFY_BUDGET_LIMITED, confidence high).
- **V1_Q2**: DEADLINE_FLOOR (secondary SCAN_EXPOSURE_LIMITED, confidence high).


## Adversarial interpretation

The V1 `DEADLINE_FLOOR` label is a floor at the frozen planned 12-scan action ceiling, not
proof of an intrinsic wall-clock floor. Median conservative additional-scan feasibility is
46.0;
realized slack therefore keeps conservative scan/VERIFY allocation as a competing cause.
V0_Q1 ordering regret is trace-conditional: counterfactual oracle choices could alter later
frontier states, so its ceiling is diagnostic rather than a realizable policy.

## Decision

`H-RECOVER1 = COMPLETE`. The bottleneck is heterogeneous: V0_Q1 exposes an ordering loss,
V0_Q2 is a positive control with additional exposure headroom, and both V1 tasks are scan
exposure floors at the frozen action count. Continue to the preregistered H-BOTTLE2 Scan ×
VERIFY factorial; this diagnostic alone does not accept a method.
