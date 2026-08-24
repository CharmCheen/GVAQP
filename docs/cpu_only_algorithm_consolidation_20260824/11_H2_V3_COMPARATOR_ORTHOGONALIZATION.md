# H2 V3 Comparator-Orthogonalized Holdout Protocol

## Motivation

H2 V2 established DATB/LargestGap nonidentity but failed the preregistered
DATB-minus-Sequential regime contrast. A required comparator audit then showed
that this contrast combines two mechanisms:

\[
U(DATB)-U(Sequential)
= [U(DATB)-U(LargestGap)]
+ [U(LargestGap)-U(Sequential)].
\]

Therefore it cannot isolate discovery/verification coupling. This is a causal
estimand error, not authorization to reinterpret V1 or V2 as positive.

## Frozen V3 estimand

The mechanism estimand is now:

\[
\Delta_{coupling}=U(DATB)-U(LargestGap).
\]

The temporal-order estimand is reported separately:

\[
\Delta_{ordering}=U(LargestGap)-U(Sequential).
\]

The primary regime contrast is sparse+multimodal minus dense+unimodal on
`Delta_coupling`.

## Anti-overfitting controls

- The original 324-point design and generator are unchanged.
- Cost ratios, factor levels, and five policies are unchanged.
- The original `0.05` interaction threshold is unchanged.
- Direction requirements remain 3/4 cost ratios, 2/3 noise levels, and 2/3
  deadlines.
- Five new holdout seeds are generated deterministically as the first eight bytes
  of `SHA256("H2_V3_HOLDOUT:<index>")`; no seed is selected by outcome.
- V1 and V2 remain frozen failures and are not superseded.

## Decision rule

`PASS_SYNTHETIC_COUPLING_MECHANISM_ONLY` requires all frozen conditions and at
least 5% DATB/LargestGap nonidentity. Otherwise the sparse+multimodal mechanism
hypothesis is retired for the current generator and DATB definition.

No V3 result can support a paper claim without ExSample-EndToEnd, natural corpus,
C3 cost, independent workloads, and human MEC external validation.

