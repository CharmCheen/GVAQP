# H2 V2 Synthetic Mechanism Screen

## Verdict

`FAIL_SYNTHETIC_MECHANISM_V2_ONLY`

## Frozen result

- Replays: 8100
- DATB/LargestGap nonidentity: 1606/1620 (99.14%)
- Sparse + multimodal DATB-minus-Sequential AUC: 0.210754
- Dense + unimodal DATB-minus-Sequential AUC: 0.295715
- Interaction contrast: -0.084961
- Positive cost-ratio directions: 0/4
- Positive proxy-noise directions: 0/3
- Positive deadline directions: 0/3

## Claim boundary

`BLOCKED_MISSING_EXSAMPLE_END_TO_END_AND_NATURAL_CORPUS`

V1 remains a frozen failure. V2 qualifies only the repaired mechanism and cannot support a natural-corpus paper claim.
