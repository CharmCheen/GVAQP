# RC-SEM validation handoff

Status: `STAGING_NOT_CONFIRMATORY`

Purpose: hand off the exact validation sequence for RC-SEM after the main
repository completes and releases the authenticated Model-Relative Oracle V3
full grid and frozen K3 reference.

This document is not authorization to modify the current full-grid seal. The
staged implementation remains isolated at `/root/charm/GVAQP_side_rcsem` until
the main run and its finalizer are complete.

## 1. Objective and primary claim

RC-SEM must answer one question:

> Under the same hard deadline and probable-event precision requirement, does
> risk-controlled speculative materialization plus state-dependent SCAN/VERIFY
> allocation return more true K3-relative events, or return them earlier, than
> the best fixed or two-stage policy?

The primary claim is not that every returned event was VERIFY-confirmed.
Probable events are legitimate returned results only when their event-level
probability lower bound passes a preregistered risk gate. `PROBABLE_EVENT` and
`VERIFIED_EVENT` remain different identities in every artifact and metric.

## 2. Required upstream artifacts

Do not begin confirmatory RC-SEM validation until all items below exist and
pass their frozen integrity checks:

```text
unit_labels.parquet
oracle_coverage_report.json
authenticated_full_grid_manifest.json
k3_model_relative_event_relation.parquet
k3_reference_manifest.json
k3_eventization_report.md
scan_candidates.parquet
candidate_features.parquet
candidate_to_reference_join.parquet
SCAN_EVENT_RECALL_CEILING.json
observed SCAN and VERIFY action-cost records
conservative action-cost upper bounds
```

Additional prerequisites:

- full grid is exactly 1,475/1,475 and the frozen finalizer passed;
- K3 configuration is frozen before any RC-SEM result is inspected;
- SCAN ceiling is high enough that controller choice can affect event recall;
- evaluator reference labels remain outside the runtime process and path view;
- zero retries, post-deadline commits and incomplete admitted actions remain
  enforceable in replay.

If the full grid, K3 reference, or SCAN ceiling fails, stop and use the existing
main-project decision mapping. RC-SEM cannot repair an invalid reference.

## 3. Integration boundary after seal release

The main repository already contains useful compatible components:

```text
src/garc_eval/accelerated_event_query/types.py
src/garc_eval/accelerated_event_query/state.py
src/garc_eval/accelerated_event_query/incremental_k3.py
src/garc_eval/scan_confirm_controller/smdp_safety_shield.py
src/garc_eval/scan_confirm_controller/smdp_dataset.py
```

Integration should occur only in a new reviewed commit after the formal
full-grid execution no longer depends on the sealed source tree.

Required changes:

1. adapt runtime K3 hypotheses into `rc_sem.EventHypothesis` records;
2. add an event-posterior model that predicts mean and uncertainty for final
   K3 event existence, rather than reusing maximum candidate score;
3. feed action-value predictions into `rc_sem.ActionOption`;
4. call `RCSEMAlgorithm.step()` using only causal runtime state;
5. stage action output and use `TwoPhaseCommitGuard` before public state update;
6. expose probable and verified events through distinct public fields;
7. keep evaluator matching and reference files in a separate process and path.

Do not replace evaluator K3 with runtime K3. Runtime event hypotheses and the
hidden evaluator reference must continue to use different entry points.

## 4. Preregistration and new seal

Before fitting on or evaluating full-grid-derived event targets, create:

```text
RC_SEM_VALIDATION_PREREGISTRATION.json
RC_SEM_EXECUTION_SEAL.json
RC_SEM_LABEL_HIDING_AUDIT.md
RC_SEM_DECISION_MAPPING.json
```

Bind at minimum:

```text
full-grid finalizer decision and artifact hashes
K3 reference hash and matching configuration
SCAN candidate and feature hashes
action-cost data and upper-bound hashes
event-posterior feature schema and model family
probable threshold
precision floor
uncertainty multiplier beta
false-positive penalty
Q-target definition
behavior-policy state generator
beam width and continuation search rule
fallback fixed/two-stage policy
deadline grid
random seeds
code commit and environment identity
```

