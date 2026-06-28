# Artifact Inventory — CASQ / G-ClipAQP

## V12 / V12.1 (Protocol & Completion)

**Goal:** Enforce Phase 1+ external-data constraints; complete remaining V12.1 tasks.

| Item | Path | Status |
|---|---|---|
| Master protocol | `CASQ_CODEX_BRIEF_V12_1.md` (1566 lines) | governing |
| Historical protocol | `docs/clip_aqp/CASQ_CODEX_BRIEF_V11.md` (1009 lines) | superseded |
| Completion report | `test_vlm/outputs/v12_1_completion_v1/reports/V12_1_COMPLETION_FINAL_REPORT.md` | complete |
| V1 benchmark | `v12_1_completion_v1/benchmark/micro_casq_32b_oracle_v1_positive_events.csv` (39 rows) | available |
| Candidate feasibility | `v12_1_completion_v1/candidate_feasibility/reports/` | READY_FOR_CERTIFICATE |
| Certificate | `v12_1_completion_v1/certificate/reports/` | UNDERPOWERED |
| Final decision | `NO_CERTIFICATE_YET` | valid |

---

## V13 Minimal Validation

**Goal:** Strict minimal validation — full-video candidate smoke on Nexar-200.

| Item | Path | Status |
|---|---|---|
| Artifact audit | `v13_minimal_validation_v1/reports/ARTIFACT_AUDIT.md` | complete |
| Candidate smoke | `v13_minimal_validation_v1/reports/FULL_VIDEO_CANDIDATE_SMOKE_REPORT.md` | complete |
| Final report | `v13_minimal_validation_v1/reports/V13_MINIMAL_VALIDATION_REPORT.md` | complete |
| Tables | `v13_minimal_validation_v1/tables/` (4 CSV) | available |
| Decision | `FULL_VIDEO_CANDIDATE_FLAT_TRY_REPRESENTATION_CANDIDATE` | valid |

---

## V13.5 — Realcartest Oracle-Relative Validation (Pilot)

**Goal:** Determine whether realcartest.mp4 contains enough O_enter_ego_path_v0 positives.

| Item | Path | Status |
|---|---|---|
| Protocol | `docs/clip_aqp/REALCARTEST_ORACLE_RELATIVE_VALIDATION_V13_5.md` | governing |
| Preflight | `v13_5.../tables/coarse_5s_clip_grid.csv` (798 clips) | available |
| Proxy features | `v13_5.../tables/proxy_features_5s.csv` (798 rows) | available |
| Pilot sample | `v13_5.../tables/vlm_pilot_sample_100.csv` (100 rows) | available |
| Pilot labels | `v13_5.../tables/vlm_pilot_labels.csv` (100 rows) | available |
| Raw responses | `v13_5.../raw_vlm_responses/pilot/` (100 JSON) | available |
| Pilot result | 18% positive, 66% abstain (old prompt) | superseded by V13.6 |

---

## V13.6 — Clip Construction Sensitivity

**Goal:** Compare clip construction policies (fixed_5s vs center_*s).

| Item | Path | Status |
|---|---|---|
| Protocol doc | `v13_6.../reports/PROMPT_CONTRACT_V13_6.md` | complete |
| Sample table | `v13_6.../tables/clip_construction_samples.csv` (416 rows) | available |
| VLM labels | `v13_6.../tables/clip_construction_vlm_labels.csv` (416 rows) | available |
| Policy summary | `v13_6.../tables/clip_construction_policy_summary.csv` (8 rows) | available |
| Pairwise comparison | `v13_6.../tables/clip_construction_pairwise_comparison.csv` (7 rows) | available |
| Call cost estimates | `v13_6.../tables/full_video_call_cost_estimates.csv` (14 rows) | available |
| Anchor-expand dry run | `v13_6.../tables/anchor_expand_dry_run.csv` (15 rows) | available |
| Final report | `v13_6.../reports/FINAL_REPORT.md` | complete |
| Raw responses | `v13_6.../raw_vlm_responses/` (416 JSON) | available |
| Decision | `USE_10S_ANCHOR_CENTERED_FOR_COARSE_ORACLE` | **valid** |
| Scripts | `v13_6.../scripts/` (5 Python) | runnable |

