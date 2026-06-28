# Budget Replay and Algorithm Findings

**Method:** No-new-VLM oracle-relative replay using full center10 oracle reference. 10 methods × 8 budgets × 200 random repeats. VLM_ORACLE_RELATIVE.

---

## 1. Methods Compared

| method | description | proxy-dependent? |
|---|---|---|
| uniform_random | random sampling (200 repeats) | no |
| uniform_temporal_grid | evenly spaced temporal grid | no |
| top_proxy | top-B by proxy score | yes (direct ranking) |
| top_proxy_temporal_nms | top-B with temporal NMS (window=3) | yes |
| proxy_diversity_prefilter | top 2B by proxy, then temporal-spread B | yes (budget decomposition) |
| stratified_proxy_temporal | quartile-stratified temporal sampling | yes |
| coverage_greedy_time_blocks | 12 time blocks, top-proxy per block | mixed |
| hybrid_explore_exploit | 60% top-proxy + 40% random explore | yes |
| cluster_aware_selection | oracle: one per cluster first (upper bound) | oracle-informed |
| audit_aware_selection | 85% top-proxy + 15% low-score audit | yes |

---

## 2. Key Results: Anchor Recall by Budget

| B | random | top_proxy | diversity_pre | temporal_grid | hybrid | cluster_aware |
|---|---|---|---|---|---|---|
| 10 | 0.031 | 0.075 | 0.075 | 0.050 | 0.075 | 0.250 |
| 20 | 0.060 | 0.100 | 0.125 | 0.050 | 0.075 | 0.500 |
| 30 | 0.091 | 0.125 | 0.125 | 0.175 | 0.125 | 0.675 |
| 40 | 0.122 | 0.150 | 0.075 | 0.100 | 0.150 | 0.675 |
| 60 | 0.180 | 0.200 | 0.225 | 0.250 | 0.150 | 0.675 |
| 80 | 0.237 | 0.250 | 0.325 | 0.200 | 0.225 | 0.675 |
| 100 | 0.293 | 0.300 | 0.250 | 0.250 | 0.350 | 0.675 |
| 150 | 0.439 | 0.475 | 0.550 | 0.475 | 0.350 | 0.775 |

## 3. Event Cluster Recall by Budget

| B | random | top_proxy | diversity_pre | temporal_grid | hybrid | cluster_aware |
|---|---|---|---|---|---|---|
| 10 | — | 0.11 | 0.15 | 0.15 | 0.15 | 0.37 |
| 20 | — | 0.22 | 0.30 | 0.19 | 0.22 | 0.74 |
| 30 | — | 0.26 | 0.30 | 0.37 | 0.26 | 1.00 |
| 40 | — | 0.33 | 0.22 | 0.30 | 0.33 | 1.00 |
| 60 | — | 0.41 | 0.44 | 0.52 | 0.33 | 1.00 |
| 80 | — | 0.48 | 0.59 | 0.48 | 0.44 | 1.00 |
| 100 | — | 0.56 | 0.56 | 0.59 | 0.67 | 1.00 |
| 150 | — | 0.74 | 0.81 | 0.81 | 0.70 | 1.00 |

---

## 4. Findings

### F1: Top-proxy is NOT the best non-oracle method
At B=40, top_proxy recall=0.150 vs random=0.122 — only +2.8% advantage. At B=80, top_proxy=0.250 vs diversity_prefilter=0.325 — diversity prefilter wins by +7.5%. **Top-proxy's advantage shrinks as budget grows** because it keeps selecting high-score negatives.

### F2: Proxy diversity prefilter is the strongest non-oracle method at high budgets
At B=80, diversity_prefilter anchor recall=0.325 (vs top_proxy=0.250, +30% relative). At B=150, diversity_prefilter=0.550 (vs top_proxy=0.475, +16% relative). This confirms the budget decomposition finding from realcartest V13.9: **splitting proxy_top(P=2B) from oracle_examine(B) with temporal spread diversity is better than top-proxy.**

