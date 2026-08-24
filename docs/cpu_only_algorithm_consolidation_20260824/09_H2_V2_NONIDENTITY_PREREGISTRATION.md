# H2 V2 Non-Identity Preregistration

## Why a versioned rerun is admissible

H2 V1 is frozen as `FAIL_SYNTHETIC_MECHANISM_SCREEN_ONLY`. Post-hoc inspection
showed exact equality between DATB-SV and LargestGap for every design-seed row.
The V1 implementation therefore did not instantiate an independently testable
SCAN/VERIFY coupling mechanism.

H2 V2 is not a reinterpretation or overwrite of V1. It is a new implementation
qualification run after replacing the alias with a deterministic value-rate
planner. V1 remains part of the falsification record.

## Frozen items retained from V1

- 324 design points;
- factor construction `F = (A + B + C + D) mod 3`;
- cost ratios `{1, 3, 10, 30}`;
- five original seeds;
- five policy labels;
- primary synthetic estimand: sparse+multimodal minus dense+unimodal contrast of
  DATB-minus-Sequential normalized anytime AUC;
- threshold `interaction contrast >= 0.05`;
- positive direction in at least 3/4 cost ratios, 2/3 noise levels, and 2/3
  deadline levels.

## Sole method change

DATB-SV now compares causally available action value rates:

\[
R_V(c)=\frac{p_{proxy}(c)\,n(c)}{cost_V(c)}
\]

and

\[
R_S(u)=\frac{\hat p_{hit}\,g(u)}{cost_S(prev,u)}.
\]

Here `n(c)=0.25` for an already committed participant-track tuple and 1 otherwise;
`p_hit` is the beta-smoothed observed non-fallback candidate rate; and `g(u)` is
the normalized distance to the current temporal anchors. No label, oracle result,
future candidate, trained controller, or fitted threshold enters the decision.

## Added implementation gate

At least 5% of design-seed rows must have nonzero DATB-minus-LargestGap AUC.
Failure is `DATB_LARGEST_GAP_NONIDENTITY_FAIL` and blocks interpretation of H2.

## Claim boundary

Even a V2 synthetic PASS is only a mechanism qualification. It cannot establish
natural prevalence, C3 cost benefit, human event utility, or superiority over
ExSample-EndToEnd.

