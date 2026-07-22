# VERA headroom and falsification report

## Pre-execution decision

`PHYSICAL_PILOT_JUSTIFIED` for a bounded mechanism test, not for a paper claim.

The evaluator-backed grid contains 69,120 aggregate cells with 500 seeds each.
It varies event prevalence, core/window length, overlap margin, enumeration
sensitivity, localization success, false-event rate, per-window cost scaling
and independent/boundary-correlated/event-cluster-correlated/adversarial-count
errors. There are 1,620 strict-reference configurations passing the mean
quality/cost gate across all four placements and 168 passing the more severe
5th-percentile gate.

## Registered realistic cell

The predeclared pilot shape uses a 50-second ownership core, 5-second context
on each side, 70 windows, sensitivity 0.95, localization success 0.95, 0.05
false events/window and cost scale 3.0 relative to a 10-second unit call.
Its dense-cost ratio is `210/347 = 0.605187` and 25/26 reference events are
fully contained in their owner input window.

| Error placement | mean recall | p05 recall | mean F1 | p05 F1 | mean gate | p05 gate |
|---|---:|---:|---:|---:|---|---|
| independent | 0.9074 | 0.8077 | 0.8861 | 0.8145 | pass | pass |
| boundary-correlated | 0.9056 | 0.6538 | 0.8830 | 0.7332 | pass | fail |
| event-cluster-correlated | 0.9166 | 0.5769 | 0.8842 | 0.6808 | pass | fail |
| adversarial count | 0.8846 | 0.8846 | 0.8765 | 0.8214 | pass | pass |

The adverse lower tail is decisive negative evidence: **no non-perfect
sensitivity/localization configuration passes the p05 gate across every
correlated placement model**. Therefore the simulation supports only a direct
physical mechanism pilot. It does not support an accuracy guarantee or
multi-video deployment.

## Cost ceiling and failure boundary

For the registered 70-window plan, a perfect enumerator passes at cost scales
1, 2 and 3 (ratios 0.2017, 0.4035 and 0.6052) and fails at scale 4
(ratio 0.8069). The analytic break-even is mean window cost `<3.47` dense unit
calls. This must be measured; logical-call compression alone is insufficient.

Across the strict grid, dense fallback is chosen in 49.06% of registered
error/cost regimes. Synthetic rare-event prevalence 0.02 has a 61.88% fallback
rate, showing that sparse event sets make the F1 impact of even a few false
events severe.

## Interpretation

Observed headroom is nontrivial because it survives non-perfect mean operator
accuracy and an adversarial miss-count allocation. The strongest competing
explanation is that the cost/error pair is unrealistic: 60 seconds at 2 fps may
cost more than 3.47 unit calls or omit 0.7-second events under correlated
context failure. The next action is exactly the frozen full-timeline pilot; the
observation that rejects VERA is recall/F1 below 0.80 or measured cost ratio
not strictly below 0.70.

