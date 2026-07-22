# Optimization objective

## Primary program

Given a frozen operator-profile table `Theta`, VERA chooses a plan `P`:

```text
minimize    predicted_gpu_seconds(P)
subject to  predicted_event_recall(P) >= 0.80
            predicted_event_f1(P)     >= 0.80
            predicted_cost(P) / dense_cost < 0.70
```

If no approximate path is feasible, it returns the dense path. In evaluator
simulations, quality is measured rather than predicted and is never exposed to
the online planner.

## Discretized dynamic program

Let `K` be the integer risk budget after rounding each edge risk upward to a
registered quantum. Define `D[j,k]` as minimum cost of a legal cover of prefix
`[0,j)` using at most risk `k`. For every edge `a=(i,j)` with integer risk
`rho(a)`:

`D[j,k] = min_a D[i,k-rho(a)] + c(a)`.

Tie-breaking is: lower cost, lower risk, fewer physical calls, shorter maximum
input window, lexicographically smaller operator/edge sequence. Dense edges
have zero modeled risk.

## Adaptive escalation

Physical execution may replace an edge with its registered fallback after
`UNKNOWN`, parse failure or resource failure. This is not a post-hoc plan
search: the fallback transition and its cost are part of the frozen state
machine. Outcome-dependent discretionary tuning is prohibited.

## Why a DP is warranted

Variable window lengths and overlap margins make local cost-per-second choices
non-optimal near video ends, heterogeneous public strata and risk budgets. The
timeline DAG provides optimal substructure after ownership cores make edge
risk/cost additive. If overlap interactions or shared batches make them
non-additive, the DP property no longer applies; those variants require an
expanded state or are reported only as heuristics.

## Dense fallback

Dense unit edges are embedded in the same plan graph. Therefore, conditional
on correct nonnegative cost estimates and a feasible dense plan, the optimizer
cannot return a plan with predicted scalar cost above dense. This statement is
about the cost model; measured runtime may contradict it and is checked after
execution.

