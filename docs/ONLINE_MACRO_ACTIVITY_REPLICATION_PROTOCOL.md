# Online Macro-Region Activity: Disposition and Frozen Replication Protocol

## Authority, scope, and evidence status

**Decision date:** 2026-07-24  
**Scope:** macro-region activity scheduling only. This document neither changes the existing PSVR routes nor authorizes a new scheduler.

This state record is based on the reported V1/V2 audit conclusion. The underlying M5 result tables and traces were not present in this checkout when it was written. The numeric values below are therefore `REPORTED_NOT_LOCALLY_RECOMPUTED`, not independently recomputed evidence. They may not support a paper claim, external report, or reproducibility claim until recovery succeeds. Recovery failure instead produces the permanent status `SOURCE_ARTIFACT_MISSING`.

## Established findings

| Statement | Status | Evidence / interpretation |
|---|---|---|
| V1 M5 is an online-method result | Invalid | Its activity statistic included observations from unscanned units, so its information set is not a subset of scanned history at decision time. |
| Offline activity-informed redistribution can be useful | Diagnostic only | V1 is retained as an `OFFLINE_FULL_INFORMATION_UPPER_BOUND_LIKE_RESULT`; it does not show online observations identify active regions. |
| An online macro-activity signal is established on two current videos | Not established | Reported V2 falsification gates fail: shuffled control (short), time-index control (short), and leave-best-region-out (long). |
| Shrinkage is a demonstrated causal contributor | Not established | The reported long-video difference is 20.60 AUC (701.82 versus 681.22), about 3%; this is insufficient on its own. |

The V2 observations admit at least three competing explanations: no predictive online signal exists under the current observation model; a video-specific absolute-time prior drives apparent performance; or one hotspot dominates the long-video result. Two videos do not discriminate these in favor of a stable macro-region mechanism.

## Binding disposition

```text
V1_M5_ONLINE_VALIDITY = INVALID_DUE_TO_FUTURE_OBSERVATION_LOOKAHEAD
V1_M5_RESULT = OFFLINE_FULL_INFORMATION_UPPER_BOUND_LIKE_RESULT
ONLINE_MACRO_ACTIVITY_SIGNAL = NOT_ESTABLISHED
ONLINE_ONLY_M5 = FAILED_PREREGISTERED_FALSIFICATION_GATE
M10_FIXED_COVERAGE_DEBT = BLOCKED
M11_ADAPTIVE_COVERAGE_DEBT = PROHIBITED
CURRENT_METHOD = M8_SAFE_ENGINEERING_BASELINE
FORMAL_METHOD_RANKING = BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION
NEXT_ACTION_1 = RECOVER_AND_HASH_V1_V2_SOURCE_ARTIFACTS
NEXT_ACTION_2 = MATERIALIZE_NEW_INDEPENDENT_COMPLETE_VIDEOS
NEXT_ACTION_3 = RUN_FROZEN_B0_A1_A4_CONFIRMATORY_MATRIX
```

No activity weight, macro-region length, shrinkage prior, coverage-debt parameter, learned predictor, RL/bandit/SMDP component, or time-index feature may be tuned or added under this branch. M10 may not be implemented merely as an exploratory check, and M11 may not be implemented. This is equivalently: `NO_NEW_ACTIVITY_FEATURES`, `NO_ACTIVITY_REWEIGHTING`, `NO_MACRO_REGION_RETUNING`, `NO_COVERAGE_DEBT`, `NO_M10`, `NO_M11`, `NO_RL_BANDIT_SMDP`, and `NO_FORMAL_METHOD_CLAIM`.

## Next stage: independent frozen replication

```text
NEXT_STAGE = ONLINE_ACTIVITY_REPLICATION_ON_INDEPENDENT_COMPLETE_VIDEOS
```

This confirms the frozen mechanism; it is not a tuning set. Existing two videos remain design/falsification evidence only. A first-new-video failure cannot change the frozen definition before the remaining selected videos are run.

### Independent evidence-recovery workstream

Evidence recovery is archival/recomputation work, not a new experiment. It may locate original policy action traces, budget-wise exposure curves, per-video/per-region metric tables, generation scripts, frozen configuration, commit identity, and environment identity. It may recompute only already reported values from recovered source artifacts. It must not modify a policy, parameter, seed rule, regionization, or input video; it must not run a new M5 variant.

The recovery output directory is fixed as:

```text
outputs/partial_scan_method_development_v2/evidence_recovery/
  artifact_manifest.json
  source_hashes.json
  recomputation_report.md
  metric_reconciliation.csv
  unresolved_artifacts.md
```

`artifact_manifest.json` identifies every recovered artifact, its source path, cryptographic hash, producing script/config/commit/environment where available, and the recovery status of every reported metric. `metric_reconciliation.csv` gives reported value, recomputed value, tolerance, and pass/fail. Any missing or non-recomputable source is listed in `unresolved_artifacts.md` and marked `SOURCE_ARTIFACT_MISSING`; absence is not grounds to rerun or reinterpret the historical experiment.

### Source selection and minimum scale

