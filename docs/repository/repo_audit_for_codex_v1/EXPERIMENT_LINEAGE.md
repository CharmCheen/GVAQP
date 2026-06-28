# Experiment Lineage — CASQ / G-ClipAQP

## Chronological Dependency Chain

### Phase 0 (V11 protocol, synthetic/local data)

```
clip_aqp_phase0_v1
  ├── Inputs: local video clips, pseudo-events from merged oracle-positive units
  ├── Produced: SUPG stitch simulation, block audit (B1), oracle stability (C)
  ├── Decision: FINAL_DECISION: NO_GO
  │
  ├── repair_v1 (sub-experiment)
  │   ├── Fixed: UCB/LCB bound formula defect
  │   └── Decision: REPAIR_DECISION: UNDERPOWERED_NO_CLEAN_GO_NO_GO
  │
  └── power_v1 (sub-experiment)
      ├── Found: ~200 events may begin to help, ~500+ needed for non-vacuous
      └── Decision: POWER_DECISION: EXPAND_BENCHMARK_TO_N_EVENTS
```

**Superseded by:** All Phase 1+ work. Phase 0 used pseudo-events only — no real event boundaries.

---

### Phase 1 — External Data Pipeline (V12/V12.1 protocol)

```
clip_aqp_phase1_data_v1
  └── Prepared scaffolding for DoTA, DADA-2000, Nexar data conversion

clip_aqp_phase1_video_access_v1 → _auth_v1
  └── Attempted Nexar video download; blocked by HF auth
      Decision: NEED_HF_AUTH_OR_LICENSE

clip_aqp_phase1_nexar_small_v1
  ├── Inputs: 50 Nexar videos (small subset)
  └── Decision: BOUNDARIES_ARE_DERIVED_ONLY

clip_aqp_phase1_nexar_200_v1
  ├── Inputs: 200 Nexar positive + 200 negative videos
  ├── Produced: Derived-boundary CASQ benchmark
  └── Decision: METHOD_STILL_TOO_VACUOUS (true_derived_recall = 0.06)

clip_aqp_phase1_nexar_200_disentangle_v1
  └── Decision: CANDIDATE_QUALITY_IS_MAIN_BOTTLENECK

clip_aqp_phase1_nexar_video_repair_v1
  └── Repaired video readability; produced balanced readable subset (384 videos)

clip_aqp_phase1_nexar_candidate_v1 → v2
  ├── v1: VIDEO_MAPPING_OR_READABILITY_FAILED (76/400 readable)
  └── v2: CANDIDATE_STILL_TOO_WEAK (Nexar-200 only, derived boundary)
      ├── VLM micro-audit: UNRELIABLE (16% positive agreement)
      └── External label mapping: LOOSE_APPROXIMATION / AUDIT_UNRELIABLE
```

**Superseded by:** V13 realcartest pipeline. Nexar labels found unreliable for O_enter_ego_path_v0.

---

### Micro-CASQ / V12.1 Completion

```
micro_casq_32b_oracle_v0
  ├── Built 32B-oracle benchmark from candidate pools (kinematic_proxy, roadclip_budget_v2)
  ├── 23 eligible positives, 51 negatives
  └── Decision: NEED_MORE_POSITIVES

micro_casq_adjudication_package_v0
  ├── 500 selected, 50 pilot clips for human review
  └── Decision: READY_FOR_PILOT_ADJUDICATION

v12_1_completion_v1
  ├── Inputs: v0 benchmark + 99 expansion 32B calls
  ├── Produced: v1 benchmark (38 positives, 131 negatives)
  ├── Candidate feasibility: READY_FOR_CERTIFICATE
  ├── Certificate: UNDERPOWERED
  └── Decision: NO_CERTIFICATE_YET
```

**Status:** Sampled-benchmark signal only. Not full-video retrieval. Certificate underpowered.

---

### V13 Realcartest Pipeline (V13.5→V13.10)

