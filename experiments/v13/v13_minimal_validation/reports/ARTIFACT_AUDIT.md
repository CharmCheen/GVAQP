# Artifact Audit: V13 Minimal Validation Stage A

**Brief used**: `CASQ_CODEX_BRIEF_V12_1.md`
**Date**: 2026-06-23
**Output directory**: `test_vlm/outputs/v13_minimal_validation_v1`

## 1. Which Benchmark Artifacts Are Available?

### 1.1 Nexar-200 Derived-Boundary Benchmark

The primary Phase 1+ benchmark is Nexar-200, constructed from:

| Component | Path | Rows |
|---|---|---|
| Manifest | `.../clip_aqp_phase1_nexar_200_v1/manifests/nexar_200_manifest.csv` | 400 |
| Events | `.../clip_aqp_phase1_nexar_200_v1/converted/casq_events_nexar_200.csv` | 200 |
| Units | `.../clip_aqp_phase1_nexar_200_v1/converted/casq_units_nexar_200.csv` | 4401 |
| Video readability | `.../nexar_video_repair_v1/tables/post_download_manifest_readability.csv` | 400 |

**Local videos**:
- 200 positive videos: `datasets/casq_external/nexar/videos_hf/train/positive/`
- 403 negative videos: `datasets/casq_external/nexar/videos_hf/train/negative/`
- Balanced readable subset: 384 videos (200 positive + 192 normal)

### 1.2 Micro-CASQ 32B-Oracle v1 Benchmark (Sampled)

| Component | Path |
|---|---|
| Benchmark | `v12_1_completion_v1/benchmark/micro_casq_32b_oracle_v1_benchmark.csv` |
| Positive events | `v12_1_completion_v1/benchmark/micro_casq_32b_oracle_v1_positive_events.csv` |
| Split | `v12_1_completion_v1/benchmark/micro_casq_32b_oracle_v1_split.csv` |

This benchmark was **sampled from prior candidate pools** (kinematic_proxy, roadclip_budget_v2). It is NOT a full-video retrieval benchmark. Eligible: 38 positives, 131 negatives.

### 1.3 Candidate Feasibility v2 (Nexar-200, Full-Video Candidate Generation)

| Component | Path |
|---|---|
| Eval results (325 rows) | `nexar_candidate_v2/tables/nexar_candidate_eval_results_v2.csv` |
| Video split (385 rows) | `nexar_candidate_v2/tables/nexar_candidate_video_split_v2.csv` |
| Balanced readable | `nexar_candidate_v2/tables/nexar_candidate_subset_balanced_readable.csv` |
| Raw windows (fixed) | `nexar_candidate_v2/candidates/fixed_sliding_window_raw_windows_v2.csv` |
| Raw windows (motion) | `nexar_candidate_v2/candidates/motion_energy_raw_windows_v2.csv` |
| Raw windows (random) | `nexar_candidate_v2/candidates/random_window_raw_windows_v2.csv` |
| Certificate results | `nexar_candidate_v2/tables/nexar_candidate_certificate_results_v2.csv` |
| Block audit rows | `nexar_candidate_v2/tables/nexar_candidate_certificate_block_rows_v2.csv` |

### 1.4 VLM Bounded Micro-Audit (Imported from v1)

| Component | Path |
|---|---|
| Results (100 calls) | `nexar_candidate_v2/audits/vlm_micro_audit_results.csv` |
| Samples | `nexar_candidate_v2/audits/vlm_micro_audit_samples.csv` |

### 1.5 Phase 0 Reports (Historical Only)

- `clip_aqp_phase0_v1/reports/PHASE0_REPORT.md` (GO decision)
- `clip_aqp_phase0_v1/repair_v1/reports/PHASE0_REPORT_v2.md` (PARTIAL_GO)
- Synthetic data only; not applicable to Phase 1+ claims.

## 2. Which Labels Are Human-Adjudicated, 32B-Oracle-Relative, External-Label-Derived, or Pseudo Labels?

