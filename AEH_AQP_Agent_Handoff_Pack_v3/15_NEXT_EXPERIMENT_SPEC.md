# Frozen S2 Public Event-Cell Representation Repair Gate v1

## Research question

Can a deterministic planner-public grouping of the existing frozen H1 actions into event cells make event saturation beneficial on S2 without adding information, candidates or oracle calls?

## Isolation principle

Only ownership/state representation may change. The following must be byte- or row-identical where applicable:

- S2 cells, budgets and seeds;
- legal actions and action scores;
- oracle observations;
- materializer and evaluator;
- event reference used only after trace generation.

## Methods

| ID | Representation | Policy |
|---|---|---|
| R0-P0 | frozen H1 | positive probability |
| R0-P1 | frozen H1 | frozen saturation |
| R1-P0 | public event cells | positive probability |
| R1-P1 | public event cells | frozen saturation |

## Frozen R1 construction

1. Seed one cell per high-proxy island.
2. Exclude audit/uncovered windows from event-cell state; retain them under stable audit-owner IDs and never update their score through event-cell saturation.
3. Process orphan-local-peak actions chronologically.
4. Assign an orphan to an overlapping seed cell.
5. If none overlaps, assign it to the nearest seed only if public interval distance ≤ one frozen unit and combined span ≤ audited K3 core cap.
6. Otherwise create one standalone orphan cell.
7. Tie-break by distance, seed start and stable seed ID.
8. Do not merge seed cells transitively.
9. Preserve all legal actions and scores; only owner IDs change.

If the actual schema cannot represent these operations exactly, stop with `EXPERIMENT_BLOCKED`.

## Primary estimand

```text
Delta_sat_R1 = AUC(R1-P1) - AUC(R1-P0)
```

Secondary decomposition:

```text
Delta_repr_P0 = AUC(R1-P0) - AUC(R0-P0)
Delta_repr_P1 = AUC(R1-P1) - AUC(R0-P1)
```

Low-budget estimand: macro paired delta over B=5/10/20.

## Gate

`PUBLIC_EVENT_CELL_SATURATION_GO` requires positive primary and low-budget deltas, non-dominance by one S2 cell, valid CI lower bound above zero when resampling is defensible, and trace-confirmed redundancy reduction.

Otherwise use `PLANNER_ROUTE_REJECTED`. A positive representation-only effect does not rescue saturation.

## Non-claims

Even GO is single-video semi-synthetic evidence. It permits a minimal multi-video validation; it does not validate AEH-AQP, a full planner or cheap-feature engineering.
