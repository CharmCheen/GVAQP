# Adversarial Review — PSVR Core Physical Pilot

## Verdict

`H-COV1 = REVISE`

`PSVR_CORE_INNOVATION_PILOT = WEAK`

## Evidence independently rechecked from raw artifacts

- Stage A: 20/20 valid profile summaries, 10 T_short, 3 T_mid; zero deadline misses and zero replay.
- Stage 2: 45 corrected complete runs and zero corrected failed runs; exact 3-run coverage of every required method/deadline cell.
- All 45 runs share one runtime identity. Every GPU cost is finite/nonnegative. All referenced snapshots exist.
- Replaying each action trace found zero query-before-proxy-observation violations; raw summaries report zero cache replay and every oracle call is physical.
- Coverage-Debt T_long: 3/3 runs have F1 0.074074, precision 1.0, recall 0.038462, one unique event, six calls, and no redundant queries. All simple baseline F1 values are zero.

## Strongest supported conclusion

Observed local proxy signal changes verification value beyond simple farthest-point coverage on this development video: Coverage-Debt and Uniform use the same call counts, endpoint coverage, and endpoint maximum gaps, but only Coverage-Debt recovers an event.

## Decisive contradiction

Coverage-Debt does not improve the best gap trajectory. Macro normalized gap integral is 0.158263, versus 0.156310 for Uniform-Temporal and 0.151569 for fixed Coverage-Interleave. Consequently the named coverage-debt mechanism is not established under the preregistered acceptance rule.

## Alternative explanations and uncertainty

- The gain may be a deterministic coincidence of one video/query and one proxy signal; three runtime repetitions are not three independent research samples.
- Coverage-Debt uses six T_long calls versus fixed Coverage-Interleave's five, but Uniform also uses six and recovers zero. The gain therefore cannot be explained solely by one extra call relative to fixed coverage.
- Mean T_long GPU seconds are about 92.93 for Coverage-Debt versus 90.07 for Uniform. Cost is fully counted, but equivalence is approximate rather than exact.
- The generated early-recall diagnostic is invalid due row-order aggregation. Correct short+mid early recall is zero for all methods; the quality conclusion rests on wall-clock AnytimeAUC_F1, not that field.

## Revision decision

Do not spend the one allowed parameter revision on lambda/beta. Those weights choose among unobserved cells but do not change the number or timing of scan actions, so they cannot match the fixed 20 s gap trajectory. A new action-allocation design must be preregistered and tested as a separate ablation.