| Label source | Classification | Evidence |
|---|---|---|
| Nexar collision/alert metadata | **External-label-derived** | Derived from `alert_time` and `event_moment` in Nexar dataset metadata. No human event boundary adjudication. |
| Micro-CASQ 32B-oracle v0 labels | **32B-oracle-relative** | Qwen3-VL-32B-Instruct on NVIDIA A100-SXM4-80GB. Sampled from prior candidate pools, not full-video. |
| Micro-CASQ 32B-oracle v1 expansion labels | **32B-oracle-relative** | 99 expansion calls on NVIDIA A100-SXM4-80GB. |
| VLM micro-audit labels (Nexar) | **32B-oracle-relative** | 100 bounded calls using Qwen3-VL-32B-Instruct on NVIDIA H20-3e. |
| Human-adjudicated labels | **None available** | No human-adjudicated event boundary labels exist in any current benchmark. |
| Pseudo labels (Phase 0) | **Pseudo labels** | Synthetic/merged-adjacent-oracle-positive units; Phase 0 only. |

### Label Quality Assessment

The bounded VLM micro-audit (100 calls, Qwen3-VL-32B-Instruct) found:
- **Positive agreement with O_enter_ego_path_v0**: 0.160 (16%)
- **Random-negative estimated miss rate**: 0.020 (2%)
- **Abstain rate**: 0.000
- **EXTERNAL_LABEL_AUDIT_RESULT**: UNRELIABLE

**Conclusion**: Nexar-derived labels do NOT reliably match O_enter_ego_path_v0. All certificate/recall numbers using Nexar labels are **Nexar-derived-boundary-relative**, not oracle-relative and not human-truth-relative.

## 3. Which Data Can Support Full-Video Candidate Generation?

**The Nexar-200 balanced readable subset (384 videos)** can support full-video candidate generation:
- All 384 videos are locally readable (confirmed by `post_download_manifest_readability.csv` and v2 video repair).
- Fixed_sliding_window and motion_energy candidates were generated from complete video timelines in the v2 run.
- Candidate generation did NOT use event_start, event_end, event_moment, alert_time, label, or boundary fields.
- This is sufficient for the FULL_VIDEO_RETRIEVAL_CLAIM_ALLOWED classification.

**The Micro-CASQ v1 benchmark cannot** support full-video candidate generation:
- Candidates were sampled from prior candidate pools (kinematic_proxy, roadclip_budget_v2).
- This is NOT full-video retrieval — it is mined-pool / sampled-benchmark testing.

## 4. Which Data Only Supports Mined-Pool / Sampled-Benchmark Candidate-Signal Testing?

| Artifact | Type | Evidence |
|---|---|---|
| Micro-CASQ v0 benchmark (23 positives) | Sampled benchmark | Candidates sourced from kinematic_proxy and roadclip_budget_v2 candidate pools |
| Micro-CASQ v1 benchmark (38 positives) | Sampled benchmark | Expanded from v0 using targeted expansion; not full-video |
| V12.1 candidate feasibility results | Sampled benchmark signal | Candidate feasibility test on Micro-CASQ v1 sampled benchmark |
| V12.1 certificate trials | Sampled benchmark signal | UNDERPOWERED; certification pool too small |

## 5. Which Prior Result, If Any, Used V12.1 Rather Than V11?

| Run | Brief used | Evidence |
|---|---|---|
| **Nexar Candidate Feasibility v2** | **V12.1** | Report explicitly states: "Authority: CASQ_CODEX_BRIEF_V12_1.md, especially Sections 23 and 26-31." |
| **V12.1 Completion v1** | **V12.1** | Report explicitly states: "Protocol Path: CASQ_CODEX_BRIEF_V12_1.md" |
| Phase 0 v1 (repair_v1) | V11 | Uses Phase 0 report template and GO/NO_GO/PARTIAL_GO decisions |
| Phase 0 original | V11 | Historical Phase 0 run |
| Candidate coverage gate v1 | V11 (likely) | Predates V12 |
| Event budget gate v2 | V11 (likely) | Predates V12 |
| Micro-CASQ v0 | V11 (likely) | Original Micro-CASQ construction |

**Key finding**: The V12.1 brief was used for Nexar Candidate Feasibility v2 and V12.1 Completion v1. Earlier runs used V11.

## 6. Are There Any Signs That Candidate Pools Were Mined Using Earlier Proxy Scores?

