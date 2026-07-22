# Agent Execution Contract

## 1. Scope discipline

The task specification must state objective, input paths, immutable paths, authorized compute/oracle calls, expected matrix, metrics, gates and output directory. If a missing choice would change the paper conclusion, stop with `TASK_SPEC_INCOMPLETE`.

## 2. Evidence hierarchy

- A design is not an implementation.
- An implementation is not an experiment.
- A single run is not a robust result.
- An evaluator-only ceiling is not an online algorithm.
- Reproducing a metric table from itself is not independent verification.

Every conclusion must cite source path, config, seed, artifact and hash.

## 3. Leakage boundary

Planner-public inputs may include units, timestamps, cheap features, public tracks, budgets and observations already returned by `OracleAccessor`.

Evaluator-only inputs include dense labels, full event reference, match tables, future oracle outcomes and any feature derived from them.

The planner API must make evaluator-only access structurally difficult. Passing a DataFrame containing hidden labels and promising not to index them is insufficient for a new implementation.

## 4. Immutable artifacts

Never modify:

- `clean_baseline_benchmark_v2_strict`;
- completed experiment directories with a final manifest;
- raw oracle responses or reference tables;
- the mathematical reference;
- historical failed attempts used for audit lineage.

New work goes to a new versioned directory.

## 5. Compute and oracle accounting

- Record physical VLM calls separately from logical oracle calls.
- Every online query is charged through `OracleAccessor`.
- Preserve retries and identify the authoritative attempt.
- Record wall time, GPU time, peak memory and cache behavior where applicable.

## 6. Fair comparisons

- Same event reference, budgets and matcher.
- Shared materializer comparisons for planner claims.
- Native and controlled/materializer-normalized baselines both reported.
- Exact seeds/config matrix; no hidden retries or cherry-picking.
- Strongest baseline means the best valid predeclared baseline, not a convenient subset.

## 7. Tuning restrictions

- The strict video is a frozen test/diagnostic video, not a development set.
- No training or threshold selection on evaluator outcomes from it.
- Synthetic/semi-synthetic gates may diagnose mechanisms but cannot establish real-video generalization.
- Cross-video parameters must be frozen before held-out evaluation.

## 8. Claim language

Use qualifiers such as:

- “under the strict single-video VLM-defined oracle”;
- “under a shared BB-EM materializer”;
- “evaluator-only estimated ceiling”;
- “empirical audit diagnostic.”

Do not say “guarantee,” “complete,” “real cut-in retrieval” or “generalizes” unless the required evidence exists.

## 9. Completion standard

A run is complete only when:

- expected/actual matrix matches;
- no duplicate queries or budget violations;
- metrics recompute from primitive artifacts;
- replay/rematerialization passes;
- independent review has no unresolved high/blocking findings;
- file manifest validates;
- decision follows the frozen gate.

## 10. Final response contract

Report:

1. exact decision;
2. key metrics and denominators;
3. what changed and what remained frozen;
4. commands and resources used;
5. oracle call counts;
6. failures/limitations;
7. artifacts created;
8. claim impact;
9. exact next action.

