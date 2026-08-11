# SCAN Optimization Headroom Audit — Frozen Protocol

```text
POLICY_TRUST_MODEL = TRUSTED_FROZEN_IN_REPOSITORY_POLICIES
ARBITRARY_EXTERNAL_POLICY_SUBMISSION = NOT_SUPPORTED
METHOD_EXPERIMENT = ALLOWED_WITH_CODE_AUDIT
PUBLIC_BENCHMARK_CLAIM = DEFERRED
REFERENCE_SEMANTICS = FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE
```

## Objective

Determine whether the current fixed-fidelity SCAN operator has exploitable
scheduling headroom, identify whether it comes from temporal coverage,
path-aware batching, or observation-conditioned refinement, and stop adding
algorithmic complexity when the evidence does not support it.

## Frozen causal policies

1. Sequential;
2. Random without replacement (50 seeds);
3. Uniform-prefix;
4. Anytime Largest-Gap;
5. Macro-region Largest-Gap with three contiguous units per selected region.

Every causal policy receives only public unit boundaries, scanned unit IDs,
current unit ID, remaining budget, past action costs, and revealed candidate
IDs. The evaluator alone holds references, candidate-event mapping, unscanned
outputs, and exposure state.

`OFFLINE_EVENT_ORACLE_GREEDY` is evaluator-only and noncausal. It greedily
maximizes unseen full-scan-mapped pseudo-reference events per frozen Q90 path
cost. It is an achievable hidden-information comparator, not a proven
mathematical upper bound; its advantage is therefore a conservative witness
that headroom exists, not a bound on all possible headroom.

## Budget and metrics

Replay checkpoints are 5, 10, 20, 30, 40, 60, 80, and 100 percent of the
video-specific sequential full-scan Q90 estimated cost. All policies use the
same absolute checkpoint deadlines within a video.

Primary metric: normalized distinct-event exposure grid AUC relative to the
offset-0 exposure ceiling (70 + 193 = 263 events). Also report recall relative
to all 268 pseudo-reference events and the ceiling 263/268.

Secondary metrics: time to first event, maximum unobserved gap, covered
duration, distinct events per cost, candidate-event match redundancy, seek
count, mean transition distance, and unused budget.

The 32 existing controlled-warm physical runs are reused only after trace-hash
capture. Their selected-unit prefixes are re-evaluated with frozen
visible-subset replay to add distinct-event exposure; no GPU rerun is required.

## Falsifiable gates

- H1 implementation sanity: Largest-Gap must reduce maximum unobserved gap
  relative to Sequential at matched replay deadlines.
- H2 coverage value: at least one noncausal-free coverage policy must improve
  exposure AUC over Sequential. Results must be reported per video; two videos
  cannot establish cross-video generalization.
- H3 physical retention: the sign and fraction of replay coverage gain retained
  under actual controlled-warm wall-clock determine whether the next innovation
  targets event allocation or macro/path execution.
- Temporal analysis proceeds when the offline greedy comparator exceeds the
  best simple causal replay AUC by at least 0.02 on either video. This is a
  mechanism-discovery threshold, not a significance threshold.
- Refinement proceeds only if trigger-conditioned neighbor first-event gain is
  positive on both videos or has pooled risk ratio at least 1.25 without a
  negative per-video effect.
- Guarded marginal scheduling is prohibited unless a simple fixed refinement
  baseline improves over the strongest coverage baseline on both videos under
  the same cost semantics.

No method is promoted as a formal paper result from these two development
videos.