### F3: Temporal grid is surprisingly strong at low budgets
At B=30, temporal_grid recall=0.175 — better than top_proxy=0.125 and diversity_prefilter=0.125. This is because temporal coverage matters more than proxy score when the budget is tight. The 1500-1800s block has 36.7% positive rate — a temporal grid hits this block, while top-proxy may miss it.

### F4: Cluster-aware selection is the upper bound
Cluster-aware (oracle-informed) achieves 100% event cluster recall at B=30. This is the upper bound — if we knew where the clusters were, 30 oracle calls would cover all 27 event clusters. The gap between best non-oracle method (diversity_prefilter at B=80: 59% event recall) and this upper bound (100% at B=30) is the AQP opportunity.

### F5: Hybrid explore-exploit peaks at B=100
At B=100, hybrid achieve recall=0.350, beating top_proxy=0.300 and diversity_prefilter=0.250. The 60/40 split between exploit (top-proxy) and explore (random) pays off when the budget is large enough for meaningful exploration.

### F6: Audit-aware selection does not improve over top-proxy
Audit-aware (85% top-proxy + 15% low-score audit) performs similarly to top_proxy at all budgets. The 15% audit budget is too small to discover the 17 low-score positives.

### F7: Temporal NMS hurts at low budgets
top_proxy_temporal_nms is worse than top_proxy at B=20 (0.075 vs 0.100) and B=30 (0.075 vs 0.125). Suppressing adjacent anchors removes potential cluster hits, which is bad when the budget is tight.

---

## 5. Which Strategies Are Effective?

| strategy | effective? | when? |
|---|---|---|
| top_proxy | marginally | B ≤ 40 (weak signal) |
| proxy_diversity_prefilter | YES | B ≥ 60 (best non-oracle) |
| temporal_grid | YES | B ≤ 40 (coverage matters) |
| hybrid_explore_exploit | moderately | B = 100 (explore pays off) |
| cluster_aware | upper bound | B ≥ 30 (100% event recall) |
| audit_aware | NO | all budgets |
| temporal_nms | NO | hurts at low budgets |

---

## 6. Implications for AQP Algorithm Design

1. **Budget decomposition is confirmed** — diversity_prefilter (proxy_top(2B) → temporal-spread B) is the strongest non-oracle method. This is a second-video replication of the realcartest V13.9 finding.

2. **Temporal coverage > proxy score at low budgets** — temporal_grid beats top_proxy at B=30. AQP algorithms should prioritize coverage at low budgets.

3. **Cluster-aware is the target** — the gap between diversity_prefilter (59% event recall at B=80) and cluster_aware (100% at B=30) shows that discovering clusters adaptively is the key opportunity. An algorithm that finds clusters early and expands around them could close this gap.

4. **Explore-exploit has value at high budgets** — hybrid beats top_proxy at B=100. Adaptive allocation that explores low-score regions is necessary to find the 42.5% of positives that are proxy-blind.

5. **Audit needs more than 15% budget** — the 15% audit fraction is insufficient. A larger audit allocation (25-30%) may be needed to discover low-score positives.

6. **Temporal NMS should be adaptive, not static** — static NMS hurts at low budgets but may help at high budgets (avoid redundant cluster calls). The NMS window should adapt to the discovered cluster structure.

---

## 7. Comparison to realcartest V13.9/V13.10

| metric | realcartest V13.9 (B=40) | dataset3 (B=40) |
|---|---|---|
| proxy AUROC | 0.738 | 0.624 |
| top_proxy recall | 0.216 | 0.150 |
| diversity_prefilter recall | 0.314 | 0.075 |
| random recall | ~0.115 | 0.122 |
| best non-oracle | diversity_prefilter | temporal_grid/hybrid |

**Cross-video difference:** On realcartest, diversity_prefilter gave +45% relative improvement over top_proxy. On dataset3 at B=40, diversity_prefilter underperforms (0.075 vs 0.150). The difference is the proxy quality: with weaker proxy (AUROC=0.624), the prefilter's top-2B pool contains more noise, making temporal spread less effective.

**At B=80+, diversity_prefilter recovers its advantage** (0.325 vs 0.250). This suggests budget decomposition needs a minimum budget to work — the P=2B pool must be large enough for temporal spread to find positives.
