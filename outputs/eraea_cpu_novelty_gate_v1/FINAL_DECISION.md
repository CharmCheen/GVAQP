# ERAEA CPU Novelty Gate — Final Decision

## 1. Final Route
**GENERIC_COVERAGE_EXPLAINS_GAIN (G_generic = -0.0194 < 0.02; relation-greedy does not beat the best generic baseline) + NO_GO_EQUAL_YIELD_RESIDUAL_EMPTY (matched-yield median Delta EventF1 = 0.0) + REFERENCE_CIRCULARITY_RISK (K3-defined model-relative reference; policy gain second-order) + BLOCKED_HUMAN_REFERENCE (0 human labels; no independent reference exists locally)**

## 2. Decisive quantities
- G_generic (relation-greedy minus best generic coverage/diversity, median) = -0.0194
- Per cluster: [{"best_generic": "stratified", "best_generic_auc": 0.1699, "cluster": "DALI", "eta_explained": 6.0026, "g_generic": -0.0244, "relation_greedy_auc": 0.1455, "top_proxy_auc": 0.1406}, {"best_generic": "mmr", "best_generic_auc": 0.1669, "cluster": "HANGZHOU", "eta_explained": NaN, "g_generic": 0.0, "relation_greedy_auc": 0.1669, "top_proxy_auc": 0.1669}, {"best_generic": "seiden_ucb", "best_generic_auc": 0.1971, "cluster": "WUHAN", "eta_explained": NaN, "g_generic": -0.0194, "relation_greedy_auc": 0.1778, "top_proxy_auc": 0.1778}]
- Equal-yield residual: median Delta EventF1 = 0.0 (pooled, n=72)
- Reward ablation: R1==R2==R3==R4 exactly; R1-R0 median = 0.0
- Materializer decoupling: gap-aware gain under C1 = 0.0016,
  under K0 = 0.0; k3_aware == gap_aware exactly.
- Deviation audit (budget 100, relation-greedy vs per-cluster best generic):
  n=198, beneficial=29, harmful=30,
  harmful rate=0.15151515151515152

## 3. Per-experiment verdicts
1. **E1 equal-yield residual: EMPTY** — median Delta EventF1 = 0.0 in all
   3 clusters; positive-direction share 7-15%. Relation structure has no
   measurable effect once yield/coverage are controlled.
2. **E2 novelty-killer: relation-greedy LOSES to generic coverage/diversity**
   (G_generic median -0.0194; best generic = stratified/mmr/seiden_ucb per
   cluster). The relation-aware algorithm claim cannot be defended.
3. **E3 reward subtraction: relation terms are INERT** (R1=R2=R3=R4 identical;
   new-component term adds <=0.005 AUC over proxy score on one cluster only).
4. **E4 materializer decoupling: no materializer regime rescues the policy
   gain** (K0 collapses everything; k3-aware scoring identical to gap-aware;
   gap threshold does not matter).
5. **E5 deviation audit**: see section 4.

## 4. Deviation audit summary
 cluster  n_deviations  beneficial  harmful  indifferent  harmful_rate  beneficial_over_harmful                                                                            top_reasons
    DALI           100          16       16           68        0.1600                     1.00 {'TIE_OR_NEGLIGIBLE': 68, 'NEW_EVENT_DISCOVERY': 16, 'WRONG_LOW_VALUE_HIGH_PROXY': 16}
HANGZHOU             0           0        0            0           NaN                      NaN                                                                                     {}
   WUHAN            98          13       14           71        0.1429                     0.93 {'TIE_OR_NEGLIGIBLE': 71, 'WRONG_LOW_VALUE_HIGH_PROXY': 14, 'NEW_EVENT_DISCOVERY': 13}

## 5. Supported claims (MODEL_RELATIVE_DIAGNOSTIC only)
- On the frozen fixed-candidate substrate, generic coverage/diversity baselines
  (stratified / frozen MMR / region-UCB) are at least as good as the
  relation-aware greedy.
- The relation-aware greedy's visible terms (redundancy/merge-risk/boundary)
  never bind on this substrate.
- All policy differences are second-order relative to the materializer and the
  model-relative reference construction.

## 6. Unsupported claims
- ERAEA relation-greedy as a novel algorithm (killed by E1/E2).
- Any real SCAN recovery / short-event discovery / human-event quality claim
  (FIXED_CANDIDATE_REPLAY + MODEL_RELATIVE_DIAGNOSTIC only; 0 human labels).
- Any claim that merge/split/boundary mechanisms matter (R-terms inert).

## 7. Human reference status
BLOCKED_HUMAN_REFERENCE: the independent human EventRelation reference has 0
labels locally. The parallel readiness audit is in HUMAN_REFERENCE_READINESS.md.
CPU-only geometric granularity analysis remains blocked until a continuous-time
human reference exists.

## 8. What would reopen the ERAEA claim
- A matched-yield residual >= 0.03 in >= 4/6 clusters AND a >0.03 gain over the
  best generic baseline on an INDEPENDENT (human) reference — i.e., the current
  model-relative emptiness could in principle be a reference artifact, which is
  exactly why the human reference is the only valid next gate. On the current
  model-relative substrate the claim is closed.