The current reference config is:

```text
/root/charm/GVAQP_side_rcsem/configs/rc_sem_reference_v1.json
canonical config SHA-256:
fa35b9c2e49b9b744cc1c44f681eca990e286c4552bc9b2bd2fb470873c8883d
```

It is a staging default, not a confirmatory threshold authorization. Fit and
calibrate thresholds using training videos only, then freeze a new config hash
before the held-out fold is evaluated.

## 5. Event-posterior dataset

For every causally reachable runtime hypothesis `e_t`, perform evaluator-only
one-to-one matching against the frozen K3 reference:

\[
y(e_t)=1 \quad\text{iff}\quad e_t\text{ matches a final reference event}.
\]

Recommended artifact:

```text
RC_SEM_EVENT_POSTERIOR_DATASET.parquet
```

Each row should include:

```text
held-out fold ID
video ID (evaluator side only)
behavior policy and seed
episode and state hash
canonical event-lineage ID
runtime event ID
elapsed time and remaining budget
causal event features
posterior target
reference match ID (evaluator side only)
feature provenance hash
```

Never randomly split time points or hypotheses. All states from the same video
and event lineage stay in one fold. Repeated time states of one event do not
count as independent precision observations.

## 6. Leave-one-video-out calibration

Run exactly three held-out folds:

```text
train DALI + HANGZHOU; test WUHAN
train DALI + WUHAN; test HANGZHOU
train HANGZHOU + WUHAN; test DALI
```

For each fold:

1. fit the event-posterior model only on the two training videos;
2. calibrate probability and uncertainty only on training-video data;
3. choose the probable threshold only from training-video calibration;
4. freeze the fold model and threshold hash;
5. evaluate the untouched held-out video once;
6. preserve every probable false positive without relabeling.

Primary precision floor recommendation:

```text
primary: 0.80
sensitivity only: 0.70 and 0.90
```

Required diagnostics:

```text
Brier score
calibration curve and ECE
probable-event precision and recall
probable coverage
precision lower confidence bound
boundary uncertainty
false-positive taxonomy
```

Hard prediction Gate:

```text
probable-event precision LCB >= frozen precision floor
```

If the number of distinct probable events cannot support that lower bound,
return `INSUFFICIENT_EVIDENCE`; do not lower the precision floor.

## 7. Dynamic-headroom experiment

Generate naturally reachable states with:

```text
SCAN-only
VERIFY-when-available
75:25
50:50
25:75
alternating
two-stage scan-then-verify
myopic
random-safe
```

At every state where both actions are safe and legal:

```text
force SCAN-first   -> search best safe continuation
force VERIFY-first -> search best safe continuation
```

Score with hidden evaluator truth:

\[
U_t=TP_t-\lambda FP_t.
\]

In evaluator metrics, a probable event that truly matches the reference earns
the same recovered-event count as a verified match. A false probable event is
an FP. Verification status is reported separately and cannot double-count the
same canonical event.

Dynamic-headroom Gate:

```text
SCAN_BETTER states occur in at least two videos
VERIFY_BETTER states occur in at least two videos
safe dynamic oracle beats best fixed/two-stage baseline
leave-best-video-out gain is nonnegative
gain is not caused by precision loss or deadline violation
```

If the safe oracle fails, stop with `NO_GO_BINARY_ALLOCATION`; controller
training cannot create headroom that is absent from the action space.

## 8. Closed-loop comparison and ablations

Run identical deadline grids, initial states, cost records and evaluator
matching for:

| Method | Probable return | Dynamic allocation |
|---|---:|---:|
| Best fixed ratio | no | no |
| Best two-stage | no | limited |
| Myopic | no | yes |
| Verified-only RC-SEM | no | yes |
| Fixed plus probable materializer | yes | no |
| Full RC-SEM | yes | yes |
| Safe dynamic oracle | yes | oracle |

Required ablations:

