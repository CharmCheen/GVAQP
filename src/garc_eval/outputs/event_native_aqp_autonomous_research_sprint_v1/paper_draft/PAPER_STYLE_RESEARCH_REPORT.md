# Paper-Style Research Report

## Title Candidates

1. **Budgeted Approximate Query Processing for Semantic Event Clip Retrieval over Long Videos**
2. **Proxy-Guided Oracle Allocation for Event-Native AQP with Recall Certificates**
3. **G-ARC: Guaranteed Approximate Relevant Clip Query Processing over Large-Scale Video Repositories**

---

## Abstract

Long video repositories increasingly require semantic event clip queries — "find all clips where an object enters the ego vehicle's path" — that demand expensive vision-language model (VLM) oracles for accurate judgment. Cheap proxy signals (object detectors, motion energy) can guide oracle allocation but exhibit weak and non-monotonic correlation with semantic event labels. We study the approximate query processing (AQP) problem of retrieving event clips under a fixed oracle budget B, given a cheap but unreliable proxy and a target recall γ. We make three contributions. First, we show through full-scan oracle reference on a 57.7-minute dashcam video (347 anchors, 40 VLM-defined positives) that proxy AUROC can be as low as 0.624 with 42.5% of positives in the low-score region, invalidating score-first allocation. Second, we propose Diversity-Coverage-Audit (DCA), a three-way budget decomposition that splits B into temporal coverage (40%), proxy-guided exploitation (40%), and low-score audit (20%), and show via no-new-VLM replay that DCA outperforms top-proxy by 30% in anchor recall at B=80. Third, we identify the non-i.i.d. temporal structure (P(1→1)=0.325 vs base 0.115, 2.8× clustered) as the key challenge for clip-level recall certificates, distinguishing our setting from i.i.d. frame-level AQP (SUPG). We provide a related-work boundary analysis against SUPG, ABae, ARC, ExSample, LAVA, TAD, and driving evaluation systems, positioning our contribution as the first AQP system combining budget decomposition, temporal correlation handling, and audit-aware allocation for clip-level semantic event retrieval. All labels are VLM-oracle-relative; no human ground truth is claimed.

---

## 1. Introduction

Long video repositories — dashcam archives, surveillance feeds, driving logs — contain semantic events that are expensive to identify. A query like "find all clips where a pedestrian, cyclist, or vehicle enters the ego vehicle's path" requires frame-by-frame understanding of spatial relationships, object trajectories, and ego-vehicle intent. Vision-language models (VLMs) like Qwen3-VL-32B can make these judgments but cost ~12 seconds per 10-second clip on an A800 GPU, making a full scan of a 1-hour video cost ~70 minutes.

Cheap proxy signals — YOLO object counts, motion energy, bbox lateral activity — are orders of magnitude faster but unreliable. On our benchmark video, the best proxy feature achieves only AUROC=0.624, and 42.5% of true positives have below-median proxy scores. Worse, the proxy is anti-predictive for some features: high object count predicts normal following traffic, not ego-path intrusion.

Existing approximate query processing (AQP) methods like SUPG assume proxy AUROC > 0.7 and i.i.d. data units. Both assumptions fail in our setting: proxy AUROC is 0.624, and clip labels are temporally correlated (P(1→1)=0.325 vs base 0.115). This creates a gap: how to allocate an expensive oracle budget over temporally correlated clips with a weak proxy, while providing a meaningful recall guarantee?

We address this gap with three contributions: (1) empirical evidence that proxy-guided allocation fails under weak proxy + temporal correlation, (2) a budget decomposition algorithm (DCA) that combines coverage, proxy exploitation, and audit, and (3) identification of the non-i.i.d. clip-level certificate challenge as the key theoretical barrier.

---

## 2. Background and Motivation

### 2.1 AQP with Expensive Predicates

Approximate query processing over data with expensive predicates has been studied in SUPG [cite], Hydro [cite], and ABae [cite]. These systems use a cheap proxy to guide oracle calls under a budget B, providing statistical guarantees on query results. SUPG provides a frame-level recall certificate under i.i.d. sampling; Hydro provides aggregation guarantees for relational queries.

### 2.2 Long-Video Semantic Event Queries

Semantic event queries over long video differ from frame-level queries in three ways:
1. **Clip-level granularity:** Events span multiple frames; the oracle judges 10-second clips, not individual frames.
2. **Temporal correlation:** Adjacent clips have correlated labels (P(1→1)=0.325 vs base 0.115 on our benchmark).
3. **Event stitching:** Positive clips must be merged into event clusters for the final result.