---

## V13.7 — Center10 Multi-Method Replay

**Goal:** No-new-VLM replay comparing 17 anchor selection methods on V13.6 labeled subset.

| Item | Path | Status |
|---|---|---|
| Protocol | `docs/clip_aqp/CENTER10_MULTI_METHOD_REPLAY_V13_7.md` | governing |
| Anchor grid | `v13_7.../tables/center10_anchor_grid.csv` (399 anchors) | available |
| Proxy features | `v13_7.../tables/center10_proxy_features.csv` (399 rows, 19 features) | available |
| Labeled subset | `v13_7.../tables/center10_labeled_eval_subset.csv` (52 clips) | BIASED |
| Budget results | `v13_7.../tables/method_budget_results.csv` (136 rows) | available (labeled subset) |
| Pipeline comparison | `v13_7.../tables/fixed5_vs_center10_comparison.csv` (10 rows) | available |
| Final report | `v13_7.../reports/FINAL_REPORT.md` | complete |
| Reuse audit | `v13_7.../reports/OLD_PIPELINE_REUSE_AUDIT.md` | REUSE_WITH_ADAPTER |
| Decision | `CENTER10_FULL_REFERENCE_RECOMMENDED` | **superseded** (biased data, but recommendation was correct) |

---

## V13.8 — Full Center10 Oracle Reference

**Goal:** Run Qwen3-VL-32B on all 399 center10 anchors.

| Item | Path | Status |
|---|---|---|
| Oracle labels | `v13_8.../tables/center10_full_oracle_labels.csv` (399 rows) | **available** |
| Stitched events | `v13_8.../tables/center10_vlm_oracle_events.csv` (51 events) | **available** |
| Stitching trace | `v13_8.../tables/center10_event_stitching_trace.csv` (51 rows) | **available** |
| Raw responses | `v13_8.../raw_vlm_responses/` (399 JSON) | **available** |
| Final report | `v13_8.../reports/FINAL_REPORT.md` | complete |
| Scripts | `v13_8.../scripts/` (2 Python) | runnable |
| Decision | `FULL_CENTER10_ORACLE_REFERENCE_READY` | **valid** |

---

## V13.9 — Latency-Aware AQP Simulation

**Goal:** Evaluate budgeted query plans on full V13.8 oracle.

| Item | Path | Status |
|---|---|---|
| Budget results | `v13_9.../tables/method_budget_results.csv` (95 rows) | available |
| Selected anchors | `v13_9.../tables/method_selected_anchors.csv` (2869 rows) | available |
| Event hit trace | `v13_9.../tables/event_hit_trace.csv` (77 rows) | available |
| Random seed summary | `v13_9.../tables/random_seed_summary.csv` (5 rows) | available |
| Best methods | `v13_9.../tables/best_methods_by_budget.csv` (5 rows) | available |
| Final report | `v13_9.../reports/FINAL_REPORT.md` | complete |
| Script | `v13_9.../scripts/run_aqp_simulation.py` | runnable |
| Decision | `LATENCY_AWARE_AQP_FAIL` | **valid** (confirmed by V13.10) |

---

## V13.10 — Oracle Upper Bound + Adaptive Search

**Goal:** Compute OracleBest@B curve; evaluate adaptive search mechanisms.

