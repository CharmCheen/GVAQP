# Candidate 3 — WAVE: Workload-Amortized Video Event views

## Formal object

- **Input:** a distribution or finite workload of event predicates over videos,
  storage/build budget and per-query EventRelation targets.
- **Output:** a selected set of cached semantic event views plus a query-time
  exact patch plan.
- **State:** predicate-containment lattice, cached relation fragments,
  freshness/version state and workload frequencies.
- **Operators:** query-agnostic semantic index, predicate-specific event view,
  cached embedding reuse, exact patch and reconciliation.

## Algorithm

Generate candidate reusable views, estimate build/storage/maintenance savings,
and solve a submodular-knapsack or ILP view-selection problem. At query time,
rewrite an EventRelation query to the best contained cached view and patch the
uncovered predicate/timeline region. Dense remains a fallback.

## Formal property

Under monotone submodular workload savings and a cardinality/storage budget, a
standard greedy view selector has the usual `(1-1/e)` bound; predicate
containment and maintenance may violate these assumptions and would need a
separate proof. Cold-to-warm break-even follows from build cost divided by
per-query savings.

## Differences

It is not ARC/SUPG record selection, but workload-aware semantic view selection
is close to materialized-view and predicate-cache literature. Its event schema
adds specificity, not necessarily algorithmic novelty.

## Feasibility, counterexample and kill criterion

The current assets contain one strict predicate/video and no frozen query
workload or update model. Any amortized advantage could be manufactured by
choosing the number of repeated queries. A bounded single-query pilot cannot
distinguish success. Kill under current assets unless a real multi-query
workload is frozen independently. WAVE is therefore not selected.

## Paper path if later revived

It would require multiple videos, diverse related predicates, query frequency
and update traces, cache baselines and a maintenance-cost evaluation—not this
single-video sprint.

