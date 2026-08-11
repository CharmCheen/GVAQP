# Binary SMDP Value Validation Contract V1

Status: `FROZEN_BEFORE_ORACLE_DATA_GENERATION`  
Base: `dspro@5047241b0561b911b9a519b18e8e7591c0074e70`  
Branch: `research/binary-smdp-value-v1`

## Research question and scope

This mechanism study asks whether, from the same causal public observation and
remaining hard wall-clock budget, forcing `SCAN` or `VERIFY_TOP1` first changes
the best attainable terminal distinct-event count and, secondarily, discovery
time.  It does not learn a scan region or candidate target.  `STOP` is a
legality/termination result, not a learned action.  The frozen largest-gap scan
order, proxy family, capacity-10 score Frontier, top-score verification target,
event materialization and deduplication semantics are unchanged.

In code and historical traces, `VERIFY_TOP1` is represented by the legacy enum
value `CONFIRM`; reports and dataset labels use `VERIFY`.

## State and information boundary

The SMDP state is `s_t=(o_t,b_t)`, where `b_t` is the remaining wall-clock
budget and `o_t` contains only values observable before action admission.
`PUBLIC_V0` is the parent `PublicState`. `PUBLIC_V1` may add total/remaining
budget, causal cost summaries and upper bounds, remaining service slots,
coverage/gap, padded top-10 Frontier scores and ages, score distribution and
replacement margin, recent causal scan/verify yields, top-candidate position,
and distance to an already confirmed event. Missing entries are padded and
masked. Candidate labels, reference events, future costs, future candidates,
future action outcomes, oracle returns, video/group identity, and evaluator
state hashes are forbidden controller features.

Realized action duration is evaluator transition information. A deployable
cost estimate or admission upper bound must be frozen from prior/calibration
observations; it may not be initialized from the evaluated task's unseen future
durations. Replay using a workload-scoped empirical maximum is identified as
trace-support safety, not a physical WCET guarantee.

## Actions, transition, legality and deadline

An admitted non-preemptive action must finish before the deadline. After an
action of realized duration `tau_t`, `b_{t+1}=b_t-tau_t`. `VERIFY_TOP1` is legal
only for a nonempty Frontier and when its conservative complete-path upper
bound fits. `SCAN` is productive-legal only when the scan upper bound plus one
verify upper bound fits; this reserves a verification opportunity after scan.
If only one action is legal it is selected. If neither is legal the result is
`STOP`. A transition whose realized completion exceeds the deadline commits no
event and is a safety failure. Formal gates require zero overruns, zero
post-deadline commits and zero incomplete admitted actions.

## Return and lexicographic objective

`Q*_event(s,a)` is the maximum terminal number of unique/distinct confirmed
events attainable after forcing legal first action `a` and then using the best
binary continuation within the remaining budget. `Q*_anytime(s,a)` is the
corresponding normalized integral `B^-1 integral_0^B N(t)dt`. The ordering is:

1. larger terminal distinct-event count;
2. if tied, larger AnytimeAUC;
3. if both differences are within frozen tolerances, `EFFECTIVELY_TIED` and
   fall back to R4.

Candidate count is diagnostic only and never reward. Values of different units
are not divided by each other; utility/second is a myopic diagnostic, not Q.
The AnytimeAUC stability tolerance is `1e-6` for deterministic replay.

## Oracle and label stability

Each both-legal state is deep-copied twice. The first copy is forced to SCAN and
the second to VERIFY; each then receives a lexicographic binary continuation
search. Evaluator state hashes cover budget/elapsed time, scan cursor and
coverage, Frontier contents/discarded/queried sets, verified outcomes,
confirmed events, candidate bindings/creation times, causal cost-estimator
history, and the event-discovery ledger. Hash deduplication and memoization are
allowed.

Beam widths are `128, 512, 2048`. A result is exact only if no live state was
pruned. A label is stable only if all widths agree on both terminal returns and
the sign/class of the conditioned action difference, and AnytimeAUC differs by
at most `1e-6`. Otherwise it is approximate and unstable. Approximate results
are never described as exact upper bounds.

## Data, behavior coverage and splits

States are deduplicated by evaluator hash and collected from independently
reset SCAN-first, VERIFY-first, 75:25, 50:50, R4 25:75, alternating, Frontier
rule, random legal (seeds `0,1,2`), and any legally runnable current myopic or
common-utility controllers. Frozen replay groups are `V0_Q1`, `V0_Q2`,
`V1_Q1`, `V1_Q2`; budgets remain `30,60,120,240` seconds. The independent split
unit is video or video-query group, never states randomly split within a video.
With only two independent videos all predictive results are a mechanism pilot,
not a cross-video generalization result.