```
V13.5 — Realcartest Oracle-Relative Validation (pilot)
  ├── Inputs: realcartest.mp4 (66.5 min)
  ├── 100 pilot VLM calls, 66% abstain (old prompt)
  └── Gate: PROCEED_FULL_ORACLE (but abstain too high)

V13.6 — Clip Construction Sensitivity
  ├── Inputs: V13.5 pilot labels + repaired prompt
  ├── 416 VLM calls (52 base clips × 8 construction policies)
  ├── center_10s beats fixed_5s: 56% vs 44% positive rate, halved calls
  ├── 0% abstain with repaired prompt
  └── Decision: USE_10S_ANCHOR_CENTERED_FOR_COARSE_ORACLE
      ↓ [V13.6 consumed by V13.7, V13.8]

V13.7 — Center10 Multi-Method Replay (no new VLM)
  ├── Inputs: V13.6 center_10s labels (52 clips, biased subset)
  ├── 17 methods × 8 budgets evaluated on labeled subset
  ├── Found: proxy methods beat random by ≥0.10 on labeled subset
  ├── Caveat: labeled subset biased (25% high-YOLO samples)
  └── Decision: CENTER10_FULL_REFERENCE_RECOMMENDED
      ↓ [V13.7 consumed by V13.8]

V13.8 — Full Center10 Oracle Reference
  ├── Inputs: V13.7 center10 anchor grid + V13.6 repaired prompt
  ├── 399 VLM calls (Qwen3-VL-32B), 74 min GPU
  ├── 94 positive anchors (23.6%), 51 stitched events, 0% abstain
  ├── 100% complete events, 0% truncation
  └── Decision: FULL_CENTER10_ORACLE_REFERENCE_READY
      ↓ [V13.8 consumed by V13.9, V13.10]

V13.9 — Latency-Aware AQP Simulation
  ├── Inputs: V13.8 full oracle labels + V13.7 proxy features
  ├── 19 methods × 5 budgets evaluated on full unbiased oracle
  ├── Best B=20: uniform (NOT proxy) at 0.137 event recall
  ├── Best B=40: top_fusion_geometry_motion at 0.216
  ├── Proxy delta vs random at B=20: only +0.059 (< 0.10 threshold)
  └── Decision: LATENCY_AWARE_AQP_FAIL
      ↓ [V13.9 consumed by V13.10]

V13.10 — Oracle Upper Bound + Adaptive Search
  ├── Inputs: V13.8 oracle + V13.7 proxies + V13.9 method definitions
  ├── OracleBest@B curve: B→min(B,51)/51 (simple, anchor-event 1:1)
  ├── Static methods far below upper bound: best eff 0.350 at B=20
  ├── 6 adaptive variants evaluated (3 bases × 2 mechanisms)
  ├── Adaptive never beats static at any budget
  ├── Window-width sweep (1,2,3): no width consistently best
  ├── Same-base comparison: adaptive hurts at 11/15 combos
  ├── V13.9 mismatch root cause: wrong field comparison (event_recall_iou_0p3 vs event_recall_overlap) + random union-across-seeds bug
  └── Decisions:
      V13_10A: STATIC_METHODS_FAR_BELOW_UPPER_BOUND
      ADAPTIVE_SIMULATION: ADAPTIVE_NO_BETTER
      ADAPTIVE_SENSITIVITY: SAME_BASE_HURTS_CONSISTENTLY
      MISMATCH_ROOT_CAUSE: V13_10_COMPARISON_BUG_NOT_SEMANTIC_DIFFERENCE
```

---

### Superseded Conclusions

| Earlier Conclusion | Later Evidence | Current Status |
|---|---|---|
| V13.7: "Proxy methods beat random by ≥0.10" | V13.9/V13.10: On unbiased full oracle, proxy delta at B=20 is +0.059 | **Superseded** — labeled subset was biased |
| V13.7: "CENTER10_FULL_REFERENCE_RECOMMENDED" | V13.8 successfully built the reference | **Completed** — recommendation was correct |
| V13.9: "Static methods evaluated on full oracle" | V13.10: event_recall definition reconciled, static numbers confirmed | **Validated** — numbers confirmed after bug fix |
| V13.5: "66% abstain rate" | V13.6: "Normal driving → negative" fixed to 0% | **Superseded** — prompt repaired |
| Phase 0: "GO" | Repair found UCB/LCB bound defect | **Superseded** by repair findings |
| Nexar-200: "Derived-boundary benchmark" | VLM micro-audit: UNRELIABLE | **Superseded** — labels unusable for O_enter_ego_path_v0 |
| V13.9 initial: "event_recall numbers" | V13.10: Comparison bug fixed, 93→18 mismatches | **Partially superseded** — numbers confirmed, field comparison fixed |

---

### Supporting Infrastructure (not in main lineage)

```
candidate_coverage_gate_v1 → event_budget_gate_v2
  └── Historical gate experiments, predate V12.1

kinematic_proxy / roadclip_budget_v2
  ├── Early candidate pool experiments
  ├── Fed into micro_casq benchmark construction
  └── Superseded by center10 pipeline

garc_eval/ (SUPG/ABAE reproduction)
  └── Separate research thread — frame-level selection/aggregation queries
  └── Not integrated with CASQ clip-level pipeline
```
