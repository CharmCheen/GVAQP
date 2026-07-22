# Native ARC vs Native PSTR

## Conclusion

**INCONCLUSIVE.** This replay cannot support `PSTR_SUPERIOR` or `ARC_SUPERIOR`.
Only two independent source videos are represented, all target labels were open
before PSTR was proposed, and native PSTR required a newly specified minimal
materializer. Descriptive differences are therefore mechanism evidence, not a
strict winner claim.

## Systems compared

- `native_arc` runs ARC's native refinement loop with progressive sampling,
  label propagation, candidate-clip boundaries, stopping rule, and exposed
  native candidate confidence. ARC's native sequential Jensen-Shannon
  clustering is used at threshold 0.001 on the available two-class public-proxy
  posterior. Original ARC CDF features were unavailable, so this is an explicit
  adaptation rather than a literal reproduction of the paper datasets.
- `native_pstr` uses frozen PSTR-5:4 selection and
  `pstr_native_minimal_materializer`: every queried-positive unit becomes one
  exact unit-boundary event, with no merging or bridging. PSTR had no existing
  independent native clip materializer; the variant is not presented as
  `pstr_native`.
- `arc_shared_k3` rematerializes the exact native ARC query trace through
  terminal `k3_bridge_safe`.
- `pstr_shared_k3` rematerializes the exact PSTR trace through the same K3.

`native_arc` and `arc_shared_k3` have byte-identical selection traces for every
run. **K3 does not affect ARC query trace.** No proxy-order exact fill is used in
this experiment. Historical BSEC shared-K3 ARC controls did append proxy-ordered
units when ARC stopped short; that behavior is not used here because it would
confound the materializer ablation with extra queries. ARC may therefore use
fewer than B calls; PSTR uses exactly B.

Shared K3 deliberately discards ARC's native candidate-clip boundaries and
confidence; it can materialize only queried-positive anchors. This is especially
consequential on `realcartest_0_1570`: native ARC averages 0.6 calls, returns
seven candidate clips and 1468 seconds at every budget, while `arc_shared_k3`
has no queried-positive anchor and returns no event. Thus the shared comparison
is a selector/query-trace control, not an approximation of native ARC output.

## Frozen and development-derived choices

Budgets are `[5,10,20,50,80,100]`; ARC seeds are `[0,1,2,3,4]`.
ARC threshold 0.4, clustering threshold 0.001, confidence 0.9, unit-scale
`tau=1`, IoU confidence threshold 0.5, and all native refinement switches were
frozen in `manifest.json`. PSTR overhead 0.25 came from the recorded five-domain
leave-one-domain-out development replay. Every included domain was already open,
so the complete study is marked exploratory/post-hoc. No parameter was selected
from the newly generated metrics in this directory.

## Metric definitions

The evaluator performs overlap-any event matching with one-to-one Hungarian
assignment; cardinality is optimized before temporal IoU. Precision is matched
predictions divided by predictions. Recall is matched references divided by
references. F1 is their harmonic mean. `tiou_03` and `tiou_05` divide the number
of matched pairs meeting the threshold by the reference-event count. Selected
positive units are never treated as event recall.

The tables below are source-video macro averages: seeds are averaged within a
domain, the two realcartest domains are averaged within their source video, and
the two source videos then receive equal weight.

## Native full-system comparison

| B | left P/R/F1 | right P/R/F1 | F1 winner |
|---:|---:|---:|:---|
| 5 | 0.354/0.362/0.316 | 0.500/0.062/0.111 | native_arc |
| 10 | 0.361/0.362/0.321 | 0.500/0.087/0.149 | native_arc |
| 20 | 0.395/0.396/0.355 | 1.000/0.277/0.418 | native_pstr |
| 50 | 0.444/0.454/0.410 | 0.771/0.415/0.501 | native_pstr |
| 80 | 0.481/0.522/0.462 | 0.735/0.599/0.627 | native_pstr |
| 100 | 0.508/0.560/0.497 | 0.644/0.662/0.612 | native_pstr |

The F1-winner column is descriptive, not an overall ranking. At B=5, 10, 20,
and 50, native PSTR has higher precision but lower recall than native ARC, so
the systems are Pareto-incomparable. Native PSTR is higher on both precision
and recall at B=80 and 100. Across the full grid, PSTR has higher precision and
F1 AUC but lower recall AUC; this is a precision/recall tradeoff, not strict
PSTR superiority.

## Shared-K3 selector control

| B | left P/R/F1 | right P/R/F1 | F1 winner |
|---:|---:|---:|:---|
| 5 | 0.250/0.013/0.024 | 0.500/0.062/0.111 | pstr_shared_k3 |
| 10 | 0.350/0.024/0.044 | 0.500/0.087/0.149 | pstr_shared_k3 |
| 20 | 0.540/0.073/0.122 | 1.000/0.277/0.418 | pstr_shared_k3 |
| 50 | 0.727/0.184/0.268 | 0.806/0.415/0.515 | pstr_shared_k3 |
| 80 | 0.726/0.297/0.385 | 0.813/0.599/0.671 | pstr_shared_k3 |
| 100 | 0.730/0.361/0.442 | 0.887/0.662/0.728 | pstr_shared_k3 |

PSTR is descriptively no lower on both precision and recall at all six shared-K3
budgets. This does not establish selector superiority because the replay is
post-hoc, has two independent videos, and ARC's native stopping policy often
uses fewer oracle calls than PSTR under the same upper-bound budget.

## Normalized AUC on the identical budget grid

| Method | Precision AUC | Recall AUC | F1 AUC |
|:---|---:|---:|---:|
| native_arc | 0.441 | 0.461 | 0.412 |
| native_pstr | 0.768 | 0.425 | 0.490 |
| arc_shared_k3 | 0.645 | 0.192 | 0.262 |
| pstr_shared_k3 | 0.825 | 0.425 | 0.518 |

K3 minus native AUC effects for ARC are P=+0.204,
R=-0.270, F1=-0.150. For PSTR they are
P=+0.057, R=+0.000,
F1=+0.028. These quantify terminal materialization effects;
they do not imply causal generalization beyond the two videos.

## Statistical interpretation

Paired rows are saved for every domain/video/seed/budget. Bootstrap and
permutation inference first averages stochastic seeds, then averages domains
from the same source video, and resamples the source video. There are only two
independent source videos, so every budget is flagged
`statistical_power_insufficient`. Holm correction is applied across the six
budgets within each comparison and metric. The smallest Holm-adjusted p-value
for the native recall comparisons is 1.000; no significance claim is
made.

## Evidence, competing explanation, and revision trigger

The strongest supported conclusion is that native output logic materially
changes both systems' precision/recall profiles, so shared-K3 selector results
cannot answer the full-system question. A major competing explanation is
source-specific proxy/time regularity combined with post-hoc PSTR development.
The key uncertainty is prospective cross-video behavior with human references.
The next high-value action is the already frozen external protocol: at least five
independently sourced videos, proxy-only sealing before labels, and human
adjudication. This `INCONCLUSIVE` conclusion should be revised only if that
independent native, paired experiment satisfies the preregistered AUC and
precision-noninferiority rules.

## Verification

`verification.json` reports `PASS` for file completeness,
run counts, budget limits, duplicate queries, materializer separation,
evaluator hash, metric and summary recomputation from predictions, input hashes,
trace identity, and proxy-only PSTR seal replay.
