# Frozen S2 Public Event-Cell Representation Repair Gate v1

## Decision

`PLANNER_ROUTE_REJECTED`.

The exact frozen R0 replay reproduced all 900 P0/P1 seed-policy rows and every budget metric with maximum absolute difference 1.11e-16. R1 changed only owner identity; actions, scores, oracle mappings, candidate masks, budgets, seeds, materializer, matcher, evaluator and AUC rule remained frozen.

## Pre-registered gate and result

Primary R1 P1-P0 AUC: `-0.003501139`. Low-budget B=5/10/20 macro delta: `+0.000170252`. Representation-only R1-P0 minus R0-P0: `+0.000000000`. Representation-plus-saturation R1-P1 minus R0-P1: `+0.000476395`.

The 15 S2 parameter cells are repeated perturbations of one video/reference, so they are not a defensible independent resampling unit. No confidence interval is claimed; the exact paired cell and seed distributions are provided.

## Representation composition

R0 has 87 nonnegative event-hypothesis owners plus one ownerless audit state. R1 has 80 event cells and 25 stable audit owners. It starts from 55 high-proxy seeds; 7 orphan sources attach to seeds and 25 remain standalone. No seed is merged with another seed.

## Identity and leakage

All per-instance action-universe, score/probability and oracle-mapping hashes match between R0 and R1. R1 was frozen and hashed before formal evaluation. Its builder accepts no event references, dense labels, event IDs, matches or future outcomes. Audit owners use negative internal IDs and produced zero saturation triggers/applications.

## Mechanism activation

R1-P1 saturation triggers: 4735; applied-to-remaining-owner cases: 3792; one-step output changes: 2696; selections differing from the unsaturated ordering: 32614.

## Causal diagnosis

R1 reduced the mean within-cell redundant-query rate at B=100 from 0.480800 under R0-P1 to 0.339733 under R1-P1, so the representation repair activated in the intended structural direction. Nevertheless, R1 P1-P0 AUC was negative in 15/15 S2 cells. Mean budget deltas were B5 -0.000344, B10 +0.000623, B20 +0.000232, B50 -0.004051, B80 -0.006990, and B100 -0.004478. The tiny positive low-budget macro average is therefore followed by larger mid/high-budget harm and cannot rescue the negative primary AUC.

## Completion and accounting

Completed 1800/1800 method-seed-cell runs, 15/15 S2 cells, and 4/4 methods. Physical VLM calls: 0. Baseline reruns: 0. Independent review: `PASS`.

## Interpretation and competing explanation

The primary gate, not the representation-only effect, determines the route. These are single-video, oracle-relative, evaluator-derived S2 perturbations; they do not establish cross-video or human-GT performance. A remaining competing explanation for any cell variation is interaction with the frozen evaluator-derived AUROC/recall perturbations rather than a general operational ranking signal.

## Exact next task

Design, but do not conflate with the completed planner gate, a separate Barrier-Constrained Event Partition/Materialization operator and fixed-trace experiment: formalize EventRelation partitioning with positive-anchor coverage, queried-negative barrier safety and bounded spans; derive an exact or provably correct DP plus incremental maintenance; compare selector-agnostically against K3, K3-safe, and fixed-evidence partition ceilings.

Stop after this sealed gate. Do not execute that task here.