**Yes, for the Micro-CASQ benchmarks**:

- Micro-CASQ v0 candidates are explicitly sourced from `kinematic_proxy` and `roadclip_budget_v2` candidate pools.
- The v0 benchmark construction report (`micro_casq_v0_yield_by_candidate_source.csv`) traces candidates to their source proxy pools.
- Micro-CASQ v1 expansion used targeted selection from the v0 pool + new expansion samples.

**No, for the Nexar-200 v2 candidate feasibility run**:

- Nexar-200 v2 candidates were generated from full video timelines using `fixed_sliding_window`, `motion_energy`, and `random_window`.
- The v2 report explicitly states: "Candidate generation did not use event_start, event_end, event_moment, alert_time, or derived boundary fields."
- No prior proxy pools were used for candidate generation in v2.

## 7. Claim-Scope Classification of Every Candidate Claim

| Artifact | Classification | Justification |
|---|---|---|
| Nexar-200 v2: fixed_sliding_window windows | **FULL_VIDEO_RETRIEVAL_CLAIM_ALLOWED** | Generated from full video timelines; deterministic 10s windows, 5s stride; no oracle/label/boundary access during generation |
| Nexar-200 v2: random_window windows | **FULL_VIDEO_RETRIEVAL_CLAIM_ALLOWED** | Generated from full video timelines; random selection from grid; fixed seed; no oracle/label/boundary access |
| Nexar-200 v2: motion_energy windows | **FULL_VIDEO_RETRIEVAL_CLAIM_ALLOWED** | Motion energy computed from frame differences over full video; no oracle/label/boundary access |
| Nexar-200 v2: yolo_count_proxy | **NOT_USABLE_FOR_CLAIM** | NOT_RUN_CPU_FALLBACK_INFEASIBLE; YOLOv8n model available but not run on GPU due to fallback issue |
| Nexar-200 v2: eval results | **SAMPLED_BENCHMARK_SIGNAL_ONLY** | FULL_VIDEO candidate generation but evaluated against Nexar-derived-boundary labels; heldout split used |
| Nexar-200 v2: certificate simulation | **SAMPLED_BENCHMARK_SIGNAL_ONLY** | Certificate simulation used Nexar-derived-boundary labels; under the HELD_OUT_REPORT split |
| Nexar-200 events/labels | **DERIVED_BOUNDARY_ONLY** | Event boundaries derived from alert_time → event_moment; no human-adjudicated boundaries |
| Micro-CASQ v0/v1 benchmark | **SAMPLED_BENCHMARK_SIGNAL_ONLY** | Candidates sampled from prior candidate pools (kinematic_proxy, roadclip_budget_v2); not full-video retrieval |
| Micro-CASQ v0/v1 labels | **ORACLE_RELATIVE_ONLY** | 32B-VLM labels; no human adjudication |
| VLM micro-audit (Nexar) | **ORACLE_RELATIVE_ONLY** | 32B-VLM labels (100 bounded calls); used for external-label validation |
| Phase 0 reports | **NOT_USABLE_FOR_CLAIM** | Synthetic data only; Phase 0 scope |
| Candidate coverage gate | **NOT_USABLE_FOR_CLAIM** | Historical; predates V12.1 |
| Event budget gate | **NOT_USABLE_FOR_CLAIM** | Historical; predates V12.1 |

## 8. Summary

### Available for Full-Video Candidate Testing
- Nexar-200: 384 balanced readable videos with derived-boundary labels
- Three candidate generators run from full timelines: fixed_sliding_window, random_window, motion_energy
- YOLO count proxy: NOT_RUN
- Representation-based candidate: REPRESENTATION_CANDIDATE_NOT_AVAILABLE

### Available Only for Sampled-Benchmark Testing
- Micro-CASQ v0: 23 eligible 32B-oracle positives
- Micro-CASQ v1: 38 eligible 32B-oracle positives
- All certificate simulations on Micro-CASQ

### Critical Gap
- **No human-adjudicated event boundary labels exist anywhere.**
- **Nexar labels are LOOSE_APPROXIMATION / AUDIT_UNRELIABLE for O_enter_ego_path_v0.**
- **All certificate simulations are either underpowered or use derived-boundary labels.**
