# Failure Causal Decomposition

## Observed evidence

- F1 **generic action enumeration failure: rejected; semantic enumeration failure: supported.** H0 reconstructs eligible `PROBE_STRUCTURE` candidates at 55 steps and owner-follow-up `AUDIT_UNCOVERED` candidates at 55 steps. However, it has no genuine exploration-cell action because 86 uncovered/low chunks were initialized as hypotheses.
- F2 **score-scale failure: not demonstrated.** Reconstructed ranges overlap: core `[0.001164, 0.003419]`, owner-follow-up `[0.000005, 0.001526]`, and structure `0.001855`. At every co-eligible step the maximum virgin-core score is higher, without evidence of a unit/range mismatch. HS is therefore not justified.
- F3 **missing saturation is an observed state-semantics defect, but a performance cause is not demonstrated.** H0 leaves remaining owner units live after positive confirmation. However, H2 has identical traces, metrics, and AUC to H1 with zero absorption triggers, so saturation has no independent value in this operating trace.
- F4 **fragmentation/overpopulation: strongly supported.** Source counts are `{'uncovered_window': 86, 'high_proxy_island': 55}`; fragmentation is `1.230769` and false burden `0.794326` under evaluator-only mapping.
- F5 **outcome-belief failure: plausible but not isolated.** 90/100 selected H0 queries are negative, many false hypotheses retain unqueried cores, and selected-score/realized-F1 Spearman correlation is only 0.0597. These observations implicate the combined belief/surrogate ranking, not the outcome model alone.

## Derived causal conclusion

The literal “141 local-peak fragments” story is contradicted by source: H0 contains no local-peak construction. The demonstrated causal contribution is semantic source representation: 55 high-proxy islands plus 86 low/uncovered chunks all receive event-existence mass, while H1's source separation improves AUC by `0.020720`. Genuine exploration is represented as fake event hypotheses in H0; structure and owner-follow-up actions are reachable but always lose to the still-unexhausted virgin-core pool. Missing saturation is real in code but its H2 ablation contributes zero here.

## Competing explanation

Poor outcome calibration remains plausible and may continue to limit repaired variants even after semantics are corrected. A repair that reduces state size but fails to improve AUC would not falsify calibration failure.
