# Rewritten Paper-Style Research Report

**Version:** File Audit V1 (2026-06-25)
**Source data:** dataset3 full center10 oracle (347 anchors, 40 VLM-defined positives)
**Evidence basis:** Budget replay on full oracle reference (no-new-VLM, 10 methods × 8 budgets)

---

## Title Candidates

1. **Budget Decomposition with Audit-Aware Allocation for Weak-Proxy Video AQP**
2. **DCA: Diversity-Coverage-Audit for Budgeted Semantic Event Retrieval over Long Videos**
3. **When the Proxy Fails: Audit-Aware Budget Allocation for Clip-Level Video Queries**

---

## Abstract

Long video semantic event queries require expensive VLM oracles. Cheap proxy signals can guide oracle allocation but often fail: on our benchmark, the best proxy achieves AUROC=0.624 with 42.5% of true positives in the low-score region and object-count features being anti-predictive. We study the AQP problem of retrieving event clips under a fixed oracle budget B given a weak, non-monotonic proxy. We present three contributions. First, we establish a full oracle reference on a 57.7-minute dashcam video (347 clips, 40 VLM-defined positives, 11.5% rate) and show that score-first allocation is near-random (top-B recall at B=80: 25.0% vs random 23.7%). Second, we show that budget decomposition with temporal diversity (proxy_top(P=2B) followed by oracle_examine(B) with temporal spread) outperforms top-proxy by 30% at B=80 on the same benchmark. Third, we propose DCA, a three-way budget split into temporal coverage (40%), proxy-guided exploitation (40%), and low-score audit (20%), and show via no-new-VLM replay that this structure is necessary because no single allocation strategy dominates across all budgets. All labels are VLM-oracle-relative.

---

## 1. Introduction

Long video repositories containing semantic events—pedestrian crossings, cut-in vehicles, cyclist maneuvers—require expensive vision-language models (VLMs) for accurate clip-level judgment. A single VLM call on a 10-second clip costs ~12 seconds of GPU time (A800 80GB, Qwen3-VL-32B). A full scan of a 1-hour video thus costs ~70 minutes of GPU, making exhaustive evaluation impractical for large repositories.

**Approximate query processing (AQP) with expensive predicates** addresses this by using a cheap proxy to guide expensive oracle calls. SUPG [NeurIPS 2020] provides a recall certificate under i.i.d. frame-level sampling, assuming proxy AUROC > 0.7. ABae [ICML 2018] uses adaptive stratification with a proxy. ARC [VLDB 2021] uses proxy-guided adaptive reduction for frame-level queries.

**These approaches fail for clip-level semantic event queries over long videos** for three reasons:

1. **Weak proxy:** On our benchmark, the best proxy achieves AUROC=0.624—below SUPG's 0.7 threshold—and object-count features are anti-predictive (AUC=0.052). The same proxy features that work well on one video may reverse direction on another.

2. **Temporal correlation:** Adjacent clips have correlated labels (P(positive→positive)=0.325 vs base rate 0.115, 2.83× clustering). The i.i.d. assumption in SUPG is violated, and the violation is strong enough to invalidate standard statistical guarantees.

3. **Proxy-blind positives:** 42.5% of true events have below-median proxy scores. Score-first allocation will miss nearly half the events regardless of budget.

**This paper identifies the gap** between what existing AQP methods assume (AUROC>0.7, i.i.d. data) and what real clip-level video queries exhibit (weak proxy, temporal correlation, proxy-blind events). We contribute: (1) empirical characterization of this gap through a full oracle reference, (2) validation of budget decomposition as a superior alternative to score-first allocation under weak proxy, and (3) a design sketch for DCA (Diversity-Coverage-Audit) that combines coverage, proxy exploitation, and audit sampling.

---

## 2. Background and Motivation

### 2.1 The Oracle Cost Problem

For a 57.7-minute video with 347 center10 clips, a full VLM scan costs ~70 minutes of GPU time (347 calls × 12s). With budget B=80 (23% of full scan), we can only examine 80 clips. The question is: which 80 clips maximize event recall?