Before acquiring or viewing any pseudo-reference or method result, freeze video inclusion criteria, minimum duration, source/session-independence criterion, selection order, maximum attempted-video count, and a benchmark-quality failure replacement rule. Acquire complete, seekable videos without inspecting reference-event density or method outcomes. Freeze each video hash and require an independent session; prefer diversity of road type, traffic state, visual condition, and source. The minimum engineering unblocking set is two new videos, which yields only a `CONFIRMATORY_MECHANISM_PILOT`. The target for method-direction assessment is at least four new videos (six total), with a later independent test set still required for a formal generalization claim.

Every attempted video must receive an immutable selection record containing:

```text
selection_order
eligibility_status
exclusion_reason
replacement_status
reference_hidden_during_selection
method_results_unavailable_during_selection
```

Replacement is legal only for a predeclared `ELIGIBILITY_FAILURE`: corrupted video, incomplete timeline, inability to random-seek, substantial SCAN failure, inability to execute the reference protocol, or a full-scan exposure ceiling below the predeclared usability threshold. `UNFAVORABLE_RESEARCH_RESULT` is never an eligibility failure. In particular, low A1 performance, few events after valid inclusion, a stronger time-index arm, absent activity gain, or adverse region concentration cannot remove or replace a video.

For every source, materialize immutable benchmark assets through the existing pipeline:

```text
video manifest and source hash
complete timeline units and unit-local frozen SCAN outputs
unit determinism audit
full-context Oracle pseudo-reference and reference-independence audit
visible-subset candidate replay and candidate-event mapping
full-scan exposure ceiling
controlled-warm cost sample
```

If the frozen SCAN operator exposes only a small fraction of pseudo-reference events, stop interpreting scheduler quality: the candidate-generation ceiling is then the dominant limitation.

### Must be frozen before references or results are viewed

```text
microchunk length
macro-region length
online activity definition
shrinkage formula and minimum-region support
Largest-Gap coverage baseline, budget, controls, and metrics
action-budget / wall-clock prefixes
progression gates and all thresholds
```

### Confirmatory matrix

```text
B0 = Anytime Largest-Gap
A1 = Online Combined Activity
A2 = Shuffled Activity
A3 = Time-Index-Only
A4 = No-Shrinkage Activity
```

Report per-video paired comparisons, macro averages, low-budget prefixes, region-contribution concentration, and leave-best-region-out analyses. A uniform-prefix baseline may be added only if it is fully activity-free and frozen before execution; no further mechanism arms are authorized.

## Preregistered progression gates

All gates must pass before M10 becomes legal. With exactly two validation videos, every directional gate requiring a majority requires both videos to be nonnegative/positive as stated; one positive and one negative is a failure.

1. **Coverage-relative gain.** Let `Delta_v = AUC(activity, v) - AUC(Largest-Gap, v)`. The validation macro-average must be positive, most videos must have `Delta_v >= 0`, and a single video may not supply a dominant share of total positive gain.
2. **Activity specificity.** `AUC(combined) > AUC(shuffled)` in validation macro-average and in a majority of videos.
3. **Not an absolute-time surrogate.** `AUC(combined) > AUC(time-index)` in validation macro-average.
4. **Region robustness.** The leave-best-region-out gain must remain positive, or at minimum must not collapse materially. Freeze the operational concentration threshold before execution; recommended: `best-region positive contribution / total positive contribution < 0.5`.
5. **Shrinkage contribution.** `AUC(shrunk) > AUC(raw)` with consistent direction across multiple videos.
6. **Early-budget safety.** At 1, 2, 4, and 8 actions (or their predeclared wall-clock equivalents), activity may not be systematically worse than Largest-Gap on a majority of prefixes/videos.

## Legal branches after replication

| Result | Consequence |
|---|---|
| All gates pass | `ONLINE_MACRO_ACTIVITY = REPLICATED`; `M10 = ALLOWED_FOR_NEW_DEVELOPMENT_CYCLE`. With only two new videos, retain the weaker `CONFIRMATORY_MECHANISM_PILOT` label rather than a final method claim. M11 remains `STILL_PROHIBITED_UNTIL_M10_PASSES`. |
| Better than shuffled but not time-index | Set `ONLINE_ACTIVITY = NOT_IDENTIFIED`, `TEMPORAL_POSITION_PRIOR = POSSIBLE`; run `TEMPORAL_PRIOR_ANALYSIS`, not M10. |
| Leave-best-region-out fails | Treat as hotspot-localization evidence only; do not claim a general macro-region scheduling mechanism. |
| Gates remain absent | Set `ONLINE_MACRO_ACTIVITY = REJECTED_UNDER_CURRENT_OBSERVATION_MODEL`, `M10 = CLOSED`, `M11 = CLOSED`; retain M8/Largest-Gap and seek a separately preregistered policy-visible signal. |

## Research state

The strongest supported conclusion is that geometric coverage controls unknown temporal risk, whereas event-directed exploitation requires an independently validated online predictive signal. The decisive validity issue is V1 future-observation lookahead; the decisive empirical issue is V2's three failed falsification checks. The key uncertainty is whether the apparent null is specific to these two videos or to the current observation model. The next high-information action is acquisition and immutable materialization of independent complete videos, followed by the frozen matrix above. Any post-freeze adjustment, or a failed gate, rejects or revises the macro-activity route rather than motivating parameter search.
