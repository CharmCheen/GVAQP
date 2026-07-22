# Properties and proofs

## Theorem 1 — discretized global optimality

For a finite timeline DAG, nonnegative edge costs, upward-rounded additive edge
risks and fixed risk budget, the VERA recurrence returns a minimum-cost feasible
path in the discretized model.

**Proof.** Any cover ending at `j` has a unique last edge `a:i->j`; removing it
leaves a feasible prefix ending at `i` with the residual risk budget. If that
prefix were not optimal for its state, replacing it would make the full path
cheaper. Induction over increasing timeline position proves the recurrence;
enumerating all last edges proves completeness. Upward rounding preserves
feasibility for the original additive risk values.

## Corollary — modeled dense fallback dominance

When every unit has a zero-risk dense edge and dense is feasible, VERA's
predicted cost is no greater than dense because the dense path is in the
minimization domain. This does not guarantee measured runtime when the cost
model is wrong.

## Theorem 2 — unique ownership

If selected cores are disjoint and cover the timeline, every canonical point
belongs to exactly one core (using half-open intervals). Therefore every
reported event retained by the core-owner rule has at most one final owner.

## Proposition — deterministic canonical relation

Fixed fragments, half-open owner cores, frozen overlap matching, stable hashes
and lexical sorting produce the same final relation independent of fragment
arrival order. This is tested by row-order permutation before sealing.

## Non-properties

Physical errors need not be independent; event recall is not certified; the
risk profile is not identified from the strict video; and no submodular or
cross-video guarantee is claimed.