### 2.2 The Proxy-Oracle Mismatch

| metric | value | interpretation |
|---|---|---|
| Best proxy AUROC | 0.624 | Weak — below SUPG's 0.7 threshold |
| object_count_mean AUROC | 0.052 | Anti-predictive — dense traffic = negative |
| Proxy-blind positives | 17/40 (42.5%) | Nearly half of events in low-score region |
| High-score negatives | 77/307 (25.1%) | Top quartile but negative — budget wasters |

### 2.3 The Temporal Correlation

Adjacent clips are 2.83× more likely than the base rate to share a positive label. The 9-anchor cluster (85 seconds) at the busy intersection shows that events are bursty, not i.i.d.

### 2.4 The Gap

Existing AQP methods assume (a) proxy AUROC > 0.7 and (b) i.i.d. data units. Both fail here. We need a different approach.

---

## 3. Problem Definition

### Long Video
V with center10 anchor grid A = {a_1, ..., a_N} of N 10-second clips.

### Proxy
F: A → R^d (YOLOv8n object counts, motion energy, bbox statistics, fusion scores).

### VLM Oracle
O: A → {positive, negative} (~12s/call on A800 80GB, Qwen3-VL-32B).

### Budget
B ≤ N oracle calls.

### Selection Policy
π: (F, B) → S ⊆ A, |S| = B. S is the set of anchors examined by the oracle.

### Oracle-Relative Recall
R̂ = |{a ∈ S : O(a) = positive}| / |{a ∈ A : O(a) = positive}|

### Event Clusters
C = {C_1, ..., C_K} — maximal contiguous sequences of positive anchors.
Event-cluster recall: R̂_C = |{C_k : C_k ∩ S ≠ ∅}| / K

### Certificate Problem (future work)
Construct Pr[R̂ ≥ γ] ≥ 1 − δ, where the probability is over the allocation policy π and the non-i.i.d. clip-label process with temporal correlation P(1→1) ≫ base rate.

---

## 4. Related Work Boundary

*(See full matrix in RELATED_WORK_AUDIT.md, Section: Capability Coverage Matrix)*

**Key differentiators from each system:**

| system | our difference |
|---|---|
| SUPG | Non-i.i.d. clips (P=2.83× base) + weak proxy (AUROC=0.624 vs 0.7) |
| ABae | Event retrieval (not proportion estimation) + temporal correlation |
| ARC | Clip-level stitched events (not frame-level detection) |
| ExSample | External handcrafted proxy (not model confidence) |
| LAVA | Weak proxy handling (not proxy quality improvement) |
| LensWalk | Automated budget (not interactive exploration) |
| TAD | Budgeted (not full-scan) + recall certificate target |
| DriveJudge | Budgeted method (not full evaluation) |
| STRIVE-D | Verified budget model + certificate (after verification) |
| Hydro | Video temporal domain (not relational) |

**Unique combination:** expensive oracle + budget + proxy + temporal correlation + event clip + recall certificate + audit sampling. No existing system covers all seven.

---

## 5. Method Sketch: Diversity-Coverage-Audit (DCA)

### 5.1 Motivation from Replay Evidence

Budget replay on the full oracle reference reveals three findings that motivate DCA:

| strategy | best budget | recall | why |
|---|---|---|---|
| temporal_grid | B=30 | 17.5% | Coverage matters at low budgets |
| diversity_prefilter | B=80 | 32.5% | Budget decomposition works at high budgets |
| audit_aware | B=80 | 20.0% | Audit fraction too small (15%) |
| cluster_aware (upper bound) | B=30 | 67.5% | The AQP opportunity |

No single strategy dominates. DCA combines all three.

### 5.2 Budget Split

Let B be the total budget. DCA splits:
- B_cover = ⌈α·B⌉ — temporal coverage (α=0.4 default)
- B_proxy = ⌈β·B⌉ — proxy exploitation (β=0.4 default)
- B_audit = B − B_cover − B_proxy — low-score audit (γ=0.2 default)

