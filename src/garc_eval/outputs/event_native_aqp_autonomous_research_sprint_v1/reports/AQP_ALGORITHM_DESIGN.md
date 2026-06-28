# AQP Algorithm Design

**Goal:** From replay evidence, abstract a paper method for Event-Native Budgeted AQP with clip-level recall certificates.

---

## Main Algorithm: Diversity-Coverage-Audit (DCA)

**Intuition:** The replay shows three findings that must be combined:
1. Proxy score is weak (AUROC=0.624) and non-monotonic → don't rely on direct ranking
2. Temporal coverage matters (temporal_grid beats top_proxy at B=30) → cover the timeline
3. 42.5% of positives are proxy-blind (low-score) → audit low-score regions

DCA combines budget decomposition (proxy prefilter), temporal coverage (grid), and audit sampling (low-score exploration) in a three-way split.

### Formal Input
- Long video V, anchor grid A = {a_1, ..., a_N} with 10s center clips
- Proxy features F(a_i) → proxy score s_i
- VLM oracle O(a_i) → {positive, negative} (clip-level label)
- Budget B, target recall γ, failure probability δ

### Budget Allocation
Split B into three components:
- **B_cover** = ⌈α·B⌉ — temporal coverage component (α=0.4)
- **B_proxy** = ⌈β·B⌉ — proxy-guided component (β=0.4)
- **B_audit** = B - B_cover - B_proxy — audit component (≈0.2)

### Selection Policy

**Phase 1: Coverage (B_cover)**
- Divide video into K = ⌈N / (B_cover)⌉ time blocks
- From each block, select the anchor with highest proxy score
- Purpose: guarantee temporal coverage, hit event-rich blocks

**Phase 2: Proxy (B_proxy)**
- From remaining anchors (not selected in Phase 1), select top-B_proxy by proxy score
- Apply temporal NMS with adaptive window: w=3 if no clusters found yet, w=1 after first positive
- Purpose: exploit proxy signal where it works (high-score positives)

**Phase 3: Audit (B_audit)**
- From remaining anchors, sample B_audit from the LOWEST proxy quartile
- Use stratified random within Q1 (not just the lowest — spread within Q1)
- Purpose: discover proxy-blind positives (42.5% of events)

### Adaptive Update (optional, Stage 6 extension)
After each oracle call:
- If a positive is found, expand examination to adjacent anchors (cluster expansion)
- Update local positive rate estimate for the time block
- If block positive rate > 2× global rate, reallocate remaining budget to that block

### Result Construction
- Selected positives → event clusters (adjacent positive anchors merged)
- Cluster-level result: {cluster_id, start_anchor, end_anchor, n_anchors, objects}
- Clip-level result: list of positive anchors with VLM evidence

### Quality Statement
- **Anchor recall:** |selected_positives| / |total_positives|
- **Event cluster recall:** |hit_clusters| / |total_clusters|
- **Oracle-relative:** all recall is relative to VLM oracle labels, not human truth

### Expected Advantage (from replay)
At B=80:
- DCA approximate: B_cover=32 (coverage), B_proxy=32 (top-proxy), B_audit=16 (low-score)
- Expected recall: coverage ~0.20 + proxy ~0.15 + audit ~0.05 = ~0.35-0.40
- vs top_proxy=0.25, diversity_prefilter=0.325
- **Expected improvement: +37% over top_proxy, +8% over diversity_prefilter**

### Failure Mode
- If proxy AUROC < 0.55 (nearly random), B_proxy component wastes budget
- If positives are uniformly distributed (no clusters), coverage component doesn't help
- If all positives are high-score (proxy is perfect), audit component wastes budget
- Mitigation: adaptive reallocation after Phase 1 results

---

## Alternative Algorithm B: Cluster-First Adaptive (CFA)

**Intuition:** The cluster_aware upper bound achieves 100% event recall at B=30. An adaptive algorithm that discovers clusters early and expands around them could approach this.

### Policy
1. **Exploration phase** (B/3): Uniform temporal grid to discover event-rich blocks
2. **Cluster expansion phase** (B/3): For each positive found, examine ±2 adjacent anchors
3. **Exploit phase** (B/3): Top-proxy from unexamined anchors

### Expected advantage
- Better event cluster recall than DCA (targets clusters directly)
- Higher precision in event-rich blocks
- Risk: may miss isolated positives (singletons)

### From replay evidence
At B=30, temporal_grid achieves 0.175 anchor recall and 0.37 event recall. If cluster expansion finds 2-3 anchors per positive, CFA could achieve ~0.35 anchor recall and ~0.60 event recall at B=30.

---

## Alternative Algorithm C: Thompson-Stratified Adaptive (TSA)

**Intuition:** The non-monotonic quartile positive rate (Q3 > Q4 > Q2 > Q1) means each stratum has different yield. Use Thompson sampling over strata.

### Policy
1. Stratify anchors into K=4 proxy quartiles
2. Maintain Beta(α_k, β_k) posterior for each stratum's positive rate
3. At each step, sample θ_k ~ Beta(α_k, β_k), select from the stratum with highest θ_k × uncertainty
4. Update posterior after each oracle call

### Expected advantage
- Principled exploration-exploitation tradeoff
- Adapts to non-monotonic stratification
- Provides uncertainty estimates for certificate construction

### From replay evidence
The stratified_proxy_temporal method underperforms (0.025 at B=10), but it uses static allocation. Thompson sampling with adaptive allocation should perform better, especially at B=60+.

---

## Algorithm Recommendations

| algorithm | priority | expected performance | risk |
|---|---|---|---|
| DCA (Diversity-Coverage-Audit) | **MAIN** | best at B=40-100 | moderate (needs tuning α, β) |
| CFA (Cluster-First Adaptive) | alternative | best event recall | high (may miss singletons) |
| TSA (Thompson-Stratified) | future | principled but untested | high (needs validation) |

---

## Safest Claim
"DCA with α=0.4, β=0.4, audit=0.2 outperforms top-proxy by ≥30% in anchor recall at B=80 on dataset3, and the improvement is attributable to coverage and audit components, not proxy quality."

## Highest-Risk Claim
"CFA achieves ≥80% event cluster recall at B=30, approaching the oracle-informed upper bound."

## Minimum Validation Experiment
Run DCA on the full oracle reference with B=40, 60, 80, comparing to top_proxy and diversity_prefilter. If DCA recall > diversity_prefilter recall at B=80, the algorithm is validated.
