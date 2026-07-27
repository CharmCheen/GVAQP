# SCAN Innovation Research Report

## Final answer

The defensible final state is `SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST`.
There is substantial *offline* SCAN scheduling headroom, but this study did
not establish a causal, cost-effective YOLO-guided signal that can exploit it
on both videos. Therefore no region-value scheduler, batching rule, novelty
exit, or new physical candidate was admitted.

This is not a conclusion that SCAN cannot be optimized. It is the narrower
conclusion that the tested policy-visible signals do not identify the
headroom reliably enough to justify an adaptive scheduler.

## Decisive evidence

| Evidence | Short video | Long video | Meaning |
|---|---:|---:|---|
| Best causal full-horizon AUC | 0.530 (ANYTIME_LARGEST_GAP) | 0.528 (MACRO_REGION_LARGEST_GAP) | simple coverage order matters |
| Offline oracle AUC | 0.904 | 0.864 | large noncausal upper headroom remains |
| Q1-L Recall@20 / AUC | 0.329 / 0.594 | 0.321 / 0.613 | stable weak detection signal |
| Q2 high-rate YOLO Recall@20 / AUC | 0.329 / 0.594 | 0.316 / 0.609 | more detections do not resolve ambiguity |
| Q3 directional motion Recall@20 / AUC | 0.329 / 0.594 | 0.326 / 0.614 | small long-only effect, not robust |
| Q1/Q2/Q3 cost ratio | 0.033 / 0.053 / 0.071 | same joint accounting | all legal, so rejection is not caused by cost-cap violation |

The frozen static Gate required Recall@20 >= 0.40 on both videos, strict
improvement over Q1-L on both, nonnegative primary net yield on both, and a
common budget with positive gain on both. Q2 and Q3 failed these conditions.
At 20% total cost Q2 changed event count by -3/+7 (short/long); Q3 by -5/+1.
This is video-unstable and preview cost removes the apparent low-budget gain.

## What the experiments imply

Observed: coverage winners vary with video and horizon. At physical 60 seconds
the tested winners are Sequential on the short video and Uniform-prefix on the
long video. At the full replay horizon they are Anytime Largest-Gap and Macro
Largest-Gap. Thus there is no evidence for one universal ordering winner.

Derived: detection sampling density is not the dominant bottleneck. Q2 used
ten-times the Q1 sampling rate on the uncertainty-selected subset yet did not
improve short-video ranking and degraded the long-video primary recall.

Working hypothesis rejected: directional local motion alone is enough to turn
Q1 into a cross-video value estimator. Q3 improves only the long video by
about 0.005 Recall@20 and leaves the short video unchanged.

Main competing explanation: the pseudo-reference event value depends on
longer temporal/interaction semantics not captured by sparse detection or
short-window flow. Another possibility is that two design videos are too few
to identify a stable mapping. Neither explanation licenses a scheduler now.

## Innovation status and scheduler design

The intended innovation was an uncertainty-escalated residual-value scheduler:
global low-rate YOLO, selective higher-fidelity sensing near the allocation
boundary, explicit competition between predicted new-event value and coverage
opportunity cost, and a recoverable one-step deviation. This would be a real
mechanistic contribution, not merely “YOLO + Largest-Gap”.

It was not implemented as a selected method because its prerequisite value
signal failed. If a future independent asset set passes the static Gate, the
next legal scheduler is:

1. produce `u_C`, the best global coverage action;
2. produce `u_R`, the best region action by `(p_new + lambda*uncertainty)/cost`;
3. execute `u_R` only if it beats the nonzero coverage opportunity utility by
   a frozen margin, preserves the maximum-gap bound, and leaves enough budget
   for coverage-only recovery;
4. otherwise execute `u_C`;
5. only after replay acceptance, test 1/2/4 contiguous units and novelty exits
   of 1/2 no-new-cluster actions.

Rejection trigger: any future signal that fails >=0.40 Recall@20 on either
complete held-out video, loses after actual preview cost, or improves only one
video must again fall back to coverage.