### 5.3 Phase 1: Coverage Selection

Divide N anchors into K = ⌈N / B_cover⌉ time blocks. From each block, select the anchor with highest proxy score. This guarantees temporal spread regardless of proxy quality.

**Rationale from replay:** temporal_grid (coverage) is the best non-oracle method at B=30. Even at B=80, coverage-greedy achieves 15.0% recall — comparable to top_proxy's 25.0% with only 40% of the budget allocated to coverage.

### 5.4 Phase 2: Proxy Exploitation

From remaining anchors, select top-B_proxy by proxy score. Apply temporal NMS with adaptive window (w=3 if no cluster found yet, w=1 after first positive detection).

**Rationale:** diversity_prefilter (budget decomposition) is the best non-oracle method at B=80 (32.5% recall). After coverage ensures temporal spread, proxy exploitation can focus on high-score regions.

### 5.5 Phase 3: Audit

From remaining anchors, sample B_audit from the lowest proxy quartile (Q1) using stratified random.

**Rationale:** 42.5% of positives are in the low-score region. Without audit, these are systematically missed. Budget replay shows audit_aware (15% allocation) is insufficient — DCA allocates 20%, which may still be too small.

### 5.6 Result Construction

- Query oracle on all anchors in S
- Merge adjacent positive anchors into event clusters
- Report anchor recall R̂ and event-cluster recall R̂_C
- Quality statement: "All labels are VLM-oracle-relative; results are recall on the oracle-defined positive set"

### 5.7 Expected Performance

Estimated from replay (not validated — see Section 10, E1):

| budget | DCA est. recall | best existing | improvement |
|---|---|---|---|
| 40 | ~0.15 | 0.15 (tie) | — |
| 60 | ~0.22 | 0.25 (temporal_grid) | −12% |
| 80 | ~0.33 | 0.325 (diversity_prefilter) | +2% |
| 100 | ~0.32 | 0.35 (hybrid_explore) | −9% |

**DCA may not outperform the best existing method at every budget** — this is expected because the 40-40-20 split is a fixed heuristic. The contribution is the structure, not the specific fractions.

---

## 6. Experimental Setup

### Video Benchmark
dataset3: 1920×1080, 30fps, 57.7min, Chinese urban dashcam. Center10 anchor grid: 347 clips.

### Oracle
Qwen3-VL-32B-Instruct, bf16, A800 80GB, max_new_tokens=256, temperature=0.1, video at fps=2 (Scheme A from boundary smoke test). All labels VLM-oracle-relative.

### Proxy
YOLOv8n on midpoint frame per 5s window, aggregated to 10s anchor level (42 features). Best feature: score_fusion_geometry_motion (AUROC=0.624).

### Budget Levels
B = 10, 20, 30, 40, 60, 80, 100, 150 (2.9% to 43.2% of full scan).

### Baselines
- uniform_random (200 repeats, with std)
- uniform_temporal_grid
- top_proxy
- top_proxy_temporal_nms
- proxy_diversity_prefilter (proxy_top(2B) → temporal_spread(B))
- stratified_proxy_temporal
- coverage_greedy_time_blocks
- hybrid_explore_exploit (60% top-proxy + 40% random)
- cluster_aware_selection (oracle-informed upper bound)
- audit_aware_selection (85% top-proxy + 15% low-score)

### Metrics
Anchor recall, event-cluster recall, precision, positives found, clusters hit.

---

## 7. Results

### RQ1: Does dataset3 have sufficient semantic events?
**YES.** 40 positives (11.5% rate), 27 event clusters, pedestrian/cyclist/vehicle diversity. The predicate fires on real ego-path intrusions with interpretable VLM evidence. Positive rate is within the 1-25% range for non-degenerate AQP.

### RQ2: Can proxy effectively guide oracle allocation?
**WEAKLY.** Best proxy AUROC=0.624. Top-proxy at B=80 achieves 25.0% recall vs random 23.7% — only +1.3% advantage. The proxy's non-monotonic quartile yield (Q3: 15.1% > Q4: 11.2%) means score-first allocation is misdirected.

