# PSVR Core Physical Pilot

`MINIMAL_PHYSICAL_BASELINES = VALID`

`H-COV1 = REVISE`

`PSVR_CORE_INNOVATION_PILOT = WEAK`

Current best development method by macro physical AnytimeAUC_F1: `coverage_debt_psvr`.

## Physical matrix

- Corrected baseline runs: 36 (4 methods x 3 deadlines x 3 runtime replicates).
- Coverage-Debt runs: 9 (3 deadlines x 3 runtime replicates).
- Deadline misses, runtime failures, cache replay, future-proxy accesses, and unobserved-candidate queries: all zero.
- One runtime identity and one NVIDIA A800-SXM4-80GB; proxy and oracle GPU seconds are recorded per run.

Coverage-Debt final results:

| Deadline | Calls/run | Coverage | Max gap | F1 | Recall | AnytimeAUC_F1 |
|---|---:|---:|---:|---:|---:|---:|
| T_short | 1 | 0.023088 | 430 s | 0 | 0 | 0 |
| T_mid | 3 | 0.046176 | 210 s | 0 | 0 | 0 |
| T_long | 6 | 0.080808 | 200 s | 0.074074 | 0.038462 | 0.008466 |

Macro AnytimeAUC_F1 is 0.002822 versus 0 for every simple baseline. The T_long gain is reproduced in 3/3 runtime replicates, each with one unique matched event and no redundant query.

## Why H-COV1 is not accepted

The best simple gap trajectory is fixed Coverage-Interleave (macro normalized gap integral 0.151569), followed by Uniform-Temporal (0.156310). Coverage-Debt is worse at 0.158263. Its endpoint gaps equal Uniform-Temporal and are worse than fixed coverage. Thus the quality endpoint improves, but the preregistered gap-mechanism condition is false.

The generated `DECISION.json` field named `early_recall_gain_vs_best_simple` is not valid evidence: it was aggregated by lexicographic row order and includes T_long. Correct T_short+T_mid recall gain is 0. The H-COV1 quality check still passes independently through AnytimeAUC_F1.

## Interpretation

Coverage-Debt acceptance requires both a lower wall-clock gap integral than the best simple controlled method and improved physical AnytimeAUC_F1 or early recall, with no added deadline miss, no future proxy access, and all GPU cost counted. Mechanism-only improvement is explicitly rejected.

This is a three-replicate, one-video, one-query, one-A800 development pilot and not an independent statistical claim.

## Next highest-value experiment

Predeclare a coverage-first/debt-refinement action-allocation ablation. Compare it with fixed Coverage-Interleave and Uniform-Temporal using identical scan/query action counts, deadlines, guard, K3, hardware, and accounted GPU cost. Reject the route if it cannot retain the event gain while matching the best simple gap integral. Do not tune lambda/beta post hoc in the current pilot.
