# BCEM Objective and Constraints

## 1. Legal-partition DAG

For ordered anchors (p_0,ldots,p_{m-1}), create vertices (0,ldots,m). Add edge (i\rightarrow j+1) for every legal group (G_{i:j}), except that no edge may start at `i>0` when the cut before it would make adjacent output intervals overlap (`e_{p_{i-1}} > s_{p_i}`). Every source-to-sink path is one legal non-crossing partition and every legal non-crossing partition is one path. This is the exact legal-partition engine shared by the evaluator-only ceiling and any public operator.

Let (L) be the maximum number of anchors reachable inside the 40-second cap. Candidate-edge construction takes (O(mL)) time and space. Counting all legal partitions uses

\[
count[0]=1,\qquad count[t]=\sum_{(i\rightarrow t)}count[i]
\]

with arbitrary-precision integers in (O(mL)). Explicit enumeration is output-sensitive and can be exponential; it is used only for small-instance verification.

## 2. Evaluator-only ceiling objective

The ceiling receives the frozen reference only in `ceiling.py`. For partition (Pi), it builds the minimal legal intervals and invokes the unchanged strict matcher and metrics:

\[
F_{ceil}(\Pi)=F1_{strict}(EventRelation(\Pi),R).
\]

The strict match objective is lexicographic maximum overlap-any cardinality and then total temporal IoU. Because predicted legal intervals and reference intervals are each temporally ordered and non-crossing, an optimal order-preserving matching exists. The exact ceiling DP tracks anchor-prefix position, last matched reference index, predicted-group count, and matched count; for equal states it retains maximum total IoU, then lower returned duration, then lexicographically smaller cut tuple. At termination it chooses maximum strict F1, then total IoU, then lower returned duration, then the canonical cut tuple. The selected partition is finally re-evaluated by the authoritative strict code.

If (E=O(mL)) legal group edges and (r) reference events, the unpruned exact ceiling DP has at most (O(m^2r^2)) count/match states and (O(Er)) outgoing match choices per layer; the implementation reports actual state counts. The small frozen instance and 40-second cap make it tractable. Exactness is tested against exhaustive partitions plus the authoritative evaluator on random small cases.

This is explicitly an evaluator-only oracle over **partition choice**, not a runnable method.

## 3. Hard constraints shared by all BCEM paths

Every output must satisfy:

- exact positive-anchor coverage;
- no queried negative strictly inside a group span;
- ordered non-crossing groups;
- 40-second core and 60-second output caps;
- at least one queried positive per event;
- explicit abstain rejection;
- deterministic canonical IDs and lineage;
- minimal convex-hull output, with no reference-derived boundary expansion.

## 4. Controlled baselines

`original_k3` restricts edges further: each consecutive anchor pair inside a group has at most one intervening unit. `k3_bridge_safe` restricts each consecutive pair to adjacent unit IDs. BCEM legality deliberately allows any unknown gap inside the duration cap unless a queried negative blocks it. This difference measures partition headroom; it does not change evidence or boundaries.

## 5. Public-only objective (conditional)

A runnable public BCEM objective is authorized only after `MATERIALIZER_HEADROOM_GO`. If authorized, it must be one frozen additive path cost

\[
C(\Pi)=\sum_{G\in\Pi} C(G)
\]

using only anchor IDs, queried negative barriers, unknown-gap length, public temporal geometry, frozen caps/priors, and public trace evidence. The shortest-path recurrence is

\[
dp[t]=\min_{i\rightarrow t}\{dp[i]+C(G_{i:t-1})\}.
\]

Ties are resolved by the lexicographically smallest ordered anchor tuples. This yields exact optimality for the frozen additive objective in (O(mL)) time and (O(m)) DP space after edge construction.

After the independently frozen headroom rule returned `MATERIALIZER_HEADROOM_GO`, the public objective was frozen—before public evaluator execution—as `CAP_NORMALIZED_DESCRIPTION_LENGTH_V1`:

\[
C(G)=1+\frac{span(G)}{40\text{s}}+
        \frac{10\text{s}\cdot \#unknown\_internal\_units(G)}{40\text{s}}.
\]

The event-open unit is a parameter-free partition-cardinality term. The other terms are normalized only by audited constants already present in the strict schema. Public support cost is zero because the trace has no defensible pairwise same-event evidence. No weight was selected from strict-reference metrics and no grid was run. `FROZEN_PUBLIC_BCEM_OBJECTIVE.json` is the authoritative freeze.