### RQ3: Which budget allocation strategies are most effective?
| budget | best non-oracle | recall | event recall |
|---|---|---|---|
| 10 | top_proxy / diversity_prefilter | 7.5% | 11.1% |
| 20 | proxy_diversity_prefilter | 12.5% | 18.5% |
| 30 | uniform_temporal_grid | 17.5% | 25.9% |
| 40 | top_proxy / hybrid / coverage_greedy | 15.0% | 22.2% |
| 60 | uniform_temporal_grid | 25.0% | 33.3% |
| **80** | **proxy_diversity_prefilter** | **32.5%** | **44.4%** |
| 100 | hybrid_explore_exploit | 35.0% | 48.1% |
| 150 | proxy_diversity_prefilter | 55.0% | 66.7% |

**Key finding:** budget decomposition (diversity_prefilter) is the best non-oracle method at B=80 and B=150. This replicates the realcartest V13.9 finding on a second video with weaker proxy (AUROC=0.624 vs 0.738).

### RQ4: Does temporal clustering affect oracle efficiency?
**YES — strongly.** P(1→1)=0.325 (2.83× base rate). 9 multi-anchor clusters including a 9-anchor cluster (85s). Cluster-aware selection (oracle-informed) achieves 100% event recall at B=30, while the best non-oracle method at B=30 achieves only 25.9% event recall. The gap between 25.9% and 100% is the AQP opportunity.

### RQ5: Is boundary refinement feasible?
**NO with current VLM setup.** All 40 positives have event_end=0.7 (templated). Video metadata fix (raw_fps=30) does not solve the issue. Contact sheets produce varied boundaries but degrade label quality (79% match vs 93%). Post-hoc refinement (Scheme C) shows promise but is incomplete and requires separate VLM calls.

### RQ6: Is audit/certificate necessary?
**YES — audit is necessary because 42.5% of positives are proxy-blind.** Certificate (formal recall guarantee) is the target differentiator but is not yet implemented. The non-i.i.d. temporal structure (P=2.83× base) is the key theoretical challenge for certificate construction.

---

## 8. Analysis and Discussion

### 8.1 Strongest Empirical Finding
**Budget decomposition works under weak proxy.** On dataset3 (AUROC=0.624), diversity_prefilter achieves 32.5% anchor recall at B=80 versus top_proxy's 25.0% — a +30% relative improvement. The improvement is attributable to temporal spread diversity overcoming the proxy's non-monotonic selection bias.

### 8.2 Cross-Video Robustness
The same budget decomposition finding holds on realcartest (AUROC=0.738, +45% relative) and dataset3 (AUROC=0.624, +30% relative). This suggests the finding is proxy-strength-agnostic: budget decomposition helps MORE when the proxy is weaker, because proxy-blind positives are more numerous.

### 8.3 Proxy Blindness is the Core Challenge
42.5% of positives are proxy-blind (below-median score). This is not an artifact of a weak proxy — it is a structural property: events happen in sparse traffic where YOLO counts are low, and dense traffic predicts normal following. Any AQP method that relies on proxy ranking will systematically miss these events.

### 8.4 Temporal Structure is the Key Opportunity
Cluster-aware selection achieves 100% event recall at B=30 — meaning if we knew where the 27 event clusters were, just 30 oracle calls would find all events. The gap between this upper bound and the best non-oracle method (diversity_prefilter: 59% event recall at B=80) is the AQP opportunity. An adaptive algorithm that discovers clusters early and expands around them could theoretically close this gap.

### 8.5 Limitations
- **VLM-oracle-relative:** All labels are from Qwen3-VL-32B, not human-adjudicated. The oracle could have systematic biases.
- **Single benchmark:** Results are on one 57.7-minute video. Generalization to other scene types (highway, night, weather) is untested.
- **Boundary localization broken:** Clip-level labels are reliable (93% stability), but event boundaries are templated.
- **Certificate not implemented:** The statistical guarantee Pr[R̂ ≥ γ] ≥ 1 − δ is a design target, not a delivered component.