Replay aggregation is limited to Round 0 plus at most two training-only policy
rounds. Held-out/sealed video adaptation is forbidden. Seeds for model fitting
are `0,1,2`; stochastic bootstrap seed is `20260729`.

## Baselines and gates

Baselines are R4, the strongest frozen fixed policy, current myopic/common
utility when legal, and the conditioned binary oracle.

The oracle headroom gate requires stable positive terminal-event headroom or,
for terminal ties, positive AnytimeAUC over R4; both SCAN-better and
VERIFY-better informative states; benefit from more than one video; positive
leave-best-video-out; no systematic low-budget loss; and zero safety failures.
It also audits whether headroom is merely a top-candidate pathology. Failure is
`NO_GO_BINARY_SMDP`; insufficient independent support or unstable beam labels
is `INSUFFICIENT_EVIDENCE`. Either stops the learned-model mainline.

If headroom passes, static gates compare `PUBLIC_V0`, `PUBLIC_V1`, and a strictly
evaluator-only upper bound. Metrics include advantage MAE/RMSE/Spearman,
informative balanced accuracy, high-confidence deviation accuracy, Brier/
calibration, per-video and leave-one-video-out results, and tie behavior. The
static gate requires signal in multiple groups, improvement over constant/R4,
and no leakage. Evaluator-only strength with weak PUBLIC_V1 triggers
`REVISE_STATE_AND_RETEST`.

The closed-loop gate requires the shielded controller to improve terminal
events or, under terminal ties, AnytimeAUC over R4 across multiple groups,
including nonnegative low-budget and leave-best-video-out results, while
retaining zero deadline violations. Required ablations remove Anytime,
uncertainty shielding, PUBLIC_V1 Frontier features, recent-yield features,
duplicate-risk features, and compare myopic utility/second and R4.

## Models and conservative controller

Models are evaluated in order: constant/R4, L2 linear/logistic models, shallow
LightGBM when installed, a 64x64 MLP, and a small seeded MLP ensemble. They
predict event advantage, Anytime advantage conditional on event ties, and
uncertainty. A model deviates from R4 only under sufficient support and a
confidence-adjusted margin; missing/OOD/uncertain states fall back to R4. The
safety shield is evaluated independently and always has final authority.

## Hangzhou and VLM roles

`data/杭州.mp4` is an unmodified 93:20.57, 852x480, 30-FPS H.264/AAC physical
resource. It uses the already frozen queries, prompt, proxy, candidate,
Frontier, verification and deduplication semantics. It is for physical cost,
throughput, action behavior, relative policy comparisons, and teacher-derived
proxy evaluation; it supplies no human ground truth.

The local runtime candidate is
`models/Qwen3-VL-8B-Instruct`; the offline teacher/auditor candidate is
`models/Qwen3-VL-32B-Instruct-FP8`. Model type and loadability must be measured,
not inferred from names. The 32B model is not a third online action. Prompts and
decoding are frozen before comparison; outputs are cached, parse failures are
retained, and 8B/32B disagreement is verifier uncertainty. Reports separate
trace-grounded, model-teacher-derived and physical-runtime evidence.

The inherited `30,60,120,240` replay grid remains frozen. A Hangzhou physical
grid is frozen after a pre-policy cost pilot to approximately `3,6,12,24`
8B-verify-equivalent actions. Formal comparison uses identical candidates,
cache, verifier, budgets and seeds for R4, the shielded controller and strongest
fixed policy.

## Stop conditions and final decision

No complex learner is trained to conceal absent/one-action/single-video oracle
headroom, unstable labels, future leakage, candidate-only gains, closed-loop
failure or deadline violations. Insufficient videos, sparse informative states,
unstable search, high teacher disagreement, absent Hangzhou events, or public
state aliasing produce `INSUFFICIENT_EVIDENCE` or
`REVISE_STATE_AND_RETEST` as appropriate.

The final decision is exactly one of `GO_BINARY_SMDP`,
`REVISE_STATE_AND_RETEST`, `INSUFFICIENT_EVIDENCE`, or
`NO_GO_BINARY_SMDP`. Structured `CONFIRM(candidate)` then `SCAN(region)` is only
a future design if all binary gates pass.
