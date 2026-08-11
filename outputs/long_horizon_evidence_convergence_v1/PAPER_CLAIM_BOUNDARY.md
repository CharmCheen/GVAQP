# Paper Claim Boundary

| Claim | Status | Evidence boundary |
|---|---|---|
| Anti-overmerge/continuity grouping improves recovery of the frozen V3 model-relative EventRelation under sparse query budgets. | PARTIALLY_SUPPORTED | 54 same-trace pairs, 3 independent videos, 3 selectors; reference is K3-defined/model-relative. |
| Current full K3 is better because verified negatives act as temporal barriers. | NOT_SUPPORTED | Barrier ablation median effect is 0. |
| Materialization is the bottleneck and dominates selector choice. | NOT_SUPPORTED | Pairwise selector difference is lower, but selector spread is higher; strong selector interaction exists. |
| The mechanism generalizes to human event continuity. | NOT_SUPPORTED | No human/official event-boundary reference. |
| The mechanism is selector-agnostic. | PARTIALLY_SUPPORTED | No K3 regression, but TemporalCoverage has mostly tie/low-gain behavior. |
| Hard-deadline superiority. | NOT_SUPPORTED | P0 is query-call replay. Guangzhou physical evidence is exploratory, single-source. |
| Deterministic temporal-bisection can improve deadline utility in the audited Guangzhou regime. | PARTIALLY_SUPPORTED | One source, one recovered event, same-source repeat. |
| MAB/RL/controller is a main innovation. | NOT_SUPPORTED | Repository evidence and prior-art audit reject it. |