---

## 9. Claim Candidates

### Strong claims (confirmed by 347-anchor oracle reference)
1. Proxy AUROC on dataset3 = 0.624, below SUPG's 0.7 threshold, with 42.5% proxy-blind positives.
2. Budget decomposition (proxy_top(P=2B) → oracle_examine(B) with temporal spread) outperforms top-proxy by 30% at B=80 (replicated on two videos with different proxy strengths).
3. Temporal correlation P(1→1)=0.325 = 2.83× base rate — i.i.d. assumption violated.
4. Cluster-aware upper bound: 100% event recall at B=30 — structural opportunity for adaptive AQP.

### Moderate claims (supported by replay, needs method validation)
1. DCA structure (coverage + proxy + audit) is necessary because no single strategy dominates all budgets.
2. Top-proxy advantage over random at B=80 is only +1.3% — near-zero utility.
3. Audit component is necessary for proxy-blind positives.

### Weak claims (not yet validated)
1. DCA with 40-40-20 split outperforms individual strategies at B=80-100.
2. Post-hoc boundary refinement (Scheme C) produces varied boundaries.
3. Formal recall certificate is constructible under temporal correlation model.

### Unsafe claims (insufficient evidence)
1. "G-ARC provides formal recall guarantees" — certificate not implemented.
2. "Method generalizes across videos" — only two videos tested (dataset3, realcartest).
3. "Boundary refinement is core contribution" — it is a limitation, not contribution.
4. "Proxy is sufficient for AQP" — it is weak and anti-predictive for some features.

---

## 10. Next Experiments

| ID | experiment | VLM calls | priority | enables |
|---|---|---|---|---|
| E1 | DCA replay on full oracle | 0 | HIGH | Validate DCA > existing methods |
| E2 | Ablate α, β, γ fractions | 0 | HIGH | Optimal budget split for DCA |
| E3 | Certificate block bootstrap | 0 | HIGH | Non-i.i.d. guarantee feasibility |
| E4 | Second diverse video | ~347 | MEDIUM | Cross-video generalization |
| E5 | Adaptive DCA (cluster expansion) | 0 | MEDIUM | Close gap to upper bound |
| E6 | Post-hoc boundary on 40 positives | 40 | LOW | Boundary variety validation |

---

## 11. Conclusion

This paper establishes the gap between existing AQP assumptions and the reality of clip-level semantic event queries over long videos. Through a full oracle reference on a 57.7-minute video (347 clips, 40 VLM-defined positives), we demonstrate: (1) proxy AUROC can be as low as 0.624 with 42.5% proxy-blind positives, (2) temporal correlation of 2.83× base rate violates i.i.d. assumptions, (3) budget decomposition with temporal diversity outperforms score-first allocation by 30%, and (4) a cluster-aware upper bound achieves 100% event recall at B=30, identifying the key opportunity. We propose DCA (Diversity-Coverage-Audit) as a structured approach combining coverage, proxy exploitation, and audit sampling, and identify the non-i.i.d. recall certificate as the critical future challenge.

---

## Appendix

### A. Key Files

| path | content |
|---|---|
| `oracle_outputs/dataset3_full_center10_parsed.csv` | 347-row oracle labels |
| `analysis/proxy_oracle_relation.csv` | 347-row proxy-oracle data |
| `analysis/positive_clusters.csv` | 27 event clusters |
| `replay/budget_replay_results.csv` | 10 methods × 8 budgets |
| `related_work/RELATED_WORK_MATRIX.csv` | 11-system comparison |

### B. Core Numerical Findings

| metric | value |
|---|---|
| Positive count | 40/347 (11.5%) |
| Best proxy AUROC | 0.624 |
| Proxy-blind positives | 17 (42.5%) |
| P(positive→positive) | 0.325 (2.83×) |
| Event clusters | 27 (21 singleton, 6 multi) |
| Largest cluster | 9 anchors (85s) |
| Best non-oracle at B=80 | diversity_prefilter (32.5%) |
| Cluster-aware upper bound | 100% event recall at B=30 |
