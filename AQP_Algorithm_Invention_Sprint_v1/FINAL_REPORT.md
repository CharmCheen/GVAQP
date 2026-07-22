# AQP Algorithm Invention and Falsification Sprint v1 — final report

## Strongest conclusion

`PHYSICAL_PILOT_NO_GO`. VERA is formally distinguishable from the closed unit-ranking and interval-pruning routes, and its physical operator is cheap on the assigned A100, but the exact frozen physical result must be judged by recall `0.038462`, F1 `0.052632`, and cost ratio `0.240987` together. The selected physical instantiation failed both frozen quality thresholds despite passing the cost threshold.

## 1. Candidates considered

- **VERA:** variable-resolution set-valued event-relation cover with padded inputs, disjoint ownership, and dense edges; selected (rubric score 0.846).
- **BOLT:** batch-optimal latency DAG; rejected (0.657) because batching alone did not earn algorithmic novelty.
- **WAVE:** workload-amortized event views with exact patching; rejected (0.725) because no frozen workload could falsify its amortization claim.

## 2–5. Selected algorithm, novelty, objective, properties

VERA minimizes predicted synchronized GPU seconds over a temporal plan DAG subject to an additive event-loss risk budget. An edge is either dense or returns a variable-cardinality EventRelation fragment. Padded windows provide context; half-open cores give one deterministic owner. The risk-discretized DP is exact for its upward-rounded model, has deterministic tie-breaking, and includes dense execution as a zero-risk feasible path. Unlike ARC it plans direct relation-producing cover edges; unlike SUPG it is not record selection under a renamed schema.

## 6. Headroom and failure region

The 69,120-cell grid (500 seeds/cell) found 1,620 all-placement robust-mean and 168 robust-p05 passing cells. The registered cell passed in mean, but boundary/event-correlated p05 recall/F1 fell below target; no non-perfect cell passed every correlated p05 model. This justified a mechanism pilot, not a guarantee. The physical processor introduced an unmodeled sampling error described in `diagnostics/PROCESSOR_SAMPLING_CAVEAT.md`.

## 7–8. Physical pilot and cost

The pilot ran in tmux with atomic checkpoints. It started `105` new calls: `20` dense calibrations, `70` enumeration calls, and `15` fallbacks. Selected-operator GPU cost was `1566.323` seconds versus estimated dense `6499.602` seconds; model load was `138.763` seconds and selected warm wall time `3211.315` seconds. The 200-call cap was respected: `True`.

## 9. Strengthened baselines

Native query-object AUCs and shared-operator reorderings are reported separately. VERA chronological same-cost AUC is `0.005540`. The best deployable shared-output label is `ALL_DEPLOYABLE_TIED` at `0.005540` (ties: `ABae_plus_EVENT_ENUMERATE|ARC_plus_EVENT_ENUMERATE|CLIP_RTG_plus_EVENT_ENUMERATE|MAP_M1_plus_EVENT_ENUMERATE|SUPG_plus_EVENT_ENUMERATE|VERA_chronological|public_proxy_plus_EVENT_ENUMERATE|uniform_random_plus_EVENT_ENUMERATE`); all such orderings share the identical 70 physical enumeration outputs and appended fallback at full coverage. Native ARC/MAP/CLIP/SUPG/ABae results retain their frozen 10-second query object. Component ablations expose ownership, exact deduplication, and fallback effects; DP/variable-resolution headroom remains simulator evidence.

## 10–12. Decision, current claim, next task

Final decision: `PHYSICAL_PILOT_NO_GO`.

Current paper claim: A formally distinct event-relation cover algorithm with simulated headroom, but its first frozen physical instantiation is falsified on the single strict video.

Exact next task: freeze a metadata-correct, post-processor-verified `EVENT_ENUMERATE` operator on disjoint held-out videos and run the smallest preregistered accuracy/cost calibration that can reject the operator hypothesis; do not tune against this strict reference or reopen closed ranking/pruning routes.
