# Action-Selection Opportunity Audit

`ACTION_SELECTOR_OPPORTUNITY = WEAK`

`CONTEXTUAL_BANDIT_REOPEN = NO`

## Actual action space

The maintained research contract exposes `SCAN_FIXED`, `VERIFY_TOP1`, and `STOP`; current prose often calls VERIFY `CONFIRM`.  REFINE is not a first-class action in this contract.  Observable state includes elapsed/remaining fraction, scanned fraction, frontier size/top/mean score, committed-event count, and scan/verify counts.  The primary proxy stress replay does not recreate progressive SCAN: all candidate/proxy rows are precomputed, so it cannot by itself validate an adaptive SCAN/VERIFY controller.

## Existing counterfactual evidence

- The cached 108-state headroom audit found heterogeneous realized action values: 25 `SCAN_BETTER`, 26 `VERIFY_BETTER`, 57 tied, with both directions on two source videos.  This is evidence that state-dependent value can exist.
- The corresponding public-state predictability audit failed its gate.  Best fixed `always_verify` regret was `0.000885`; the best learned linear rule had regret `0.009693` (10.95× worse), and the contextual-bandit control had regret `0.010325`.
- Those audits use two sources, older query/reference assets and abstract costs rather than current V3 physical time.  The older PSVR bottleneck program also ended `COMPLETE_NO_GO`, with no cross-video scan/verify quality signal.

## Decision

The evidence meets neither requirement for `STRONG`: observable-state-dependent best actions exist in a diagnostic replay, but simple fixed-policy regret is tiny and learned/public-state decisions do not exploit the heterogeneity.  Therefore MAB remains `ARCHIVED_NON_MAINLINE`.  A theory-level fit to a bandit/SMDP is not empirical justification to reopen it.
