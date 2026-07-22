# Research state

## Current objective

Determine whether a genuinely distinct event-valued long-video AQP mechanism can deliver event recall/F1 >=0.80 at <0.70 dense Qwen3-VL GPU cost.

## Established findings

- Forty-two frozen facts were independently reproduced from primitive artifacts; all prior BCM/DARE/BCEM/risk-limiting routes remain closed.
- Three candidates were scored. VERA was selected at 0.846; BOLT (batch-only risk) and WAVE (missing workload evidence) were rejected.
- The risk-discretized timeline DP passed exact small-instance tests and always admits dense execution.
- The 69,120-cell, 500-seed simulation justified only a bounded pilot: 1,620 robust-mean cells and 168 robust-p05 cells passed, but no non-perfect cell survived every correlated p05 placement.
- The physical run used 105 new calls (20 calibration, 70 enumeration, 15 fallback), recall `0.038462`, F1 `0.052632`, and GPU ratio `0.240987`.
- Final decision: `PHYSICAL_PILOT_NO_GO`.

## Active hypotheses

- H-OPERATOR: metadata-correct set-valued enumeration may retain the observed cost advantage while recovering missed short events. Untested after this freeze.
- H-TRANSFER: operator error/cost profiles may transfer sufficiently across videos for DP planning. Untested.

## Rejected hypotheses

- H-PILOT-AS-RUN: the exact frozen physical instantiation is sufficient for a positive top-tier claim. Rejected by `FAIL` gate and single-video scope.
- H-SIM-COMPLETE: the simulator captured the decisive physical error modes. Rejected by the processor metadata-resampling caveat.
- Prior search/ranking/materialization/pruning hypotheses remain rejected for the reasons in `evidence/CLOSED_ROUTE_LEDGER.md`.

## Important failure/lesson

Freeze audits must validate post-processor frames/timestamps, not merely decoded frame identities and message metadata. Byte-identical dense calibration establishes benchmark comparability but not correct temporal sampling.

## Unresolved uncertainty

Whether VERA's abstract relation-cover mechanism fails intrinsically or only this metadata-free physical implementation; one video cannot distinguish transfer or human-truth validity.

## Next highest-value action

Freeze a metadata-correct `EVENT_ENUMERATE` operator on disjoint held-out videos, verify post-processor frame indices before inference, and run the smallest preregistered operator-accuracy/cost calibration that can reject H-OPERATOR. Do not reopen proxy ranking, ANY pruning, or merge tuning.
