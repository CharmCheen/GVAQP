# Formal EventRelation Materialization Model

## 1. Frozen inputs and observation states

Let the frozen `UnitTable` be an ordered sequence (u_0,ldots,u_{n-1}), where unit (u_i) has a stable integer ID and half-open public interval (I_i=[s_i,e_i)). IDs, starts, and ends are monotone in the strict benchmark. Consecutive intervals need not be disjoint; in particular, the final two frozen units overlap.

At budget (B), the saved trace induces disjoint sets:

- (P_B): queried units whose explicit observation string is `positive`;
- (N_B): queried units whose explicit observation string is `negative`;
- (A_B): explicitly queried `abstain` units, if the schema admits them;
- (U_B): all units not queried by the prefix.

This gate observes (A_B=\varnothing) in all frozen traces. The implementation nonetheless rejects abstain rather than mapping it to negative. Membership in (U_B) is unknown evidence, not negative evidence. Conflicting duplicate observations are invalid; identical duplicate rows are canonicalized to one observation.

## 2. Positive anchors and barriers

Write the positive anchors in temporal order as (p_0<\cdots<p_{m-1}). A queried negative (q\in N_B) is a **negative barrier** for anchors (p_i<p_j) iff (p_i<q<p_j). A gap unit between anchors is **unqueried** iff it lies in (U_B); such a unit may be included in an output interval but never becomes an anchor or barrier.

Here “crosses a queried-negative unit” has the authoritative audited K3 meaning: the event's anchor slice straddles that negative in UnitTable order. It does not mean arbitrary temporal intersection with a neighboring unit interval. This distinction is material because the frozen terminal units overlap in time; changing to an any-temporal-overlap exclusion would be a different barrier semantics, not a repair of the frozen one.

## 3. Legal event group

A legal event group is a nonempty contiguous slice of the anchor sequence

\[
G_{i:j}=(p_i,p_{i+1},\ldots,p_j),\qquad 0\le i\le j<m,
\]

with output interval

\[
J(G_{i:j})=[s_{p_i},e_{p_j}).
\]

It is legal exactly when:

1. no (q\in N_B) satisfies (p_i<q<p_j);
2. (e_{p_j}-s_{p_i}\le D_{core}=40\) seconds;
3. (e_{p_j}-s_{p_i}\le D_{out}=60\) seconds;
4. its support is exactly the listed queried-positive anchor IDs.

The 60-second test is retained for semantic completeness but is redundant under the 40-second core cap. The minimal convex hull makes the group evidence-faithful: it contains at least one positive anchor and performs no evaluator-informed expansion.

## 4. Legal partition and EventRelation

A legal partition is an ordered list

\[
\Pi=(G_{0:c_1},G_{c_1+1:c_2},\ldots,G_{c_{k-1}+1:m-1})
\]

of legal groups. Thus every positive anchor is covered exactly once, groups are temporally ordered and non-crossing, and no group crosses a queried-negative barrier. If (m=0), the unique legal partition is the empty partition and the EventRelation is empty.

Non-crossing is an interval condition, not merely an anchor-ID condition: for every adjacent pair of groups `(G,H)`, `end(J(G)) <= start(J(H))`. Equivalently, a cut between consecutive anchors `(p_t,p_{t+1})` is admissible only when `e_{p_t} <= s_{p_{t+1}}`. If overlapping anchors cannot legally merge because of a barrier or duration cap, no legal partition exists; the engine must report infeasibility rather than emit crossing events.

The predicted **EventRelation** is the ordered relation of materialized rows containing canonical event ID, interval, positive-anchor support, observed evidence lineage, configuration hash, and predecessor/successor order. It is a partition of evidence, not a claim that binary presence observations identify latent event identity.

## 5. Ambiguity

- **Merge ambiguity** exists for an adjacent cut location (t) when some legal partition joins (p_t,p_{t+1}) in one group and another legal partition separates them.
- **Split ambiguity** for a legal multi-anchor group exists when at least one internal cut yields two legal subgroups.
- A **barrier block** is a maximal consecutive anchor subsequence containing no queried negative between consecutive anchors. Duration bounds may still require or permit cuts inside a block.

These are properties of the legal partition set. They are not inferred event labels.

## 6. Canonical identity and lineage

For fixed observations and configuration, a chosen partition is canonicalized by ordered anchor tuples. The relation hash is SHA-256 over the schema version, sorted positive and negative IDs, explicit abstain IDs, caps, objective ID, and ordered group anchor tuples. Event (r) receives ID `bcem_<relation-hash-prefix>_event_<r:04d>`. Input row order therefore cannot alter identity.

Lineage records each event's anchor tuple, interval, relation hash, prior relation hash (for incremental execution), and transition type. Event identity is deterministic for a state/configuration, not persistent across changed states; lineage provides the cross-state correspondence.

## 7. Incremental transition

An incremental state is

\[
S_B=(P_B,N_B,A_B,\Pi_B,h_B).
\]

Applying one new observation first validates that it does not conflict with prior evidence, updates exactly one evidence set, and computes (S_{B+1}). A positive insertion may create new legal joins with nearby anchors; a negative insertion may invalidate groups that cross it. Because every legal group spans at most 40 seconds, only anchors within the cap-reachable temporal neighborhood can participate in newly created or invalidated group edges. Batch recomputation remains the semantic reference. Incremental output is correct only when its canonical partition, intervals, IDs, and relation hash equal batch recomputation exactly.

## 8. Non-identifiability and claim boundary

Presence observations plus barriers do not identify the true event partition. This model defines a constrained physical operator over observed evidence. The evaluator-only ceiling may ask which legal partition best matches the frozen reference; a runnable operator may not access that reference.
