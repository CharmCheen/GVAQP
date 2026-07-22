# Properties, Proof Sketches, and Counterexamples

## Exact invariants

### Positive-anchor coverage

Every DAG path starts at anchor index 0, ends at (m), and uses consecutive slice edges. Slices are disjoint and exhaustive, so each queried-positive anchor appears exactly once. The empty trace has the unique empty partition.

### Barrier safety

An edge is absent whenever any queried negative lies strictly between its first and last anchors. Every multi-anchor output corresponds to one present edge, so no output crosses a queried-negative barrier. Boundary negatives outside the first/last anchor do not shrink the minimal interval.

### Boundedness

Every edge is admitted only if its minimal interval satisfies both caps. Emission uses that same interval without expansion, so every output satisfies both; the 60-second property follows redundantly from 40 seconds in the frozen config.

### Determinism

Inputs are canonicalized as sorted unique IDs, candidate edges are generated in anchor order, objective ties use a documented tuple order, and identity hashes canonical JSON. Input row order cannot affect the EventRelation.

### Exact additive optimization

Every legal partition corresponds bijectively to a DAG path. Additive group cost equals path cost, so the acyclic shortest-path recurrence examines every feasible final edge and returns a global minimum. No greedy or submodular claim is made.

## Counterexamples and non-claims

1. **Unqueried is not negative.** Positives at units 0 and 2 with unit 1 unqueried may legally form one event; marking unit 1 negative would incorrectly forbid it.
2. **Abstain is not negative.** An abstain between two positives supplies neither a hard barrier nor positive support. This gate rejects it because no public abstain policy is frozen.
3. **Positive evidence does not identify sameness.** Two adjacent positives may be one latent event or two; both joined and split partitions are legal absent further semantics.
4. **A queried negative can add value.** Positives on each side of a newly observed negative must split, preventing an evidence-invalid merge.
5. **A wider legal interval can match an unanchored reference.** Overlap-any may reward an interval whose anchors belong to another reference. Therefore the ceiling reports anchor-certified matches separately and a gain dependent only on unanchored overlap cannot justify a public operator.
6. **Maximum F1 is not additive.** The evaluator-only ceiling requires a reference-aware state DP; it is not the public additive recurrence.
7. **Greedy optimality is not claimed.** Choosing the locally best split can change prediction count and global one-to-one matching.
8. **Completeness is scoped.** The engine is complete for the stated minimal-convex-hull legal partition model, not for arbitrary boundary expansion, actor identity, or unseen events.

## Incremental locality caveat

The 40-second cap bounds which legal group edges a new observation can affect, but a changed local edge can alter the globally optimal path tie or cost downstream. A correct incremental implementation may reuse unaffected prefix/suffix summaries, but it must fall back to or equal full batch reconstruction. Local recomputation size is an implementation diagnostic, not a proof by itself.

The implemented incremental interface indexes the 347-unit geometry once, then rebuilds the exact DAG only over the observed evidence table after each update. It therefore does not rescan the video after initialization. It exposes the cap-reachable affected anchor suffix and a full-state fallback. This is incremental observation maintenance with exact batch-equivalent reconstruction, not a claim of asymptotically optimal dynamic shortest-path maintenance.

## Recovered non-crossing counterexample and repair

Independent review found that monotone unit endpoints do not imply disjoint unit intervals: frozen units 345 and 346 overlap. Before the repair, the split partition `((345,), (346,))` was admitted and emitted overlapping events. Legal cut construction and the invariant/emission checks now enforce `end(left) <= start(right)`. A regression test uses the same overlapping-interval geometry. A full 738-trace equivalence audit is required because this formal correction postdates the original ceiling/public replay.

The same geometry shows why barrier scope must remain explicit: a singleton positive anchor at unit 346 temporally intersects neighboring unit 345. Under the audited K3 barrier predicate, unit 345 is not *strictly between* the singleton's first and last anchors and therefore is not crossed. Treating every temporal intersection as a barrier would change the frozen operator semantics and can make otherwise valid positive evidence infeasible; that alternative is not introduced post hoc in this gate.

## Evaluator matching tie caveat

The benchmark fixes cardinality and total-IoU objectives but delegates exact equal-score assignment ties to SciPy. Primary event-F1 is invariant to which equal-score maximum-cardinality assignment is returned. Boundary attribution can differ under exact ties and must be interpreted as diagnostic.
