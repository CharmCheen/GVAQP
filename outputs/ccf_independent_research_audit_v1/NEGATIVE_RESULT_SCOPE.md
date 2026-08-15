# Negative-result scope

Which negative results genuinely falsify a hypothesis, versus which falsify
only a particular implementation or substrate.

## Genuinely falsified (within scope)

- Complex K3 materializer as a novel mechanism (C-F). Mechanism ablation on 54
  same-trace pairs attributes essentially all gain to the 10-second gap rule
  (median +0.1377); duration cap, negative barrier, and K3 extras have median
  increment 0.0. The complex mechanism is dead as a novelty claim.
- The specific learned selective-deviation rule trained on the 108 cached
  states. Learned regret 0.009693 versus fixed always-VERIFY 0.000885; the
  learned rule is worse and does not generalize across the two source videos.
- MAB / contextual-bandit / learned controller on the current substrate (C-G).
  0/18 immediate strong positives, 1/7 timing-only continuation conversion,
  near-random public-state prediction, worse regret than fixed action.

These are falsifications of specific mechanisms/implementations, and the
project labels them CLOSED / NO-GO. They are correctly recorded as such.

## Falsifies only a substrate/implementation (NOT the hypothesis)

- The controller NO-GO does NOT falsify "state-dependent SCAN/VERIFY allocation
  is valuable" (Claim B). The substrate has no endogenous sensing, no natural
  exposure misses, no measured costs, no natural state prevalence, and no human
  utility. A negative on this substrate is a negative on emulated
  information-release ranking, not on adaptive allocation in a faithful system.
- The P2 INCONCLUSIVE result (generic relevance+coverage ties StaticProxyRank)
  does NOT falsify the human-geometry hypothesis (H1). It is model-relative and
  ran before human P1. It weakens the query-policy novelty claim but leaves H1
  formally untested.
- The VLM-direct shadow LOW result does NOT falsify H1. The shadow reference has
  low annotator agreement and same-checkpoint dependence; it is a feasibility
  warning, not human truth.
- The "98/108 indifferent states" prevalence observation does NOT establish
  that natural high-regret states are rare; the 108 states are behavior-sampled,
  not population-weighted.

## Negative results that are actually bounded positive findings in disguise

- "Exposure degradation produces 0 low-budget gap" is not a failure of the
  experiment; it is a correct identifiability statement that the current
  substrate measures ranking only. It is a diagnostic of construct limitation,
  not a null result about the real system.

## Summary of scope discipline

The repository's own vocabulary ("NO-GO / CLOSED is not universal
impossibility") is scientifically correct and is preserved here. The two
load-bearing negative conclusions that a reader might over-extend are:

1. controller NO-GO → does not extend to faithful endogenous SCAN;
2. geometry/shadow/P2 weakening → does not replace the still-missing human
   reference.

The one negative that is robust and load-bearing for the paper is the complex-K3
mechanism ablation: it removes a specific novelty candidate permanently.
