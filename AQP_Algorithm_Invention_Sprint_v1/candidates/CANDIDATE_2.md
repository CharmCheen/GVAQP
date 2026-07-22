# Candidate 2 — BOLT: Batch-Optimal Latency DAG

## Formal object

- **Input/output:** same EventRelation query, but primitive operations are unit
  presence, localize and certify tasks with precedence constraints.
- **State:** ready operator tasks, GPU memory, batch configuration, cache and
  remaining latency budget.
- **Objective:** minimize wall/GPU time through joint batch packing and
  escalation while preserving the exact logical task set.

## Algorithm

Build a precedence DAG of semantic tasks. At each layer solve a memory-bounded
batch-packing problem using measured subadditive batch runtimes; execute
uncertainty-triggered escalation and materialize events after all dependencies.
Dense is a fallback schedule.

## Property and complexity

For a frozen layer with batch size choices and additive item memory, exact
packing is a knapsack/partition DP; the full precedence-constrained scheduling
problem is NP-hard. A list scheduler can be bounded only under restrictive
identical-machine assumptions that do not match one GPU with nonlinear memory.

## Novelty challenge

The query semantics and logical plan are unchanged. LOTUS/task-cascade and
semantic scheduling work already optimize physical executions, and the task
explicitly excludes batching alone as novelty. Adding event postprocessing
does not repair this.

## Feasibility, counterexample and kill criterion

It is physically feasible on the current GPU, but requires many calls to
measure a batch-runtime surface. If Qwen visual prefill dominates and scales
linearly, batching saves little; if OOM forces batch size one, the mechanism
vanishes. Reject unless a non-batching semantic/query-plan contribution can be
identified before execution. No such contribution survived review, so BOLT is
not selected.

## Differences

It is not ARC/SUPG in implementation, but it can wrap either without changing
their algorithm. That is insufficient for this sprint.

