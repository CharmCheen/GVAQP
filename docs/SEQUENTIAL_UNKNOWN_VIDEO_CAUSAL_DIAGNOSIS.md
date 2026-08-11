# Sequential unknown-video causal diagnosis

Status: post-heldout diagnostic.  This document explains the observed result;
it must not be used to retroactively select a method on the primary video.

## Strongest supported conclusion

The primary-video gain came mainly from a favorable alignment between the
label-blind temporal-bisection SCAN order and the locations of early positive
units.  It did not demonstrate a transferable learned SCAN/VERIFY switching
surface.  The dynamic V3 policy inherited the same favorable scan order, but
its cross-video probability model was badly miscalibrated and its local K3
novelty rule later fragmented one long event and missed another event.

## 1. Proxy domain shift is the dominant scheduler bottleneck

The development derivatives contain 277 units with positive prevalence
`0.2744`; the primary video contains 347 units with prevalence `0.1124`.  The
balanced logistic model fitted on the development derivatives predicts a mean
primary probability of `0.4406`.

On the primary video, raw proxy discrimination is weak:

```text
ROC AUC:             0.5171
average precision:   0.1277
positive prevalence: 0.1124
```

The ten highest proxy scores are all negative.  The top 20 contain three
positives; the top 96 contain 13 positives.  Consequently current two-stage
scheduling completes all 35 cheap SCAN cells and then spends ten VERIFY calls
on false candidates before its first event, at total cost `14.5`.

The V3 score is called a posterior in code, but `class_weight="balanced"`
probabilities are not calibrated probabilities without a separate calibration
step.  Domain prevalence shift makes using them directly as action utilities
especially unsafe.

## 2. Scan-order ablation separates interleaving from coverage

An exact post-heldout ablation retained fixed SCAN1:VERIFY1 and changed only
the label-blind cell order:

| Order | Mean Anytime Event Recall AUC | First event at budget 100 |
| --- | ---: | ---: |
| chronological fixed 1:1 | 0.0793 | 12.1 |
| temporal-bisection fixed 1:1 | 0.1332 | 1.1 |
| current two-stage | 0.0812 | 14.5 |

Chronological interleaving alone is therefore approximately equal to current
two-stage.  The large uplift is attributable to broad temporal coverage, not
to the 1:1 action ratio by itself.

The bisection order starts with cells `17, 8, 26, 3, 12, 21, ...`.  Cells 17
and 8 each happen to have a positive as their highest-proxy unit, so the first
two VERIFY opportunities are unusually productive.  Across all 35 cells,
only six cell maxima are positive (`17.1%`).

A 10,000-order label-blind random diagnostic at budget 20 placed the observed
bisection order at approximately the `98.08` percentile of an approximate K3
group-recall AUC distribution.  It reached the earliest possible first-event
cost, `1.1`; the random median was `4.4`.  This supports a favorable-order
explanation.  The random diagnostic uses evaluator-only labels after the
experiment and approximate group recall, so it is explanatory rather than a
new policy result.

## 3. The learned additions do not contribute stable independent gain

Primary means across the six budgets are:

| Method | Anytime Recall AUC | Terminal recall | Precision |
| --- | ---: | ---: | ---: |
| dynamic proxy V1 | 0.1224 | 0.2051 | 1.0000 |
| dynamic K3 V2 | 0.1251 | 0.2115 | 0.9848 |
| adaptive K3 V3 | 0.1223 | 0.2115 | 0.9848 |
| fixed 1:1 | 0.1332 | 0.2115 | 1.0000 |

V3 exceeded V2 by only `0.000094` development Anytime Recall AUC, but V2
exceeded V3 by `0.002815` on the primary video.  Thus the adaptive term was
selected on a near tie and did not transfer.

The online update shifts every candidate's log odds by the same amount.  It
cannot repair slope error, nonlinear proxy failure, temporal domain shift, or
candidate-specific uncertainty.  It also treats actively selected VERIFY
labels as if they were a representative prevalence sample.  They are not:
high-score candidates are deliberately oversampled, and the first lucky
positive raises the estimated prevalence, creating selection-feedback bias.

The scan-value calculation uses the same training-derived cell-maximum
distribution for every unseen cell.  It does not condition on region content
or which cell remains.  At budget 10, V3 uses 15 SCAN and eight VERIFY actions,
where fixed 1:1 uses nine of each.  Both recover three events, so the extra
exploration has no demonstrated marginal value.

## 4. Local K3 novelty creates a fragmentation failure

At budget 100, raw-proxy V1, fixed 1:1, and current two-stage all verify the
same 13 positive units and return 11 matched events.  V2/V3 verify only 11
positive units and return 11 predicted events, of which ten match references.

V2/V3 drop positive units `172`, `217`, and `246`, and add unit `177`.
Units 171 through 179 belong to the same long reference event.  Because the
hidden bridge units 172--176 are not verified, K3 materializes unit 171 and
unit 177 as two fragments.  One-to-one evaluation matches one fragment and
marks the other as an unmatched prediction.  The policy also loses the
distinct event anchored by unit 217.

This falsifies the assumption that distance from currently revealed positive
neighbors is a reliable estimate of new-event novelty.  Hidden positive spans
make local novelty partially unidentifiable.

## 5. Why ARC is worse

The shared-runtime ARC comparator waits for a complete proxy scan and then
uses proxy-cluster sampling.  With proxy ROC AUC near random, those clusters
are weakly aligned with the semantic query.  Across five seeds at budget 100,
first-event cost ranges from `11.5` to `52.5`; recall ranges from `0.2308` to
`0.3077`.  Its mean first-event cost is `25.9`.

This result applies to `ARC_TWO_STAGE_COMMON`, not to a completed historical
physical ARC execution.  It indicates that a sophisticated selector cannot
recover information that its proxy representation does not contain.

## Interpretation and next discriminating action

Observed evidence supports:

1. global temporal diversification can greatly reduce time to first event;
2. the present primary result contains substantial favorable scan-order luck;
3. current probability calibration and K3 novelty state are not transferable;
4. the proxy/query alignment, rather than controller model capacity, is the
   dominant bottleneck.

The main competing explanation is that temporal bisection is systematically
good for driving-event queries because events are dispersed across long
videos.  One primary video cannot distinguish this from luck.

The next high-information experiment is therefore not a larger controller.
Freeze temporal bisection, chronological, stratified-random, and content-aware
label-blind scan orders; combine each with fixed 1:1; then evaluate them on
multiple new query-identical videos.  Only after scan-order robustness is
established should an advantage model override fixed 1:1.  Reject a universal
dynamic-selector claim if its lower-confidence gain over the best frozen
label-blind order is nonpositive on a new held-out video.
