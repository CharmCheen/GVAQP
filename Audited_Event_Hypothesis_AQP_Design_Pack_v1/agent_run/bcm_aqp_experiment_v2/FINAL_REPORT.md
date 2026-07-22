# BCM-AQP v2 Final Report

Decision: `NO-GO`

## Strongest supported conclusion

BCM-AQP v2 completed a public-input-only, OracleAccessor-mediated CPU replay on frozen strict benchmark `cbbv2_514c0d360fd5b2a4b5fe`. Its event-F1 AUC is `0.294270`, versus `0.389659` for the best frozen repository baseline and `0.388056` for current MAP/M1. The deltas are `-0.095389` and `-0.093786` respectively.

This is a single-video diagnostic against a VLM-defined pseudo-oracle, not human ground truth and not evidence of general G-ARC performance.

## Decisive evidence

- Strict preflight and every synthetic falsification test passed.
- Planner state and scoring use only public units/proxies plus already queried observations.
- Actual outcomes were obtained only after selection through the frozen `OracleAccessor`.
- Physical VLM calls: `0`; all calls are logical reads of the immutable strict cache.
- Configuration uses preregistered no-training weights `(0.45, 0.20, 0.00, 0.35)` and was not selected from test-reference results.
- Candidate, oracle-informed, and full-oracle materializer ceilings are in `tables/ceilings.csv`; M0/M1 replay is in `tables/materializer_matrix.csv`.
- Mechanism activation failed: the public builder produced 141 hypotheses and all 100 maximum-budget actions were `DISCOVER_CORE`; structure probes and follow-up audit actions were never selected.
- Weight ablations have identical event curves. They share complete query prefixes through budget 50; later ordering differences do not change pseudo-event metrics.
- The selected-score/realized-one-step-F1 diagnostic is in `audit/surrogate_validity_summary.csv` and was computed only after acquisition.

## Competing explanation and uncertainty

The loss may be driven primarily by overfragmented public hypotheses and uncalibrated existence priors, rather than by counterfactual materialization itself: the structure-probing branch was never exercised. The permissive overlap-any pseudo-event evaluator and single-video proxy distribution are additional competing explanations. Cross-video calibration/regret and human-adjudicated evaluation remain unresolved.

## Rejection/revision trigger

Reject this candidate construction now: it fails to expose the claimed BCM mechanism within the full budget. Revise only on development videos, requiring a preregistered mechanism-activation gate and improved score/realized-utility correlation before another frozen evaluation. Reject any future general BCM claim if held-out-video AUC, regret, or calibration fails to reproduce, or if leakage auditing finds unqueried-label/reference access.
