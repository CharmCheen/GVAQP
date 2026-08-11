# Final Contributions (Current, Maximum Two Defensible Candidates)

## Contribution 1 — Problem/measurement candidate

**Claim:** Sparse expensive semantic verification for an event query introduces a downstream relation-materialization problem: the same verified unit trace can yield very different event retrieval results depending on how anchors are coalesced.

**Novelty:** Video/AQP work emphasizes proxy-based selection, aggregate estimation, tracks, or frame predicates. The candidate distinction is an explicit query-time quality object: a partial semantic observation relation materialized into an EventRelation.

**Evidence:** Frozen V10 model-relative substrate; 54 exact same-trace P0 pairs across 3 independent source videos; median K3−K0 F1 `+0.1457`.

**Scope:** One driving-response predicate; Qwen model-relative unit labels and K3-defined reference events.

**Risk:** High. A reviewer can view this as ordinary temporal coalescing, and the reference construction favors its own grouping family. This contribution is not paper-ready without P0 independent continuity evidence.

## Contribution 2 — Mechanism/operator candidate

**Claim:** Under the released sparse-query regime, local temporal continuity grouping prevents the global-anchor overmerge failure of a naive materializer.

**Novelty:** The claim is deliberately not “negative barriers solve event topology.” The observed operator is simple C1 gap-limited grouping, which gives nearly all P0 gain.

**Evidence:** Same-trace C0→C1 mean/median ΔF1 `+0.1738/+0.1377`, 40 positive / 14 equal / 0 negative cells. C2 duration adds little; C3 queried-negative barriers have median `0`; current K3 extras have no positive marginal effect.

**Scope:** A conditional, model-relative mechanism result. It should be presented as a correctness/quality-contract baseline unless independent evidence demonstrates a non-obvious general property.

**Risk:** Very high algorithmic-novelty risk. This is currently a supporting operator, not sufficient as a standalone SIGMOD/VLDB algorithm contribution.

## Explicitly not selected

- MAB/RL/VOI controller: rejected by repository evidence and close prior work.
- Verified-negative barrier semantics: not a measured main mechanism in the P0 traces.
- Hard-deadline executor: one-source exploratory physical result only; supporting systems context, not a main contribution.
