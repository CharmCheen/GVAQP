# Top-tier claim audit

1. **One-sentence novelty.** VERA compiles a heterogeneous timeline cover of set-valued event-enumeration and dense edges, with padded observation windows and disjoint relation ownership, to minimize measured semantic-operator cost subject to an event-level risk budget.
2. **Why not ARC.** ARC selects relevant clips and refines unit labels; VERA optimizes a cover whose physical edges directly return zero or more event objects and whose composition is part of the plan semantics.
3. **Why not SUPG.** SUPG selects records under precision/recall constraints. Renaming VERA windows as records loses the variable-cardinality relation fragment, overlap ownership, and alternative dense/enumeration edge cover.
4. **Why not ordinary retrieve-then-ground.** VERA does not rank candidate clips then ground them. Its selected pilot covers the entire timeline with a different set-valued physical operator and reconciles relation fragments by ownership.
5. **Formal property.** The DP is globally optimal for the upward-discretized additive-risk temporal DAG; risk rounding is conservative in that model, dense fallback is feasible, and half-open cores give unique ownership.
6. **Physical speedup.** Selected GPU seconds `1566.323` versus current-GPU dense estimate `6499.602`, ratio `0.240987`. This is meaningful only together with recall `0.038462` and F1 `0.052632`.
7. **Single-video evidence.** Every accuracy result is on one Qwen3-VL-defined pseudo-reference, not human truth. Operator cost is one A100 run. No generalization is established.
8. **Needed for VLDB/SIGIR.** Repair and independently freeze processor metadata; predeclare multiple held-out videos and human adjudication; calibrate operator risk on disjoint videos; compare end-to-end cold/warm workload cost; and reproduce gains against native and shared-operator baselines.
9. **Paper-route kill result.** Reject the route if metadata-correct, preregistered multi-video evaluation cannot simultaneously achieve event recall/F1 >= 0.80 and <0.70 dense GPU cost, or if the best strengthened baseline matches the relation-cover result without its novel components.

Current allowed claim: **A formally distinct event-relation cover algorithm with simulated headroom, but its first frozen physical instantiation is falsified on the single strict video.**

Final sprint decision: `PHYSICAL_PILOT_NO_GO`. This is not a top-tier-ready declaration.