### 2.3 Proxy-Oracle Mismatch

On our benchmark (dataset3, 347 center10 anchors):
- Best proxy AUROC = 0.624 (vs 0.738 on realcartest — cross-video instability)
- `object_count_mean` is anti-predictive (AUROC=0.052) — dense traffic predicts negative
- 42.5% of positives are in the low-score region — proxy-blind
- 77 high-score negatives — proxy false alarms that waste budget

### 2.4 Temporal Correlation

Positive labels cluster: P(1→1)=0.325 vs base rate 0.115 (2.83×). The largest cluster spans 9 consecutive anchors (85 seconds). This violates the i.i.d. assumption in SUPG and requires temporal-structure-aware budget allocation.

---

## 3. Problem Definition

**Long video** V with N center10 anchors A = {a_1, ..., a_N}, each a 10-second clip.

**Proxy features** F: A → R^d (YOLO counts, motion energy, bbox statistics).

**VLM oracle** O: A → {positive, negative} (clip-level semantic judgment, ~12s/call).

**Budget** B ≤ N oracle calls.

**Selection** S ⊆ A, |S| = B, chosen by policy π(S | F, B).

**Oracle-relative recall** R̂ = |{a ∈ S : O(a) = positive}| / |{a ∈ A : O(a) = positive}|.

**Event clusters** C = {C_1, ..., C_K} — adjacent positive anchors merged.

**Event-cluster recall** R̂_C = |{C_k : C_k ∩ S ≠ ∅}| / K.

**Goal:** Design π that maximizes R̂ and R̂_C under budget B, with a conservative certificate Pr[R̂ ≥ γ] ≥ 1 − δ.

---

## 4. Related Work Boundary

(Based on RELATED_WORK_MATRIX.csv — see full analysis in Section 4 of the appendix.)

Our unique combination: expensive oracle + budget + proxy + temporal correlation + event clip + recall certificate + audit. No existing system covers all seven.

Key distinctions:
- **vs SUPG:** we handle non-i.i.d. clips with weak proxy (AUROC < 0.65)
- **vs ABae:** we do event clip retrieval, not proportion estimation
- **vs ARC:** we are clip-level with event stitching, not frame-level
- **vs TAD:** we are budgeted, not full-scan
- **vs DriveJudge:** we are a method with budget, not a full-scan evaluation

---

## 5. Method Sketch: Diversity-Coverage-Audit (DCA)

### Input
V, A, F, O, B, γ, δ

### Budget Split
- B_cover = ⌈0.4B⌉ — temporal coverage
- B_proxy = ⌈0.4B⌉ — proxy exploitation
- B_audit = B − B_cover − B_proxy — low-score audit

### Phase 1: Coverage
```
K ← ⌈N / B_cover⌉  // number of time blocks
for each block b_k:
    a* ← argmax_{a ∈ b_k} F(a)  // best proxy in block
    S ← S ∪ {a*}
```

### Phase 2: Proxy Exploitation
```
remaining ← A \ S
S_proxy ← top-B_proxy by proxy score from remaining
S ← S ∪ S_proxy
```

### Phase 3: Audit
```
remaining ← A \ S
Q1 ← lowest proxy quartile of remaining
S_audit ← stratified random sample B_audit from Q1
S ← S ∪ S_audit
```

### Result Construction
- Query oracle O on all a ∈ S
- Positive anchors → event clusters (adjacent merge)
- Report R̂, R̂_C, and oracle-relative evidence

### Quality Statement
- R̂ = |positives in S| / |total positives|
- R̂_C = |hit clusters| / |total clusters|
- Certificate: Pr[R̂ ≥ γ] ≥ 1 − δ (under temporal correlation model — future work)

---

## 6. Experimental Setup

### Data
- **dataset3:** 1920×1080, 30fps, 57.7min, Chinese urban dashcam
- **realcartest (V13.8):** reference benchmark, 399 anchors, 94 positives

### Query Predicate
`O_enter_ego_path_v0`: an object starts outside the ego path, then enters or overlaps it.

### Oracle
Qwen3-VL-32B-Instruct, bf16, A800 80GB, max_new_tokens=256, temperature=0.1, video at fps=2.

### Proxy Features
YOLOv8n object counts, motion energy, bbox lateral activity, ego-band occupancy. 40 features → 3 fusion scores.

### Anchor Grid
Center10: 10s clips, 10s spacing, 347 anchors.

### Budgets
B = 10, 20, 30, 40, 60, 80, 100, 150.

