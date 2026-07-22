# Gate C0 protocol: hierarchical block-oracle ceiling

## Question

Under what interval-cost growth curves can exact multi-resolution operators
beat a dense 347-unit complete audit by at least 30%?

## Competing hypotheses

- **C0-strong:** exact count-guided localization reaches 80% recall below 70%
  dense cost with COUNT multiplier 1.25 and a required fixed-cost fraction no
  greater than 0.75.
- **C0-conditional:** it passes only when interval cost is almost constant.
- **C0-no-region:** it fails even at constant interval cost.

The 0.75 and 70% thresholds are pilot engineering gates, not theoretical
constants.

## Compared plans

- dense complete unit audit;
- full recursive binary `ANY_EVENT`;
- root `COUNT_EVENTS` plus public-proxy best-first `ANY_EVENT` splitting;
- the same ANY plan with evaluator-informed priority (ceiling only);
- count-conserving best-first splitting using exact `COUNT_EVENTS`.

Targets are 80%, 90%, and 100% canonical-event recall.  The root exact count
makes the denominator known; every localized anchor is separately certified.

## Cost sweep

The registered grid uses

```text
c(L; alpha) = alpha + (1-alpha)L,
alpha in {0, 0.05, ..., 1}.
```

COUNT multipliers are 1.0, 1.25, and 2.0.  The primary cell is count-guided,
80% recall, COUNT x1.25.  Dense complete audit costs 347.

## Routing

- `STRONG_C0_GO`: authorize a bounded real block-operator accuracy/cost pilot.
- `CONDITIONAL_C0_ONLY`: first measure a very small stratified operator pilot;
  do not build the full algorithm or run broad VLM inference.
- no constant-cost advantage: close the interval route under this contract.

No real-operator claim follows from an exact cached ceiling.

