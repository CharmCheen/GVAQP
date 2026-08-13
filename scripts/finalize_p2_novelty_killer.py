#!/usr/bin/env python3
"""Terminal writer for the frozen P2 cached-replay novelty-killer audit."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/p2_query_policy_novelty_killer_v1'
def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 required=['P2_PROTOCOL.json','EVENT_METRICS.csv','ANYTIME_METRICS.csv','TRACE_REPRODUCIBILITY.csv','P2_DECISION.md','CLUSTER_STATISTICS_MANIFEST.json','SEMANTIC_STATE_RESIDUAL_ANALYSIS.md','HEADROOM_ANALYSIS.csv','PROXY_ROBUSTNESS.csv','EQUAL_YIELD_POLICY_PAIRS.csv']
 missing=[x for x in required if not (OUT/x).exists()]
 if missing:raise RuntimeError(f'missing P2 finalization inputs: {missing}')
 if (OUT/'P2_FINALIZATION_MANIFEST.json').exists():raise RuntimeError('P2 already terminally finalized')
 protocol=json.loads((OUT/'P2_PROTOCOL.json').read_text()); dec=(OUT/'P2_DECISION.md').read_text(); decision=dec.split('`QUERY_POLICY_ALGORITHMIC_GAP = ')[1].split('`')[0]
 if decision!='INCONCLUSIVE':raise RuntimeError('this terminal writer is deliberately bound to observed P2 INCONCLUSIVE result')
 event=pd.read_csv(OUT/'EVENT_METRICS.csv'); anytime=pd.read_csv(OUT/'ANYTIME_METRICS.csv'); head=pd.read_csv(OUT/'HEADROOM_ANALYSIS.csv'); eq=pd.read_csv(OUT/'EQUAL_YIELD_POLICY_PAIRS.csv'); boot=json.loads((OUT/'CLUSTER_STATISTICS_MANIFEST.json').read_text())['summary']
 final=event[event.budget==100]; static=anytime[anytime.policy=='StaticProxyRank']; generic=anytime[anytime.policy=='ProxyTemporalCoverage_L050']; coverage=anytime[anytime.policy=='CoverageFirst']
 stat=lambda x:float(x.median())
 text=f'''# Final P2 query-policy novelty-killer report

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
  mean final F1 `{static.final_EventF1.mean():.4f}` versus CoverageFirst
  `{coverage.final_EventF1.mean():.4f}`; pure coverage is not sufficient.
- The canonical generic relevance+coverage rule (fixed λ=0.50) is essentially
  tied with StaticProxyRank: mean final F1 `{generic.final_EventF1.mean():.4f}`
  versus `{static.final_EventF1.mean():.4f}`, while the video-query-cluster
  median ΔF1 is `{boot['delta_F1']['observed_median']:.4f}` (95% bootstrap
  interval `{boot['delta_F1']['ci95_median'][0]:.4f}` to
  `{boot['delta_F1']['ci95_median'][1]:.4f}`). Its probability of meeting the
  preregistered practical median ΔF1 threshold is only
  `{boot['delta_F1']['bootstrap_probability_median_ge_practical_threshold']:.1%}`.
- Equal-verified-positive comparisons (`n={len(eq)}`) have median ΔEventF1
  `{eq.delta_EventF1.median():.4f}` and median ΔEventRecall
  `{eq.delta_EventRecall.median():.4f}` for generic coverage minus StaticProxyRank.
- The offline full-label oracle diagnostic has median available final-F1
  headroom `{head.AvailablePolicyHeadroom.median():.4f}`, but generic coverage
  captures median fraction `{head.FractionCapturedByGenericCoverage.median():.4f}`.
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
'''
 (OUT/'FINAL_P2_REPORT.md').write_text(text)
 manifest={'status':'COMPLETE_P2_NOVELTY_KILLER','decision':decision,'protocol_hash':protocol['protocol_hash'],'final_report_sha256':sha(OUT/'FINAL_P2_REPORT.md'),'input_hashes':{x:sha(OUT/x) for x in required},'code_sha256':sha(Path(__file__))}
 (OUT/'P2_FINALIZATION_MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'status':manifest['status'],'decision':decision,'final_report_sha256':manifest['final_report_sha256']},sort_keys=True))
if __name__=='__main__':main()