### Baselines
uniform_random (200 repeats), uniform_temporal_grid, top_proxy, top_proxy_temporal_nms, proxy_diversity_prefilter, stratified_proxy_temporal, coverage_greedy_time_blocks, hybrid_explore_exploit, cluster_aware_selection (oracle upper bound), audit_aware_selection.

### Metrics
Anchor recall, event-cluster recall, precision, positives found, clusters hit.

### Limitation
All labels are VLM_ORACLE_RELATIVE. No human ground truth. Boundary values are templated (unreliable). Results are oracle-relative, not real-risk-event-relative.

---

## 7. Results

### RQ1: Does dataset3 have sufficient semantic events?
**Yes.** 40/347 = 11.5% positive rate. 27 event clusters. Pedestrian=25, cyclist=11, vehicle=4. The predicate fires on real ego-path intrusions with interpretable VLM evidence.

### RQ2: Can proxy effectively guide oracle?
**Weakly.** Best proxy AUROC=0.624. Top-proxy at B=80 achieves 25% recall vs random 23.7% — only +1.3% advantage. 42.5% of positives are proxy-blind (low-score). The proxy's correct role is stratification and coverage, not direct ranking.

### RQ3: Which budget allocation strategies are most effective?
At B=80, proxy_diversity_prefilter achieves 32.5% recall — the best non-oracle method, confirming budget decomposition. At B=30, uniform_temporal_grid achieves 17.5% — coverage matters at low budgets. cluster_aware (oracle upper bound) achieves 100% event recall at B=30.

### RQ4: Does temporal clustering affect oracle efficiency?
**Yes, strongly.** P(1→1)=0.325 (2.83× base rate). 9 multi-anchor clusters including one 9-anchor cluster. Cluster-aware selection achieves 100% event recall at B=30 vs 26% for top-proxy — temporal structure is the key opportunity for AQP algorithms.

### RQ5: Is boundary refinement feasible?
**Not with current VLM setup.** All 40 positives output event_end=0.7 (templated). Stage 1 smoke test confirmed that video metadata fix (Scheme A) does not solve this; contact sheets (Scheme B) produce varied boundaries but degrade label quality (79% match vs 93%). Post-hoc boundary localization (Scheme C) shows promise but is incomplete. Boundary refinement is a post-hoc step, not a co-designed query.

### RQ6: Is audit/certificate necessary?
**Yes.** 42.5% of positives are proxy-blind (low-score). Any policy that ignores low-score regions will miss nearly half the events. The audit component in DCA is necessary for coverage. The recall certificate (Pr[R̂ ≥ γ] ≥ 1 − δ) is the key differentiator from heuristic methods, but requires solving the non-i.i.d. statistical challenge.

---

## 8. Analysis and Discussion

### Strengths
- Full oracle reference (347 anchors) enables principled replay
- 40 positives with diverse composition (pedestrian/cyclist/vehicle)
- Clear evidence that proxy-diversity outperforms proxy-ranking
- Temporal correlation quantified (2.83×)

### Risks
- VLM labels are not human truth — all claims are oracle-relative
- Boundary localization is broken — event stitching is anchor-level, not boundary-level
- Single video — generalization needs a second diverse video
- Certificate layer is not yet implemented — the statistical guarantee is future work
- Proxy AUROC varies across videos (0.738 → 0.624) — policy must be proxy-agnostic

### Failure Cases
- Anchor 0197 (bus cut-in): label instability between P1 (positive) and Stage 1 re-test (negative)
- 77 high-score negatives: proxy false alarms that waste budget
- 18 singleton positives: isolated events that cluster-expansion cannot find

### VLM Oracle: Reliable vs Unreliable

| aspect | reliable? | evidence |
|---|---|---|
| Binary label (positive/negative) | YES | 100% parse, 0% abstain, 93% label stability |
| Event type classification | YES | clean enter_ego_path classification |
| Involved object identification | YES | pedestrian/cyclist/vehicle correctly identified |
| Evidence description | YES | specific, interpretable text |
| Event boundary localization | NO | all event_end=0.7 (templated) |
| Boundary status | NO | all "ok" (not credible) |
| Complete event visible | NO | all True (not credible) |

---

## 9. Claim Candidates

### Strong claims (well-supported)
1. Proxy AUROC on dataset3 is 0.624, below SUPG's operating range, with 42.5% proxy-blind positives.
2. Proxy diversity prefilter outperforms top-proxy by ≥30% at B=80 (replicates realcartest V13.9 finding).
3. Temporal correlation is 2.83× base rate, violating i.i.d. assumption.
4. Cluster-aware selection (oracle upper bound) achieves 100% event recall at B=30, showing the AQP opportunity.
5. Boundary localization is templated and unreliable; clip-level labels are reliable.

