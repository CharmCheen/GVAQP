# Current implementation audit

Audit date: 2026-07-29 UTC  
Observed base: `dspro@5047241b0561b911b9a519b18e8e7591c0074e70`  
Working branch: `research/binary-smdp-value-v1`  
Initial dirty state: only pre-existing untracked safety-pilot/DADA paths; none
was modified or staged by this study.

## Strongest supported reconstruction

The current mechanism is a deterministic replay over complete measured SCAN
and physical-Qwen CONFIRM traces for two videos (`V0,V1`), two queries and four
budgets. SCAN follows the frozen largest-gap unit order. A capacity-10 Frontier
keeps the highest online proxy scores, permanently discards overflow, and
CONFIRM terminalizes the current highest-score unit. Confirmed utility is the
number of newly mapped distinct reference events, not candidate count.

The public V0 state contains remaining/unused budget, coverage and maximum gap,
scan count/time, Frontier size and score summaries/quantiles, oldest/newest age,
ever-admitted candidate count, confirmed distinct-event count, recent scan
arrival yield and zero streak, recent confirm positive/new-event rates and zero
streak, causal-estimator outputs for action costs, and completed-action count.
It does not expose unit/video identity or explicit future labels.

SCAN realized cost is the sum of seek, decode, detector, CPU tracking, rule
scoring and evidence serialization plus 1 ms. CONFIRM realized cost is measured
physical VLM query-to-snapshot duration, with historical per-unit generation
time plus median post-processing fallback where necessary. Admission in the
parent environment uses a causal estimator's Q90; the common-utility safe replay
replaces it with the workload's observed maximum plus 0.25 s.

Asset recheck after attempting a clean environment construction found an
important qualification: the V1 per-unit cost set is complete (567/567), but
the untracked V0 raw JSONL named by `runner.py` is absent from Git and from the
server. Only a few V0 costs survive in complete combined traces. The repaired
loader therefore marks missing V0 durations as `IMPUTED_TASK_MEDIAN_MISSING_V0_RAW`
to keep diagnostic replay executable. Results depending on those durations are
cost-sensitivity evidence, not complete measured-trace evidence, and cannot by
themselves establish cross-video headroom.

## Oracle and counterfactual support

`TraceReplayEnvironment` is deepcopy-able in current tests and inspection: its
mutable sets, Frontier, estimators and ledger are instance-owned. Existing
counterfactual code already deep-copies before one-step probes, so it is a
viable substrate. This must still be tested for mutation isolation across all
fields in the new implementation.

The existing `multi_step_trace_oracle()` is not reusable as the requested
labeler without revision. It returns one best trajectory only from the supplied
initial state, not both forced first-action returns at every state. Its beam
ranking is terminal event count, then low elapsed and Frontier size; it omits
AnytimeAUC. Although config declares width 2048, the historical execution
script passes `min(16,width)`, so all nontrivial historical multi-step results
were width-16 approximations. Search metadata correctly marks pruning as
inexact.

## Why common utility is not SMDP value

Common utility corrected the old dimensional error by valuing both actions in
expected new distinct events. It estimates a SCAN's one-step change in
serviceable Frontier value and a top candidate's conversion probability, then
compares utility/second. It neither forces and evaluates both first actions nor
optimizes a full continuation policy, state-dependent future duplicate risk,
terminal event count, or AnytimeAUC. Historical evidence found only 21
informative R4 states in two groups and worse CONFIRM Brier than a constant
rate, so its failed static gate is evidence against that estimator, not yet
against a correctly defined long-horizon SMDP.

## Interface/configuration risks

Observed issues are:

- terminology is `CONFIRM` in code but `VERIFY_TOP1` in the new research
  question; an explicit alias is required, not a new third action;
- parent Q90 admission caused 35 recorded overruns; post-deadline utility was
  excluded, but hard-deadline safety was not established;
- initial parent cost estimates use the evaluated task's complete per-unit cost
  distribution. This is acceptable as evaluator transition support but is
  future-task information if exposed as a deployable controller estimate;
- common-utility safe bounds use the evaluated workload's observed maximum,
  giving trace-support safety by construction rather than future physical WCET;
- historical `offline_beam_width: 2048` was not effective because the runner
  capped it at 16;
- cached visible-candidate scores are keyed by task and scan cursor. This is
  valid only because frozen largest-gap coverage is a deterministic prefix; it
  would be wrong after learning regions, which is out of scope;
- the summary reports `deadline_rejections: 0` rather than counting rejected
  steps, and an actual cost can exceed the admitted estimate; new safety audits
  must inspect the ledger/result directly;
- `use_remaining_budget_value=False` changes only a reason string in the old
  myopic controller and does not alter its computation, so that historical
  ablation configuration was not behaviorally effective.

No evidence was found that reference labels enter `public_state()`. Labels,
event mappings and complete costs do exist inside the evaluator environment and
must remain inaccessible to learned feature extraction.

## Hangzhou and local models

The task text names `model/`, but the observed repository path is `models/`.
The complete local candidates are:

- `models/Qwen3-VL-8B-Instruct` (about 17 GB), architecture
  `Qwen3VLForConditionalGeneration`;
- `models/Qwen3-VL-32B-Instruct-FP8` (about 34 GB), the same architecture with
  FP8 quantization metadata.

Installed Transformers 5.9.0 and Torch 2.10.0+cu129 expose the model class used
by existing project inference code. vLLM and `qwen-vl-utils` are not installed
in the active Python environment, so the existing physical-oracle code cannot
yet run unchanged; actual load, memory, latency and GPU count remain unverified.
The evidence supports testing 8B as the online verifier and 32B-FP8 as an
offline teacher/auditor, not treating either output as human ground truth.

`data/杭州.mp4` passes ffprobe: duration 5600.57 s, 852x480, 30 FPS, H.264 High,
AAC stereo. It is not currently one of the V0/V1 trace-replay tasks and cannot
enter the old pipeline merely by filename. It requires frozen-query unit/index
and proxy/candidate materialization followed by cached physical VLM outcomes;
the original video must remain unchanged. Existing PSVR physical-oracle and
proxy scripts are the integration path, subject to a small fixed pilot before
formal policy comparison.

## Evidence status and next discriminating action

Established: the replay substrate and event mapping can support binary
counterfactuals; R4 is the strongest frozen fixed baseline; old myopic and
common-utility methods failed; historical multi-step results indicate possible
but unverified headroom.

Unresolved: whether forced-first-action values are stable at widths
128/512/2048, whether both action signs occur across videos, and whether the
headroom survives conservative deadline admission. The next highest-value
action is therefore a tested conditioned oracle and a small beam-stability
pilot before any learner work.
