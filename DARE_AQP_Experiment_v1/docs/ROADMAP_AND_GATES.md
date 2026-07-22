# Roadmap and gate routing

| Requirement from the DARE proposal | Current evidence/status | Route |
|---|---|---|
| P0 canonical anchor and oracle contract | Implemented for frozen pseudo-events; real typed oracle unresolved | Keep claims explicitly pseudo-event-only |
| P1 all-unit query-specific index | Frozen CLIP/X-CLIP/fusion executed for 347/347 units on A100; best CLIP linked cost is 311/347 (89.625% dense) | `UNIT_ORACLE_DARE_ACCELERATION_NO_GO`; freeze route |
| P2 residual estimator simulator | Implemented and run for 500 seeds with exact fixed-stage bounds | Public Gate B = NO_GO; retain raw coverage/cost artifacts |
| P3 end-to-end DARE replay | Not justified because Gate A is absent and public Gate B failed | Do not implement until A passes and a revised joint A/B gate is registered |
| P4 multi-video/human audit | Not available in the current artifact set | Required before any real-event or generalization claim |
| C0 hierarchical operator ceiling | Exact ANY/COUNT ceiling executed; physical recovery found numerical accuracy/abstention gates missing | `INTERVAL_OPERATOR_CONTRACT_BLOCKED`; preregister gates before call 1 |

## Gate A acceptance target

The idealized diagnostic first crosses the 80%-recall cost gate only when
24/26 pseudo-events are discovered in the first 24 calls.  This is not a fair
performance target for a real method, but it quantifies how far the current
certificate regime is from usefulness.  Gate A should report, for every frozen
signal:

- all-unit canonical-anchor and presence top-k coverage at k=5/10/20/24/50;
- blocked/prequential AUROC and AP;
- distinct events per query;
- cold and warm feature cost;
- the resulting Gate B cost curve, without choosing weights on strict labels.

The route should be rejected or revised if attainable signals leave total
certificate cost above the registered 70%-dense threshold.  Passing a ranking
metric alone is insufficient.

## Gate C0 result

Exact count-guided localization reaches 80% recall using 85 interval calls and
21 certifications.  With COUNT cost x1.25 it costs 36.7% of dense audit only
under constant-cost interval queries, but 449.5% when cost grows linearly with
duration.  It requires a fixed-cost fraction of at least 0.95 on the registered
grid to beat the 70%-dense gate.  Therefore C0 is conditional, not a strong GO.

## Why full Gate C is deferred

Residual-aware allocation, adaptive discovery, K3-safe materialization, and
accuracy-aware stopping add complexity but cannot repair a certificate whose
public fixed-stage cost is already near dense scan.  They become justified
only after Gate A demonstrates a signal strong enough to change the end-to-end
cost regime, or after a measured block-oracle pilot validates the narrow C0
cost/accuracy conditions.  Sequential stopping additionally requires alpha
spending or an anytime-valid confidence sequence; v1 makes no such claim.
