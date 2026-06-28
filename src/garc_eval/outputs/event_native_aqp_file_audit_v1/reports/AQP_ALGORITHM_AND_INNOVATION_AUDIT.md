# AQP Algorithm and Innovation Point Audit

Based on `AQP_ALGORITHM_DESIGN.md`, `BUDGET_REPLAY_AND_ALGORITHM_FINDINGS.md`, `paper_draft/PAPER_STYLE_RESEARCH_REPORT.md`, and budget replay data.

---

## Q1: Current proposed AQP algorithms

| algorithm | type | priority |
|---|---|---|
| DCA (Diversity-Coverage-Audit) | Static 3-way budget split | MAIN |
| CFA (Cluster-First Adaptive) | Adaptive with cluster expansion | Alternative |
| TSA (Thompson-Stratified Adaptive) | Bayesian adaptive over strata | Future |

## Q2: Most promising for paper main method

**DCA (Diversity-Coverage-Audit)** is the strongest candidate.

Rationale: It directly addresses the three findings from replay:
1. **Coverage (40%):** Temporal grid beats top-proxy at B=30
2. **Proxy exploitation (40%):** Diversity prefilter beats top-proxy at B≥60
3. **Audit (20%):** 42.5% proxy-blind positives need low-score exploration

## Q3: Core problem DCA solves

"How to allocate an expensive oracle budget over temporally correlated clips with a weak, non-monotonic proxy, while maintaining coverage of proxy-blind positives."

**Standard AQP answer (SUPG/ABae):** "Use proxy as ranking function, allocate top-B" — this fails because proxy AUROC=0.624, it's non-monotonic, and 42.5% of positives are proxy-blind.

**DCA answer:** "Split budget into coverage + proxy + audit. Don't trust the proxy alone. Cover the timeline first, exploit the proxy second, audit low-score regions third."

## Q4: How DCA uses the proxy

- NOT as a ranker for final selection
- NOT as a hard filter
- AS a weak stratification signal: each quartile has 8-15% positive rate
- AS a coverage signal: pick best anchor per time block
- AS an audit signal: low-score regions need exploration
- Correct usage: coverage-first, proxy-second, audit-third

## Q5: How DCA saves oracle resources

At B=80 (23% of full scan):
- DCA phase 1 (coverage): 32 calls → guarantees temporal spread
- DCA phase 2 (proxy): 32 calls → exploits proxy where it works
- DCA phase 3 (audit): 16 calls → explores low-score regions

Expected recall: ~35% vs full scan 100% → **77% oracle saving** for ~35% recall.

At B=80, DCA expected ~2.9× recall per call vs random.

## Q6: How DCA handles temporal correlation

- Phase 1 (coverage): enforces temporal spread across K blocks — avoids clustering all budget in one time region
- Phase 2 (proxy with temporal NMS): after selecting top-proxy, apply adaptive NMS to avoid redundant selections within a cluster
- Phase 3 (audit): spread B_audit across Q1 — provides coverage in low-score regions

**Gap:** DCA's coverage phase uses uniform blocks, not adaptive block sizes. The CFA alternative addresses this by expanding around found clusters.

## Q7: How DCA handles boundary/REFINE

**Not.** DCA operates on anchor-level positive/negative labels. Boundaries are not used. Event stitching merges adjacent positive anchors. This is a deliberate design choice — boundary fields are untrustworthy.

## Q8: How DCA handles audit/certificate

- **Audit is built-in:** Phase 3 (B_audit) explicitly samples from low-score quartile
- **Certificate is NOT built-in:** DCA does not construct Pr[R̂ ≥ γ] ≥ 1 − δ. This is marked as future work (E3)
- **Audit fraction (20%) may be too small:** Budget replay showed "audit_aware" (15% low-score) did not improve over top_proxy at any budget. DCA's 20% audit allocation may need to be larger (25-30%) to discover the 17 low-score positives

## Q9: DCA vs existing work

| system | DCA difference |
|---|---|
| SUPG | SUPG assumes i.i.d. frames + AUROC>0.7; DCA handles temporal clips + AUROC=0.624 |
| ABae | ABae estimates class proportion; DCA retrieves event clips |
| ARC | ARC is frame-level detection; DCA is clip-level semantic event |
| ExSample | ExSample uses model confidence; DCA uses external handcrafted proxy |
| LAVA | LAVA improves proxy quality; DCA works with weak proxy |
| LensWalk | LensWalk is interactive; DCA is automated with formal budget |
| TAD | TAD assumes full oracle scan; DCA is budgeted partial scan |
| STRIVE-D | Unknown budget model; if detected: differentiate on certificate |
| Hydro | Hydro is relational; DCA is video with temporal structure |

## Q10: Evidence strength for current claims

### Strong claims (supported by replay on full oracle)
- Proxy AUROC=0.624, below SUPG's operating range of 0.7
- 42.5% of positives are proxy-blind (low-score)
- Top-proxy advantage over random at B=80 is only +1.3%
- Temporal correlation P(1→1)=0.325 (2.83× base rate)
- Budget decomposition (diversity prefilter) beats top-proxy by +30% at B=80
- Cluster-aware upper bound: 100% event recall at B=30

### Moderate claims (needs DCA validation)
- DCA outperforms top-proxy by ≥30% at B=80
- Temporal grid beats top-proxy at B=30
- Audit component is necessary for proxy-blind positives

### Weak claims (not yet validated)
- DCA approaches cluster-aware upper bound
- Post-hoc boundary refinement can produce varied boundaries
- Recall certificate is constructible under temporal correlation

### Unsafe claims
- "Formal recall guarantees" — certificate not implemented
- "Generalizes across videos" — only 3 videos (realcartest, dataset3, dataset2 NO-GO)
- "Boundary refinement is a contribution" — it's a limitation

## Q11: Safest claim
"Budget decomposition (proxy_top(P=2B) → oracle_examine(B) with temporal spread diversity) outperforms score-first top-proxy allocation by ≥30% in anchor recall at B=80 on a VLM-oracle-relative benchmark with proxy AUROC=0.624, replicating the finding on a second video (realcartest) with a different proxy strength (AUC=0.738)."

## Q12: Highest-risk claim
"Cluster-aware adaptive allocation can approach the oracle-informed upper bound (100% event recall at B=30) without oracle knowledge."

## Q13: Experiments needed for paper claims

| missing experiment | enables claim | VLM calls | priority |
|---|---|---|---|
| E1: DCA replay on full oracle | "DCA outperforms top-proxy by ≥30%" | 0 (replay) | HIGH |
| E3: Certificate simulation | "Recall certificate is feasible" | 0 (analysis) | HIGH |
| E2: Second video | "Framework generalizes" | 347 new | MEDIUM |
| E4: Adaptive DCA | "Adaptive allocation reduces gap to upper bound" | 0 (replay) | MEDIUM |
| E5: Post-hoc boundary | "Boundary refinement is viable" | 40 new | LOW |

**Without E1: paper cannot claim DCA works.** (Only diversity prefilter is validated, not the full DCA split.)

**Without E3: paper cannot claim formal guarantees.** (Only feasible with block bootstrap / non-i.i.d. CI.)

**Without E2: paper can only claim "on two videos"** — this is weak for generalization but acceptable for a systems paper with strong experimental methodology.
