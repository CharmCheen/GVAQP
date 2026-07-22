# Independent adversarial review: Gate C0

Review date: 2026-07-11.  The reviewer made no file changes.

## Verdict

No undercharging, stopping, conservation, or cost bug was found that reverses
`CONDITIONAL_C0_ONLY`.

The primary cell was independently reconstructed as

```text
C(alpha) = 1.25 * [85*alpha + 1231*(1-alpha)] + 21.
```

It has continuous break-even `alpha > 0.919267`; the registered 0.05 grid
first passes at 0.95, above the strong-GO threshold 0.75.

## Findings and resolutions

1. **Missing unit-order comparators (medium).**  The first C0 output omitted
   uniform and ARC/MAP acquisition orders requested by the research route.
   Resolution: frozen strict selected-unit traces are now summarized in
   `unit_order_comparators.csv`.  They are contextual comparators and do not
   alter the registered C0 primary.
2. **Only grid threshold reported (low).**  Resolution: both analytic
   continuous and registered-grid thresholds are now emitted.
3. **Weak conservation/cost tests (low).**  Resolution: exhaustive small-N
   count recovery and closed-form cost tests were added.

## Confirmed semantics

- root COUNT legally supplies the recall denominator;
- each split queries the left count and infers the right by exact conservation;
- positive leaves localize anchors, and every localized anchor pays a separate
  certification cost;
- ANY splitting does not undercharge and can conservatively over-query one
  sibling in the target-reaching split;
- dense complete audit and interval plus certification have identity-compatible
  outputs under the pilot contract;
- the unit-audit zero-hit lower-bound formula and numerical table are correct.

## Remaining threat

The ceiling assumes exact interval COUNT/ANY.  Real operator error and measured
duration/frame cost remain entirely unresolved and can only weaken the result.

