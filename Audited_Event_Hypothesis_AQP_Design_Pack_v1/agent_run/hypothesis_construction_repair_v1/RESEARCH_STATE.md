# Research State

## Objective
Test whether corrected hypothesis/anchor/exploration/materialization/structure semantics recover BCM on the frozen strict benchmark.

## Established findings
H0 exact reproduction passed. The 141 state consists of 55 high islands and 86 uncovered chunks. Source-separated H1 is the only repair with independent value: AUC `0.314990` versus H0 `0.294270`. H2 saturation, H3 dynamic creation, and H4 triggered structure add zero on the formal trace. Decision: `HYPOTHESIS_REPAIR_WEAK_GO`.

## Rejected hypotheses
The failed builder did not create 141 local-peak hypotheses. Generic enumeration and score-scale failure were not demonstrated. Missing saturation is not a demonstrated performance cause in this trace.

## Active uncertainty
Single-video outcome calibration and cross-video stability remain unresolved; no repaired variant improves B<=50 or activates formal exploration/structure selection.

## Next highest-value action
Freeze the winning semantic repair and test it unchanged on multiple held-out videos with outcome calibration diagnostics.
