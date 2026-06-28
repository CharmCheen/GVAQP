# Decision Log — CASQ / G-ClipAQP

All final decision strings extracted from reports and summaries. Status: `valid`, `partially_valid`, `superseded`, `needs_code_review`, `unknown`.

## V13 Series (Active Pipeline)

| # | Decision String | Source | Supporting Metrics | Status |
|---|---|---|---|---|
| 1 | `FINAL_DECISION: USE_10S_ANCHOR_CENTERED_FOR_COARSE_ORACLE` | V13.6 FINAL_REPORT.md | center_10s: 56% pos rate vs 44% fixed_5s, 0% abstain, 50% fewer calls | **valid** |
| 2 | `FINAL_DECISION: CENTER10_FULL_REFERENCE_RECOMMENDED` | V13.7 FINAL_REPORT.md | Proxy beats random by ≥0.10 on labeled subset (later found biased) | **superseded** (biased subset, but recommendation was correct — oracle was built) |
| 3 | `FULL_CENTER10_ORACLE_REFERENCE_READY` | V13.8 FINAL_REPORT.md | 399/399 calls, 94 positives, 51 events, 0% abstain | **valid** |
| 4 | `V13_9_DECISION: LATENCY_AWARE_AQP_FAIL` | V13.9 FINAL_REPORT.md | B=20: uniform beats proxy (0.137), delta +0.059 < 0.10 | **valid** (confirmed by V13.10) |
| 5 | `V13_10A_DECISION: STATIC_METHODS_FAR_BELOW_UPPER_BOUND` | V13.10 REPORT | Best eff 0.350 at B=20, 0.275 at B=40 | **valid** |
| 6 | `ADAPTIVE_SIMULATION_DECISION: ADAPTIVE_NO_BETTER` | V13.10 REPORT | Adaptive never beats static at any budget | **valid** |
| 7 | `ADAPTIVE_SENSITIVITY_DECISION: SAME_BASE_HURTS_CONSISTENTLY` | V13.10 REPORT | Adaptive hurts same-base static at 11/15 combos | **valid** |
| 8 | `MISMATCH_ROOT_CAUSE: V13_10_COMPARISON_BUG_NOT_SEMANTIC_DIFFERENCE` | V13.10_MISMATCH_ROOT_CAUSE.md | 93→18 mismatches after fix; zero deterministic mismatches remain | **valid** |
| 9 | `LOOP_FINAL_DECISION: V13_9_NEEDS_8B_OR_REPRESENTATION_CASCADE` | agent_loop_FINAL.md | Cheap proxy insufficient for budgeted AQP | **valid** |

## V13 Minimal Validation

| # | Decision String | Source | Supporting Metrics | Status |
|---|---|---|---|---|
| 10 | `STAGE_B_DECISION: FULL_VIDEO_CANDIDATE_FLAT` | V13 minimal validation | No candidate reaches 0.50 at ≤0.35 returned fraction | **valid** |
| 11 | `FINAL_DECISION: FULL_VIDEO_CANDIDATE_FLAT_TRY_REPRESENTATION_CANDIDATE` | V13 minimal validation | Cheap handcrafted candidates fail, representation unavailable | **valid** |

## V12.1 / Micro-CASQ

| # | Decision String | Source | Supporting Metrics | Status |
|---|---|---|---|---|
| 12 | `MICRO_CASQ_BENCHMARK_DECISION: READY_FOR_CANDIDATE_FEASIBILITY` | V12.1 completion | 38 eligible positives | **valid** (but underpowered) |
| 13 | `MICRO_CASQ_CANDIDATE_DECISION: CANDIDATE_READY_FOR_CERTIFICATE` | V12.1 completion | Candidate feasibility passed on sampled benchmark | **partially_valid** (sampled benchmark only) |
| 14 | `MICRO_CASQ_CERTIFICATE_DECISION: UNDERPOWERED` | V12.1 completion | Certification pool too small for non-vacuous certificate | **valid** |
| 15 | `V12_1_COMPLETION_DECISION: NO_CERTIFICATE_YET` | V12.1 completion | aggregate of above | **valid** |
| 16 | `MICRO_CASQ_PACKAGE_DECISION: READY_FOR_PILOT_ADJUDICATION` | micro_casq_adjudication_package_v0 | 500 selected, 50 pilot clips | **valid** (package exists, waiting for human) |
| 17 | `MICRO_CASQ_32B_ORACLE_DECISION: NEED_MORE_POSITIVES` | micro_casq_32b_oracle_v0 | Only 23 eligible positives | **valid** |

## Phase 1 — Nexar Pipeline

| # | Decision String | Source | Supporting Metrics | Status |
|---|---|---|---|---|
| 18 | `NEXAR_CANDIDATE_DECISION: CANDIDATE_STILL_TOO_WEAK (Nexar-200 only, derived boundary)` | nexar_candidate_v2 | Fixed/motion near-zero recall, random 0.49 at 50% fraction | **valid** |
| 19 | `NEXAR_200_DECISION: METHOD_STILL_TOO_VACUOUS` | nexar_200_v1 | True derived recall 0.06, median LCB 0.0 | **valid** |
| 20 | `DISENTANGLE_DECISION: CANDIDATE_QUALITY_IS_MAIN_BOTTLENECK` | nexar_200_disentangle_v1 | Candidate quality, not event definition | **valid** |
| 21 | `VIDEO_REPAIR_DECISION: READY_FOR_NEXAR_CANDIDATE_RERUN` | nexar_video_repair_v1 | 392/400 readable after repair | **valid** |
| 22 | `LOCAL_CANDIDATE_DECISION: PIPELINE_READY_FOR_NEXAR_VIDEO` | local_candidate_smoke_v1 | Pipeline validated locally | **valid** |
| 23 | `NEXAR_SMALL_DECISION: BOUNDARIES_ARE_DERIVED_ONLY` | nexar_small_v1 | No original annotations | **valid** |

## Phase 0

| # | Decision String | Source | Supporting Metrics | Status |
|---|---|---|---|---|
| 24 | `FINAL_DECISION: NO_GO` | PHASE0_REPORT.md | Pseudo-event analysis only | **superseded** (Phase 0 scope) |
| 25 | `REPAIR_DECISION: UNDERPOWERED_NO_CLEAN_GO_NO_GO` | repair_v1 | Bound defect fixed but still underpowered | **superseded** |
| 26 | `POWER_DECISION: EXPAND_BENCHMARK_TO_N_EVENTS` | power_v1 | ~500+ events needed for non-vacuous certificates | **valid** |

## Gate Experiments

| # | Decision String | Source | Status |
|---|---|---|---|
| 27 | `WEAK GO` (candidate_coverage_gate_v1) | candidate_coverage gate | **superseded** |
| 28 | `WEAK GO` (event_budget_gate_v2) | event_budget gate | **superseded** |
| 29 | `PARTIAL_GO` (nuscenes_event_aqp_feasibility) | nuscenes audit | **unknown** (not followed up) |

---

## Status Summary

| Status | Count |
|---|---|
| **valid** | 16 |
| partially_valid | 1 |
| superseded | 6 |
| unknown | 1 |
| needs_code_review | 0 |