| Item | Path | Status |
|---|---|---|
| Oracle upper bound | `v13_10/tables/oracle_upper_bound_v13_10.csv` (51 rows) | available |
| Static efficiency | `v13_10/tables/static_methods_efficiency_v13_10.csv` (95 rows) | available |
| Adaptive simulation | `v13_10/tables/adaptive_simulation_v13_10.csv` (30 rows) | available |
| Combined comparison | `v13_10/tables/combined_comparison_v13_10.csv` (125 rows) | available |
| Same-base comparison | `v13_10/tables/same_base_comparison_v13_10.csv` (15 rows) | available |
| Window sensitivity | `v13_10/tables/window_sensitivity_v13_10.csv` (45 rows) | available |
| Mismatch root cause | `v13_10/reports/V13_10_MISMATCH_ROOT_CAUSE.md` | complete |
| Main report | `v13_10/reports/V13_10_REPORT.md` | complete |
| Scripts | `v13_10/scripts/` (4 Python) | runnable |
| Decisions | STATIC_METHODS_FAR_BELOW_UPPER_BOUND, ADAPTIVE_NO_BETTER, SAME_BASE_HURTS_CONSISTENTLY | **valid** |

---

## Other Experiments (Historical / Supporting)

### Micro-CASQ Adjudication
| Item | Path | Status |
|---|---|---|
| Package report | `micro_casq_adjudication_package_v0/reports/MICRO_CASQ_ADJUDICATION_PACKAGE_V0_REPORT.md` | READY_FOR_PILOT |
| Review package | `micro_casq_adjudication_package_v0/review_package/` (50 pilot clips) | available |
| Decision | `READY_FOR_PILOT_ADJUDICATION` | **valid** |

### Nexar Candidate Feasibility v2
| Item | Path | Status |
|---|---|---|
| Report | `nexar_candidate_v2/reports/NEXAR_CANDIDATE_FEASIBILITY_REPORT_V2.md` | complete |
| VLM micro-audit | `nexar_candidate_v2/reports/VLM_MICRO_AUDIT_REPORT.md` | UNRELIABLE |
| External label mapping | `nexar_candidate_v2/reports/EXTERNAL_LABEL_MAPPING.md` | LOOSE_APPROXIMATION |
| Decision | `CANDIDATE_STILL_TOO_WEAK` | **valid** |

### Phase 0
| Item | Path | Status |
|---|---|---|
| Report | `clip_aqp_phase0_v1/reports/PHASE0_REPORT.md` | NO_GO |
| Repair report | `clip_aqp_phase0_v1/repair_v1/reports/PHASE0_REPORT_v2.md` | UNDERPOWERED |
| Power report | `clip_aqp_phase0_v1/power_v1/reports/POWER_REPORT.md` | NEED_500_EVENTS |

### Candidate Coverage / Event Budget Gates
| Item | Path | Status |
|---|---|---|
| Coverage gate | `candidate_coverage_gate_v1/reports/FINAL_CANDIDATE_COVERAGE_GATE_REPORT.md` | WEAK_GO (superseded) |
| Event budget gate | `event_budget_gate_v2/reports/FINAL_EVENT_BUDGET_GATE_REPORT.md` | WEAK_GO (superseded) |

### Kinematic Proxy / RoadClip (early candidate pools)
| Item | Path | Status |
|---|---|---|
| Kinematic proxy reports | `kinematic_proxy/` (20+ .md reports) | BLOCKED (learned anomaly proxy) |
| RoadClip budget reports | `roadclip_budget_v2/` (11 .md reports) | available, fed micro-casq |

### G-ARC Evaluation (SUPG/ABAE)
| Item | Path | Status |
|---|---|---|
| Reproduction matrix | `garc_eval/outputs/paper_reproduction_matrix.md` | complete |
| Retrospective | `garc_eval/outputs/garc_research_retrospective.md` | complete |
| Synthetic reproduction | `garc_eval/outputs/supg_paper_synthetic_reproduction/` | complete |
| Real-frame (BDD100K, KITTI, UA-DETRAC) | Multiple subdirectories | complete |
| ABAE reproduction | `garc_eval/outputs/abae_paper_synthetic_reproduction/` | complete |
| AQP-related (collapse, temporal, oracle allocation) | Multiple reports | complete |