```text
event posterior vs maximum candidate score
LCB threshold vs mean-probability threshold
uncertainty shield on/off
terminal speculative SCAN vs mandatory VERIFY reserve
event-value VERIFY target vs highest-score target
probable materialization only
dynamic scheduling only
full combined algorithm
```

The terminal speculative-SCAN ablation is essential. Under RC-SEM, SCAN may
be the final admitted action only when it can directly return a risk-admissible
probable event. If it cannot directly materialize, it must still reserve a
complete safe VERIFY opportunity.

## 9. Primary metrics

Use hidden reference matches for the primary outcome, not the controller's own
probability estimates:

\[
\operatorname{AnytimeTrueReturnedEventUtility}
=\frac{1}{D}\int_0^D(TP_t-\lambda FP_t)\,dt.
\]

Report:

```text
terminal distinct matched events
combined event recall and precision
probable-only recall and precision
verified-only recall and precision
AnytimeTrueReturnedEventUtility
AnytimeEventRecallAUC
time to first returned event
probable-to-verified latency
false-positive probable events
SCAN and VERIFY cumulative costs
switching timeline
K3 materialization timeline
incomplete admitted actions
post-deadline commits
```

Probable precision must pass independently. Verified events must not dilute a
poor probable-event precision result.

## 10. Final Gate and decision mapping

RC-SEM passes only if all conditions hold:

```text
all three leave-one-video-out folds preserve label hiding
probable precision LCB reaches the frozen floor
dynamic oracle headroom exists
Full RC-SEM beats best fixed/two-stage policy
Full RC-SEM beats probable-only and scheduling-only ablations
at least two videos improve
leave-best-video-out gain is nonnegative
zero safety, integrity and deadline violations
```

Map failures to the existing main-project decision space:

| Observation | Decision |
|---|---|
| All Gates pass | `GO_ACCELERATED_EVENT_QUERY` |
| SCAN ceiling or discovery failure | `REVISE_SCAN` |
| VERIFY target has low event-level value | `REVISE_VERIFY_TARGET` |
| K3 structure invalidates materialization | `REVISE_K3` |
| Event posterior, DeltaQ or calibration fails | `REVISE_STATE` |
| Admission bounds or commits fail | `REVISE_COST_SAFETY` |
| Safe oracle has no binary-action headroom | `NO_GO_BINARY_ALLOCATION` |
| Too few events or incomplete evidence | `INSUFFICIENT_EVIDENCE` |

## 11. Required final artifacts

```text
RC_SEM_VALIDATION_PREREGISTRATION.json
RC_SEM_EXECUTION_SEAL.json
RC_SEM_LABEL_HIDING_AUDIT.md
RC_SEM_EVENT_POSTERIOR_DATASET.parquet
RC_SEM_LOVO_CALIBRATION.json
RC_SEM_DYNAMIC_HEADROOM.json
RC_SEM_CLOSED_LOOP_RESULTS.parquet
RC_SEM_ABLATION_REPORT.md
RC_SEM_COST_SAFETY_AUDIT.json
RC_SEM_FINAL_DECISION.json
```

The final report must state that three videos support mechanism validation only
and do not establish broad deployment generalization.

## 12. Staging-package verification

Reference implementation:

```text
/root/charm/GVAQP_side_rcsem/src/rc_sem
```

Run:

```bash
cd /root/charm/GVAQP_side_rcsem
PYTHONPATH=src pytest -q
```

At the current sequential-study handoff, 39 tests pass. Verify the current package manifest before
integration:

```text
/root/charm/GVAQP_side_rcsem/RC_SEM_PACKAGE_MANIFEST.json
```

The latest cached closed-loop decision is `REVISE_STATE`.  Do not promote
`DYNAMIC_ADAPTIVE_K3_VALUE_V3` as universal: it was the valid development-
selected method but lost to the pre-existing fixed 1:1 candidate on the
primary held-out video.  Fixed 1:1 is now the required fallback, not a
retrospectively substituted winner.  A revised advantage model requires a new
independent held-out video.
