# MF-PSVR Stage-A support report

## Strongest supported conclusion

The frozen Stage-A decision is `STOP_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE`. All 96 one-way physical attempts have exact durable raw and parsed artifacts, and all 192 preregistered Q1/Q2 projections reconcile to the frozen sample.

## Decisive evidence

- Q1: 10 positives across 10 providers, 76 negatives, 10 abstentions, 10 K3 groups, support gate `True`.
- Q2: 14 positives across 14 providers, 72 negatives, 10 abstentions, 14 K3 groups, support gate `True`.

- Parse failures: 0.
- Uncertain non-retriable calls: 0.
- Hard positives: 0; hard negatives: 109 under the frozen full-pool quartiles.
- Total physical cost seconds: 2129.120964.

## Interpretation

Stage A is a support/trainability test over a label-independently enriched sample, not a prevalence estimate. A pass establishes that the frozen pool contains enough observed Q1/Q2 support under the preregistered gates; it does not establish that any learned representation generalizes across sources. A stop decision identifies insufficient support under this exact frozen design and must not be repaired by retrying, replacing, or duplicating identities.

## Main competing explanation

Apparent score failures may reflect ambiguity or noise in the generic unit-level oracle rather than model-correctable candidate ranking. The downstream grouped models and shuffled/ID-only controls are required to distinguish transferable feature signal from selection-stratum, query, or provider memorization.

## Next action and rejection trigger

Build one semantic row per frozen verification key, then compare raw YOLO confidence, FIFO order, aggregate features, and genuine temporal sequences under grouped source/session evaluation. Reject readiness for a physical pilot if performance does not exceed shuffled/ID-only controls, calibration is poor, or gains collapse on the worst provider/query group.
