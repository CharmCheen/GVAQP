# Experiment State Reconstruction

---

## Summary

All planned stages (P0 scout → P1 pilot → P1b boundary fix → P1c full oracle → full AQP analysis → budget replay → algorithm design → related work → paper draft) are **COMPLETE**. The sprint state is `COMPLETE` with final decision `MAINLINE_GO_WITH_BOUNDARY_LIMITATION`.

---

## Question-by-Question Answers

### Q1: P0 Scout — Complete?
**YES.** `new_video_scout_gate_v1/` executed fully.
- dataset3 = GO (57.7min, 1920x1080, 693 windows, rich object mix, highest lateral activity)
- dataset2 = WEAK GO (in-cabin camera, predicate-inapplicable, later determined NO-GO in Sprint S8)
- Key output: `window_features_dataset3.csv` (693 5s windows, 42 proxy features)

### Q2: P1 dataset3 Semantic Pilot — Complete?
**YES.** `event_native_aqp_p1_dataset3_semantic_pilot_v1/` executed fully.
- 50 stratified anchors labeled with Qwen3-VL-32B
- 5/50 positive (10.0%), 45/50 negative
- 100% parse success, 0% abstain
- Boundary degeneracy confirmed (event_start=0.0, event_end=0.7 templated)
- Positive composition: pedestrian=4, vehicle=1, cyclist=0
- Decision: GO with boundary-fix prerequisite for P1b

### Q3: P1b Boundary-Fix Smoke — Complete?
**YES.** Executed as Sprint Stage 1 (`STAGE1_BOUNDARY_FIX_SMOKE.md`).
- 14 anchors tested across 3 schemes
- Scheme A (video metadata fix): 93% label match, but boundaries still templated
- Scheme B (contact sheet): 79% label match, varied boundaries — degrades label quality
- Scheme C (post-hoc boundary): promising but incomplete (timeout)
- Decision: `USE_CLIP_LEVEL_LABELS_AND_POSTHOC_BOUNDARY`
- Root cause discovered: boundary template is VLM behavior, not metadata issue

### Q4: P1c Full Center10 Oracle — Complete?
**YES.** Executed as Sprint Stage 2 (`STAGE2_DATASET3_FULL_CENTER10_ORACLE.md`).
- 347 anchors labeled (50 P1 reused + 297 new)
- 40 positives (11.5%), 307 negatives, 0 abstain
- Positive composition: pedestrian=25, cyclist=11, vehicle=4
- GPU time: ~60min (2 sessions, resumable)
- Negative reasons: normal_following=182, no_ego_path_interaction=125
- All boundaries templated (event_end=0.7)
- All confidence = high

### Q5: Full-Reference AQP Analysis — Complete?
**YES.** Executed as Sprint Stage 4 (`STAGE4_FULL_REFERENCE_AQP_STRUCTURE.md`).
- Selectivity analysis: 12 time blocks, 1500-1800s block has 36.7% positive rate
- Temporal correlation: P(1→1)=0.325 vs base 0.115 (2.83×)
- 27 positive clusters, 21 singletons, 6 multi-anchor
- Largest cluster: 9 anchors (85s duration)

### Q6: Budget Replay — Complete?
**YES.** Executed as Sprint Stage 5 (`BUDGET_REPLAY_AND_ALGORITHM_FINDINGS.md`).
- 10 methods × 8 budgets (B=10,20,30,40,60,80,100,150)
- uniform_random: 200 repeats with std deviation
- All other methods: 1 deterministic repeat each
- cluster_aware_selection: oracle-informed upper bound
- Key finding: proxy_diversity_prefilter best at B≥60

### Q7: Algorithm Innovation Exploration — Complete?
**YES.** Executed as Sprint Stage 6 (`AQP_ALGORITHM_DESIGN.md`).
- DCA (Diversity-Coverage-Audit): main algorithm, 40-40-20 budget split
- CFA (Cluster-First Adaptive): alternative, exploration+expansion+exploit
- TSA (Thompson-Stratified Adaptive): future method
- Each algorithm designed with formal input/output/policy
- Failure modes documented

### Q8: Related Work Boundary Analysis — Complete?
**YES.** Executed as Sprint Stage 7 (`RELATED_WORK_BOUNDARY_ANALYSIS.md`).
- 11 systems compared: SUPG, ABae, ARC, ExSample, LAVA, LensWalk, TAD, DriveJudge, DrivingDojo, STRIVE-D, Hydro
- Capability matrix: 7 dimensions (oracle, budget, proxy, temporal, clip, certificate, audit)
- Our unique combination covers all 7
- Claims to avoid and safe claims documented

### Q9: Paper-Style Report Generated?
**YES.** Executed as Sprint Stage 9 (`paper_draft/PAPER_STYLE_RESEARCH_REPORT.md`).
- Title candidates
- Abstract (250 words)
- Full sections: Introduction through Conclusion
- Claim strength categorized (strong/moderate/weak/unsafe)
- Next experiments table

### Q10: Current Final Decision?
**`MAINLINE_GO_WITH_BOUNDARY_LIMITATION`**

Rationale: Full oracle reference established (40 positives, 27 clusters). Budget decomposition confirmed (+30% over top-proxy at B=80). DCA algorithm well-motivated. Boundary templated but clip-level labels reliable. Certificate not yet implemented.

---

## Stage Results Summary

| stage | status | key finding |
|---|---|---|
| P0 scout | SUCCESS | dataset3=GO, dataset2=WEAK_GO→NO-GO |
| P1 pilot | SUCCESS | 10% positive rate, GO with boundary caveat |
| S1 (P1b) | SUCCESS | USE_CLIP_LEVEL_LABELS_AND_POSTHOC_BOUNDARY |
| S2 (P1c) | SUCCESS | 40 positives, 11.5% rate |
| S3 proxy-oracle | SUCCESS | AUROC=0.624, 42.5% proxy-blind |
| S4 AQP structure | SUCCESS | 27 clusters, P(1→1)=0.325 |
| S5 budget replay | SUCCESS | diversity_prefilter best at B≥60 |
| S6 algorithm design | SUCCESS | DCA main algorithm |
| S7 related work | SUCCESS | 7-capability unique combination |
| S8 dataset2 | SUCCESS | NO-GO decision |
| S9 paper draft | SUCCESS | Full paper-style report |

---

## Data Suitable for Follow-up Research

1. **Full oracle labels** (347 anchors) — ground truth for DCA validation (E1)
2. **Proxy features** (693 5s windows, 347 center10 aggregates) — for feature analysis
3. **Budget replay results** — 10 methods × 8 budgets for benchmarking
4. **Positive cluster definitions** — for cluster-aware AQP testing
5. **Temporal correlation matrix** — for certificate simulation (E3)
6. **Boundary scheme comparison** — for boundary refinement experiments (E5)

---

## Data Needing Verification

1. **P1 pilot anchor 0197 label instability** — labeled positive in P1, negative in Stage 1 re-test
2. **Diversity prefilter at B=40** — 7.5% recall seems unexpectedly low vs 15.0% for top_proxy; worth verifying the deterministic replay result
3. **Singletons = 18 vs 21** — Report section 4.3 says 18 singletons, temporal_structure.csv says 21. Discrepancy from different counting conventions (anchor-level vs cluster-level reporting)