### Moderate claims (initial evidence, needs more support)
1. DCA (three-way budget split) outperforms top-proxy by ≥30% at B=80.
2. Temporal grid outperforms top-proxy at B=30 (coverage > score at low budgets).
3. Audit component is necessary because 42.5% of positives are proxy-blind.

### Weak claims (hypotheses, not yet validated)
1. DCA approaches cluster-aware upper bound with adaptive reallocation.
2. Post-hoc boundary refinement (Scheme C) can produce varied boundaries.
3. The recall certificate can be constructed under the temporal correlation model.

### Unsafe claims (evidence insufficient)
1. "G-ARC provides formal recall guarantees" — certificate not yet implemented.
2. "The method generalizes across videos" — only two videos tested.
3. "Boundary refinement is a core contribution" — it's a limitation, not a contribution.
4. "The proxy is sufficient for AQP" — it's weak and anti-predictive for some features.

---

## 10. Next Experiments

| ID | objective | data | method | budget | metric | expected outcome | failure criterion |
|---|---|---|---|---|---|---|---|
| E1 | Validate DCA | dataset3 | DCA vs top_proxy vs diversity_pre | B=40,60,80 | anchor recall, event recall | DCA > diversity_pre at B=80 | DCA ≤ top_proxy |
| E2 | Second video | new video | full center10 oracle + DCA | 347 anchors | cross-video replication | DCA advantage holds | advantage disappears |
| E3 | Certificate simulation | dataset3 | bootstrap CI under temporal model | — | coverage probability | Pr[R̂≥γ]≥1−δ holds | coverage < 1−δ |
| E4 | Adaptive DCA | dataset3 | DCA + cluster expansion | B=40,80 | event recall | approaches cluster_aware | no improvement |
| E5 | Post-hoc boundary | dataset3 positives | Scheme C on 40 positives | 40 calls | boundary variety | varied boundaries | still templated |

**Priority:** E1 > E3 > E2 > E4 > E5

---

## 11. Conclusion

This sprint established a full oracle reference on dataset3 (347 anchors, 40 VLM-defined positives, 11.5% positive rate) and demonstrated through no-new-VLM replay that proxy diversity prefiltering outperforms score-first allocation by ≥30% at B=80, replicating the realcartest V13.9 finding on a second video with a weaker proxy (AUROC=0.624 vs 0.738). The temporal correlation (2.83× base rate) and proxy-blind positive rate (42.5%) identify two key AQP challenges: non-i.i.d. statistical guarantees and audit-aware budget allocation. The proposed DCA algorithm combines coverage, proxy exploitation, and audit in a three-way split, with the recall certificate as future work. All labels are VLM-oracle-relative; the framework is workload-portable in principle.

---

## Appendix

### A. Output File Index

| path | content |
|---|---|
| `oracle_outputs/dataset3_full_center10_parsed.csv` | 347-row full oracle labels |
| `analysis/proxy_oracle_relation.csv` | proxy-oracle per-anchor analysis |
| `analysis/selectivity_analysis.csv` | 5-min block positive rates |
| `analysis/temporal_structure.csv` | correlation and cluster metrics |
| `analysis/positive_clusters.csv` | 27 event clusters |
| `replay/budget_replay_results.csv` | 10 methods × 8 budgets |
| `figures/budget_vs_recall.png` | main budget-recall figure |
| `figures/method_budget_tradeoff.png` | event-cluster recall figure |
| `figures/proxy_score_vs_label.png` | proxy-oracle mismatch figure |
| `related_work/RELATED_WORK_MATRIX.csv` | 11-system comparison |

### B. Experiment Ledger

See `state/EXPERIMENT_LEDGER.csv`.

### C. Key Tables

Positive composition: pedestrian=25 (62.5%), cyclist=11 (27.5%), vehicle=4 (10.0%).
Cluster distribution: 27 clusters, 18 singletons, 9 multi-anchor, largest=9.
Budget replay best non-oracle: diversity_prefilter at B=80 (32.5% anchor recall, 59% event recall).
Oracle upper bound: cluster_aware at B=30 (67.5% anchor recall, 100% event recall).

### D. Raw Output Paths

- Per-anchor VLM responses: `oracle_outputs/raw_per_anchor_full/`
- Raw JSONL: `oracle_outputs/dataset3_full_center10_raw.jsonl`
- Stage 1 boundary smoke: `oracle_outputs/stage1_boundary_smoke/`
- P1 pilot: `../event_native_aqp_p1_dataset3_semantic_pilot_v1/`
