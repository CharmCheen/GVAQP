# Research state

## Objective

Develop and falsify DARE-AQP: biased all-unit event discovery coupled to an
independent finite-population residual-event audit, with recall-aware stopping
and full cost accounting.

## Established findings (direct artifacts)

- The frozen strict benchmark contains 347 eligible units and 26 VLM-defined,
  non-human-adjudicated pseudo-events with unique anchor times.
- The existing handoff records MAP/M1 AUC 0.388056, oracle-informed reorder AUC
  0.664458, public blocked-CV AUROC 0.548282, and legal candidate coverage
  20/26.  These support search headroom but not a deployable search signal.
- Existing audits report K3-safe close to a legal materialization ceiling;
  this motivates freezing materialization, but does not prove it is optimal on
  future human-event datasets.
- Frozen Gate A completed 347/347 CLIP and X-CLIP scores. CLIP improved anchor
  AUROC from 0.535945 to 0.616343 and K3-safe event-F1 AUC from 0.354212 to
  0.538949, but found only 8/26 events in the first 24 calls and its best Gate B
  total cost remained 311/347 (89.625% dense).

## Active hypotheses

- H-C0: exact hierarchical COUNT/ANY operators help only when long-interval
  costs are dominated by fixed overhead.
- H-Calt: real interval accuracy or duration-dependent cost eliminates the
  exact ceiling's apparent advantage.

## Rejected or paused directions

- Closed H1 candidate universes: rejected for the target method because direct
  evidence reports only 20/26 event coverage.
- More merge/split heuristics: paused because measured materialization headroom
  is negligible relative to acquisition headroom.
- Hypothesis saturation / exploration / counterfactual planner route: rejected
  by the completed mechanism gate on frozen public H1.
- H-A unit-ranking route: rejected by one-shot frozen Gate A. CLIP improved
  ranking quality but no public signal crossed the registered 70%-dense joint
  Gate A/B threshold; X-CLIP and frozen fusion were worse.

## Important assumptions

- `CertifyEvent` reveals pseudo-event identity and anchor at the registered
  cost.  This is simulated, not observed real-oracle behavior.
- Canonical anchors are unique at 10-second unit resolution in this population.
- Fixed-stage simple random audit is operationally feasible.

## Unresolved uncertainty

- Public Gate B is NO_GO: the cheapest tested public fixed stage meeting the
  80%/90% criterion costs 315 calls (90.8% of dense scan).
- The oracle-anchor ceiling defines an idealized feasible region but does not
  prove that weak public search is the cause or that Gate A can approach it.
  It first crosses the pilot gate at B=24 after ideal discovery of 24/26 events;
  B=23 costs 246 calls and remains just above the threshold.
- Minimum empirical fixed-cell coverage was 0.938.  Small-population exhaustive
  tests support the exact implementation, but this below-0.94 diagnostic cell
  must remain visible rather than being averaged away.
- Why the broad frozen query is poorly aligned with the pseudo-event population;
  this remains explanatory uncertainty, not authorization for post-hoc tuning.
- The physical C0 task cannot start compliantly because the frozen C0 contract
  has no numerical ANY sensitivity/false-negative, COUNT accuracy/undercount,
  or abstention acceptance thresholds. Compute and the exact strict VLM are
  available; the decision contract is the blocker.
- Real certification/audit cost and human anchor agreement.
- Cross-video and cross-predicate validity.
- Gate C0 is `CONDITIONAL_C0_ONLY`: count-guided 80% recall uses 85 interval
  calls plus 21 certifications, but COUNT x1.25 needs fixed-cost fraction 0.95
  to beat 70% dense; its linear-duration cost is 4.495x dense.
- Frozen Gate A evaluator preflight reproduces current-proxy weakness: anchor
  AUROC 0.536, 4/26 distinct events in top 24, and linked cost 318/347.

## Next highest-value action

Freeze unit-ranking DARE as `UNIT_ORACLE_DARE_ACCELERATION_NO_GO`. Before the
conditional C0 physical pilot can spend call 1, preregister numerical ANY and
COUNT accuracy/abstention gates independently of physical interval results.
Only then may the bounded operator pilot measure accuracy and duration cost.

## Execution status

`INTERVAL_OPERATOR_CONTRACT_BLOCKED` as of 2026-07-11. Gate A remains sealed.
Both exact frozen models ran on the
assigned A100 for all 347 units. CLIP improved top-24 event discovery from 4 to
8 and event-F1 AUC from 0.354212 to 0.538949, but its best linked Gate B cost is
311/347 (89.625% dense), above the registered 70% threshold. X-CLIP and frozen
fusion were worse. All four rankings are sealed; physical exact-oracle VLM
calls remained zero. The independent fail-closed audit passed all 14 checks and
the package is sealed. The subsequent C0 physical recovery found the A100 and
exact strict 32B model available but made 0/160 calls because required frozen
physical accuracy thresholds are absent.
