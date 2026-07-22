# Candidate 1 — VERA: Variable-resolution Event-Relation AQP

## Formal object

- **Input:** video timeline, event predicate/contract, typed operator profiles,
  optional frozen public strata, event-quality target and cost budget.
- **Output:** `ApproxEventRelation` with event identity, boundaries, evidence
  windows, ownership core and lineage.
- **State:** timeline position, discretized risk budget, cache state, executed
  window ledger and deterministic relation-reconciliation state.
- **Operators:** `EVENT_ENUMERATE`, optional `UNIT_PRESENCE`/dense patch,
  `BOUNDARY_REFINE`, and `RECONCILE_RELATIONS`.

## Algorithm

Compile all legal variable-resolution ownership cores and padded input windows
into a DAG. Solve a risk-constrained shortest path/DP minimizing predicted GPU
seconds. Execute relation-valued windows, assign every reported event to one
core, reconcile overlap duplicates, and invoke a frozen dense fallback on
unknown/parser/resource failure. Dense execution is itself a legal plan.

## Objective and property

Minimize GPU seconds subject to event recall/F1 at least 0.80 and cost below
0.70 dense. With upward-discretized additive risks, the DP is globally optimal
over the registered plan graph. Because dense edges are included, predicted
cost is never worse than the dense fallback. Core ownership makes final event
rows single-owner and reconciliation deterministic.

## Complexity

For `N` positions, `A` legal window edges and integer risk budget `K`, time is
`O(AK)` and space `O(NK)` with parent reconstruction. Execution cost is the
sum of selected semantic operators; reconciliation is `O(R log R)` for `R`
reported event rows.

## Required assumptions

The optimizer requires frozen cost/risk profiles and additive ownership-core
risk. These are not inferred from the strict reference online. Physical
accuracy may be arbitrarily correlated; simulation includes adversarial
placement. No distribution-free recall certificate is claimed.

## Why physical speedup is possible

One enumeration call may return multiple event objects and own 50 seconds,
versus one Boolean result for a 10-second dense unit. A 50-second-core cover
needs 70 calls; it meets the 70% dense cost target if mean enumeration cost is
less than 3.47 unit calls.

## Exact distinctions

- **ARC:** ARC refines per-frame predicate scores into relevant clips. VERA
  compiles a plan of set-valued operators and directly composes EventRelations.
- **SUPG:** SUPG selects records using a proxy threshold and statistical
  sampling. VERA chooses record *granularity/operator type* and reconciles
  variable-cardinality relation fragments; intervals cannot be trivially
  renamed fixed records without losing the plan decision.
- **Prior failed methods:** no unit ranking, saturation, exploration,
  counterfactual materialization, Boolean ANY pruning or audit certificate is
  used as the speedup mechanism.

## Feasibility and falsification

Current Qwen3-VL, video and exact dense reference support a bounded pilot.
Strongest counterexample: 0.7-second events occur between sampled frames or
long-window context causes omission/hallucination, while runtime grows at least
3.47x. The decisive experiment is a frozen full-timeline 50-second-core/5-second
margin enumeration cover with per-call GPU and output lineage. Kill if recall
or F1 is below 0.80, or cost is not strictly below 70% dense.

## Paper contribution if successful

A typed set-valued temporal semantic operator, globally optimized
variable-resolution relation cover, ownership/reconciliation semantics and a
physical cost-quality result against strengthened baselines. Multi-video
validation would still be required.

