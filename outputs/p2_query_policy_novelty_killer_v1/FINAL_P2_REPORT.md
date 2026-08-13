# Final P2 query-policy novelty-killer report

## Scientific decision

`QUERY_POLICY_ALGORITHMIC_GAP = INCONCLUSIVE`

This is a completed, cached, **MODEL-RELATIVE** novelty-killer audit — not an
engineering incompletion and not a human-semantic claim.

## What is established

- All legal policies used identical frozen unit candidates, two natural proxy
  representations, two complete semantic queries, the same six query budgets,
  and fixed C1 materialization.
- All 432 legal trace prefixes reconstructed hash-identically in an independent
  replay; P2 contains 504 policy/event/budget records and 84 anytime curves.
- StaticProxyRank has a large legal quality advantage over proxy-free coverage:
  mean final F1 `0.5199` versus CoverageFirst
  `0.4876`; pure coverage is not sufficient.
- The canonical generic relevance+coverage rule (fixed λ=0.50) is essentially
  tied with StaticProxyRank: mean final F1 `0.5228`
  versus `0.5199`, while the video-query-cluster
  median ΔF1 is `0.0000` (95% bootstrap
  interval `-0.0136` to
  `0.0223`). Its probability of meeting the
  preregistered practical median ΔF1 threshold is only
  `3.6%`.
- Equal-verified-positive comparisons (`n=39`) have median ΔEventF1
  `0.0000` and median ΔEventRecall
  `0.0000` for generic coverage minus StaticProxyRank.
- The offline full-label oracle diagnostic has median available final-F1
  headroom `0.4766`, but generic coverage
  captures median fraction `0.0000`.
  That oracle sees future full-grid labels/reference events and is **not a legal
  policy**, so this is only a ceiling diagnostic.
- Observed semantic-state residual is `ABSENT`: adding already-verified outcome
  state worsened macro held-out MAE by `0.000090` (LOVO) and `0.001427` (LOVQ)
  rather than yielding the preregistered ≥0.02 improvement.

## Direct answers to the P2 questions

1. **Why StaticProxyRank wins:** its proxy relevance yield is substantially
   higher than UniformTemporal/CoverageFirst; the decomposition is in
   `STATIC_PROXYRANK_DECOMPOSITION.csv`.
2. **Does generic temporal coverage stably help:** no material stable canonical
   improvement was found; it helps selected Proxy-A/DALI cells but is zero or
   adverse elsewhere, particularly under Proxy B.
3. **Does CoverageFirst alone help:** no; it trails StaticProxyRank in final F1
   and anytime AUC despite perfect temporal-axis coverage.
4. **Does relevance+coverage beat relevance:** not at the preregistered
   cluster/practical threshold; all λ values are reported, so there is no
   post-hoc winner selection.
5. **How much headroom does generic coverage explain:** near zero by the fixed
   median fraction diagnostic, but the denominator is an illegal oracle ceiling.
6. **Are proxies consistent:** no stable improvement is replicated across both
   natural proxies; Proxy-B results are mostly ties or losses.
7. **Equal-yield effect:** median effect is zero.
8. **Semantic-state residual:** absent under both LOVO and LOVQ.
9. **Policy-visible state:** all legal baselines use only score/timestamps and
   selected timestamps; no reference-only data enters ordering.
10. **Is a new policy justified:** not yet. The large oracle ceiling demonstrates
   only the value of forbidden full future knowledge; the lack of observable
   state residual prevents treating it as an algorithm specification.
11. **MAB:** `NO`.
12. **P3:** `NO`; no P3 implementation or opportunity specification is justified.

## Why the decision is INCONCLUSIVE, not NOT_ESTABLISHED

The P2 preregistration permits `NOT_ESTABLISHED` only when there is no stable
oracle headroom. Here the full-label diagnostic headroom is large across all
six video-query clusters. But `ESTABLISHED` requires a stable residual that is
predictable from legal already-observed semantic state across two proxies; that
residual is absent. This is exactly the prescribed `INCONCLUSIVE` case: the
remaining ceiling cannot be assigned to a legal semantic-state-aware algorithm
from current evidence.

## Claim boundary and next action

`EVENT_EVIDENCE_GEOMETRY_STATUS_AFTER_P2 = WEAK / NON-CONFIRMATORY`.

`PROJECT_MAINLINE = PIVOT_REQUIRED` for query-policy novelty, while the
two-stage formulation and C1 materialization remain bounded system findings.
Do not reopen MAB/RL, do not build P3, and do not claim human semantic benefit.
The single next action is an independent design that can distinguish the
full-label oracle ceiling from a policy-visible, observed-state signal; it must
be separately preregistered before any P3 work.
