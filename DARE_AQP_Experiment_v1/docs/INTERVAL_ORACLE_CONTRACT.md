# Gate C0 interval-oracle contract

## Purpose and status

This is an exact **ceiling simulator contract**, not an implemented VLM API.
It asks whether changing the physical query unit could create an acceleration
regime before spending GPU/oracle budget on real 30s/60s/120s queries.

Intervals are half-open contiguous ranges `[lo, hi)` of frozen 10-second
units.  Canonical anchors, rather than all positive evidence units, are counted.

## Operators

- `ANY_EVENT(interval) -> bool`: whether at least one canonical anchor lies in
  the interval.
- `COUNT_EVENTS(interval) -> nonnegative integer`: exact canonical-anchor
  count.  Counts obey conservation across a binary split.
- `CERTIFY_EVENT(anchor_unit) -> event_identity`: event identity/materialized
  pseudo-event for a localized anchor.

`LOCALIZE_EVENTS(interval)` is intentionally not simulated: returning all
events from an arbitrary long interval would hide the localization problem in
an unrealistically strong oracle.

## Cost family

For interval length `L` in 10-second units:

```text
c(L; alpha) = alpha + (1 - alpha) * L
```

- `alpha=1`: constant-cost interval query;
- `alpha=0`: cost grows linearly with duration/frame count and is equivalent to
  scanning all included units;
- intermediate values sweep the break-even region.

`COUNT_EVENTS` is additionally multiplied by 1.0, 1.25, or 2.0.  Every
localized event pays one certification unit.  Dense complete unit audit costs
347 and already returns event identity.

This family covers `a+bL` after normalizing `c(1)=1`.  Under fixed frame rate,
`a+b*frames(L)` is the same family with a rescaled `b`.  Actual VLM costs are
unknown and must not be fabricated; they are a later measured input.

## Validity boundary

The simulator assumes exact operators and ignores context-window, frame
sampling, calibration, parse failure, and latency effects.  A C0 GO only says
that a physical-operator feasibility region exists.  It authorizes a small
real block-oracle pilot; it does not validate multi-resolution DARE-AQP.

