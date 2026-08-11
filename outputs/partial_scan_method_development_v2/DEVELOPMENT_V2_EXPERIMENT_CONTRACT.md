# PARTIAL_SCAN_METHOD_DEVELOPMENT_V2 Experiment Contract

```text
STATUS = MECHANISM_PILOT
PRIMARY_NEW_HYPOTHESIS = MACRO_ACTIVITY_CAN_BE_EXPLOITED_UNDER_BOUNDED_RECOVERABLE_COVERAGE_DEBT
V1_RESULTS = FROZEN_UNCHANGED
V1_M5_INTERPRETATION = INVALID_FOR_CAUSAL_METHOD_SELECTION_DUE_TO_UNSCANNED_ACTIVITY_LOOKAHEAD
FORMAL_METHOD_RANKING = BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION
```

## Scope

Only evaluator-side development replay is allowed. Macro-region scores may use
only observations from already scanned units. Pseudo-reference events are used
only for post-hoc metrics. No RL, Bandit, SMDP, CONFIRM, M1--M4, M6, or M9 is
run in V2.

## Fixed audit design

Regions are eight timeline units. The M5 falsification audit compares combined
shrunken activity to shuffled activity, time-index-only, no-shrinkage, each
activity component, and leave-best-region-out. The existing two videos are
development design inputs only; no independent validation set is available.

## M10 gate

M10 may be implemented only after the audit shows combined online activity is
greater than shuffled and time-index-only controls and is not wholly removed by
leave-best-region-out. It will compare fixed coverage debt of 0, 1, 2, and 4
median action costs against B0 (Largest-Gap), B1 (online M5), and B2 (M8).

At every checkpoint it must report exposure AUC, prefix exposure, maximum gap,
integrated distance, region concentration, and unused budget. Development
coverage tolerance is evaluated at `rho_G = 1.5` and `2.0` relative to
Largest-Gap. M11 is prohibited unless M10 passes these exploratory gates.

## Current gate result

```text
M5_FALSIFICATION_AUDIT = COMPLETE
M10_GATE = NOT_PASSED
M10_FIXED_COVERAGE_DEBT = NOT_IMPLEMENTED
M11_CONFIDENCE_ADAPTIVE_DEBT = PROHIBITED
BLOCKER = ONLY_TWO_DEVELOPMENT_VIDEOS_AND_NON_ROBUST_ONLINE_ACTIVITY_SIGNAL
```
