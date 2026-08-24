# Frozen H2 Synthetic Analysis Plan V1

Status: `FROZEN_BEFORE_FULL_H2_OUTCOMES`

## Primary question

Does the DATB-SV advantage increase from dense/unimodal to sparse/multimodal event regimes under a common C1 simulated cost contract?

## Primary endpoint

Normalized Anytime Distinct-Committed-Event AUC.

## Named primary comparator

`ExSample-EndToEnd` is the claim-grade named comparator. Until its shared-engine implementation exists, the five-policy H2 matrix is mechanism preflight only and cannot establish the primary comparative claim.

## Primary contrast

For each frozen baseline, compute:

```text
Delta = AUC(DATB-SV) - AUC(baseline)

H2 contrast =
mean Delta in sparse+multimodal cells
-
mean Delta in dense+unimodal cells
```

## PASS rule

- H2 contrast is at least 0.05 normalized AUC.
- Direction agrees at no fewer than three of four frozen VERIFY/SCAN cost ratios.
- Direction holds against Sequential and ExSample-EndToEnd.
- The result is not explained by one noise or deadline level.

If ExSample-EndToEnd is unavailable, the status cannot exceed `MECHANISM_PREFLIGHT_PARTIAL`.

## Statistical model

Fit the frozen main-effects and two-factor-interaction model over the 324-point design. Primary interaction families are policy-by-density, policy-by-temporal-modes, policy-by-cost-ratio, and policy-by-deadline. Interactions of order three or higher are excluded.

## Exclusions

Only the four exclusions listed in `frozen_h2_generator_spec_v1.json` are permitted. Runtime failures remain in the result matrix with an explicit failure status.

## Cost statement

Every result is labeled `C1 / simulated-bound / PARTIAL cost validity`. No measured wall-clock or deployment deadline claim is permitted.
