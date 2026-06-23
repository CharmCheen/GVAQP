# V13 Minimal Validation Report

**Brief used**: `CASQ_CODEX_BRIEF_V12_1.md` (read and enforced)
**Date**: 2026-06-23
**Output directory**: `test_vlm/outputs/v13_minimal_validation_v1`
**Protocol type**: Strict minimal validation — Phase 1+ full-video candidate smoke

---

## 1. Exact Commands Run

```bash
# Stage A: Inventory and claim-scope audit (manual inspection + CSV generation)
# Inspected files under: test_vlm/, garc_eval/, datasets/casq_external/, test_vlm/manifests/
# Produced: tables/artifact_inventory.csv, reports/ARTIFACT_AUDIT.md

# Stage B: Full-video candidate smoke evaluation
python3 test_vlm/outputs/v13_minimal_validation_v1/scripts/10_stage_b_full_video_candidate_smoke.py

# Stage C: Skipped (FULL_VIDEO_CANDIDATE_FLAT)
```

No models were trained. No large datasets were downloaded. No large-scale VLM was run. No prior experiment outputs were modified. No existing reports were overwritten.

## 2. Brief File Used

`/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md` — 1566 lines, Phase 1+ protocol sections (26-31) enforced.

## 3. Git Status Summary

Repository: `qiuyeqing/llama_prl/G-ARC`
Branch: `main`
Status: Clean at start of run. New files created under `test_vlm/outputs/v13_minimal_validation_v1/`. No existing files modified.

## 4. Artifact Inventory Summary

### Available Benchmarks

| Benchmark | Type | Videos | Events | Labels |
|---|---|---|---|---|
| Nexar-200 | Derived-boundary | 384 readable | 200 | External-label-derived (alert_time → event_moment) |
| Micro-CASQ v0 | Sampled | N/A (sampled pools) | 23 eligible | 32B-oracle-relative |
| Micro-CASQ v1 | Sampled | N/A (sampled pools) | 38 eligible | 32B-oracle-relative |

### Local Infrastructure

| Asset | Status |
|---|---|
| Nexar positive videos | 200 locally readable |
| Nexar negative videos | 403 locally readable |
| YOLOv8n model | Available at `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt` |
| YOLOv8x model | Available at `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt` |
| CLIP/SigLIP embeddings | **REPRESENTATION_CANDIDATE_NOT_AVAILABLE** |
| GPU (H20-3e) | Available for inference |
| GPU (A100-SXM4-80GB) | Used for prior 32B expansion; logged in v12.1 completion |

Full inventory: `tables/artifact_inventory.csv`
Detailed audit: `reports/ARTIFACT_AUDIT.md`

## 5. Benchmark / Label Provenance Table

| Label source | Provenance | Agreement with O_enter_ego_path_v0 | Classification |
|---|---|---|---|
| Nexar collision/alert | External-label-derived (alert_time → event_start, event_moment → event_end) | 0.16 positive agreement (UNRELIABLE) | DERIVED_BOUNDARY_ONLY |
| Micro-CASQ 32B-oracle v0 | 32B-VLM (Qwen3-VL-32B-Instruct) | Not evaluated against human gold | ORACLE_RELATIVE_ONLY |
| Micro-CASQ 32B-oracle v1 expansion | 32B-VLM (Qwen3-VL-32B-Instruct, 99 calls) | Not evaluated against human gold | ORACLE_RELATIVE_ONLY |
| VLM micro-audit (100 calls) | 32B-VLM (Qwen3-VL-32B-Instruct, H20-3e) | Used to validate Nexar → O_enter_ego_path_v0 mapping | ORACLE_RELATIVE_ONLY |
| Human-adjudicated labels | **NONE** | N/A | NOT_AVAILABLE |

**Critical finding**: Zero human-adjudicated event boundary labels exist in any current benchmark. All labels are either external-label-derived or 32B-oracle-relative.

## 6. Whether the Run Tests Full-Video Retrieval or Only Sampled Benchmark Signal

**This run tests full-video retrieval candidate generation.**

- Candidate windows were generated from complete video timelines (not pre-mined candidate pools).
- The evaluation uses Nexar-derived-boundary labels, which are LOOSE_APPROXIMATION for O_enter_ego_path_v0.
- The Micro-CASQ sampled benchmarks were NOT used for this Stage B test — they are sampled-benchmark-signal-only artifacts.

**Caveat**: All evaluation metrics are **Nexar-derived-boundary-relative**, not human-truth-relative and not O_enter_ego_path_v0 oracle-relative. The VLM micro-audit found only 16% positive agreement between Nexar labels and O_enter_ego_path_v0.

## 7. Full-Video Candidate Smoke Results

### Candidate Generators Tested on Heldout (192 videos, 96 events)

| Candidate | Best recall at ≤0.35 frac | Best recall at 0.50 frac | Runtime (384 videos) |
|---|---|---|---|
| fixed_sliding_window | 0.0000 | 0.0104 | 0.003s |
| random_window | **0.3229** | 0.4896 | 0.054s |
| motion_energy | 0.0000 | 0.0104 | 156.4s |
| yolo_count_proxy | NOT_RUN | NOT_RUN | N/A |
| representation_candidate | NOT_AVAILABLE | NOT_AVAILABLE | N/A |

### Hard Invariants

| Invariant | fixed_sliding_window | random_window | motion_energy |
|---|---|---|---|
| uses_oracle_for_generation == False | ✅ | ✅ | ✅ |
| uses_event_boundary_for_generation == False | ✅ | ✅ | ✅ |

All candidates pass. No leakage detected.

### Decision Rules

```text
FULL_VIDEO_CANDIDATE_STRONG_PASS: best_non_fixed_recall=0.3229 < 0.75 → NOT MET
FULL_VIDEO_CANDIDATE_PASS:      best_non_fixed_recall=0.3229 < 0.60 → NOT MET
FULL_VIDEO_CANDIDATE_FLAT:      best_non_fixed_recall=0.3229 < 0.50 → APPLIES
```

Full results: `tables/full_video_candidate_results.csv`
Per-video data: `tables/full_video_candidate_per_video.csv`
Detailed report: `reports/FULL_VIDEO_CANDIDATE_SMOKE_REPORT.md`

## 8. Certificate Stage Decision

```
CERTIFICATE_STAGE_SKIPPED_DUE_TO_WEAK_FULL_VIDEO_CANDIDATE
```

Stage C was not run because Stage B did not achieve FULL_VIDEO_CANDIDATE_PASS or FULL_VIDEO_CANDIDATE_STRONG_PASS. Certificate simulation would be meaningless when the best full-video candidate achieves only 32.3% recall at 35% returned duration (on Nexar-derived-boundary labels).

## 9. Caveats

1. **Labels are LOOSE_APPROXIMATION**: All evaluation uses Nexar-derived-boundary labels. The bounded VLM micro-audit found only 16% agreement with O_enter_ego_path_v0 (UNRELIABLE). Results must be interpreted as "Nexar-derived-boundary-relative recall," not oracle-relative or human-truth-relative recall.

2. **Single dataset scope**: All findings are Nexar-200 only. No second independently-sourced dataset (DoTA, DADA-2000) has been evaluated. Per Section 30, these results cannot be promoted to general claims.

3. **No representation-based candidate**: The failure of fixed_sliding_window and motion_energy is failure of cheap handcrafted candidates only, not failure of candidate generation in general. A representation-based candidate (CLIP/SigLIP) could potentially provide informative window scoring.

4. **No human-adjudicated labels exist**: Zero human-adjudicated event boundary labels are available. All claims must be qualified as derived-boundary-relative or oracle-relative.

5. **YOLO count proxy not run**: YOLOv8n is locally available but was not run due to CPU fallback issues in v2. If GPU-accelerated YOLO inference is possible, this candidate could be tested.

6. **No selectivity stratification available**: Nexar labels lack subtype/severity metadata. Pooled recall numbers may hide heterogeneous performance.

7. **Phase 0.6 power simulation**: ~500+ events were needed for consistently non-vacuous certificates. The heldout set has only 96 events, which is below both the 200-event threshold where improvement begins and the 500+ threshold for non-vacuous certificates.

## 10. Next Recommended Action

1. **Obtain a representation-based candidate**: Install a local CLIP or SigLIP package and compute embeddings for video windows. This is likely required for any useful full-video candidate generation.

2. **Build a small human-adjudicated benchmark**: Create a small (20-50 video) set with human-adjudicated O_enter_ego_path_v0 event boundaries. This is necessary before any human-truth-relative claim can be made.

3. **Debug YOLO GPU inference**: If YOLOv8n can be run on GPU, test whether YOLO object counts provide informative window scoring.

4. **Consider DoTA or DADA-2000**: A second independently-sourced dataset is needed before promoting Nexar-derived findings to general claims (per Section 30).

5. **Do NOT run certificate simulation** until full-video candidate recall is substantially higher. Certificate simulation is underpowered with only 96 events and provides no useful information when candidate recall is below 0.50.

6. **Do NOT claim full-video retrieval feasibility** based on current results. The evidence shows that cheap handcrafted candidates (fixed sliding window, motion energy) produce near-zero recall from full video timelines on Nexar-200.

---

## 11. Final Decision

```
FINAL_DECISION: FULL_VIDEO_CANDIDATE_FLAT_TRY_REPRESENTATION_CANDIDATE
```

**Rationale**: All cheap handcrafted full-video candidate generators (fixed_sliding_window, motion_energy) produce near-zero recall on Nexar-200 heldout videos. The random baseline achieves 32.3% at 35% duration fraction but does not constitute a useful candidate generator. No representation-based candidate is available. Certificate stage was skipped.

This is not FULL_VIDEO_CANDIDATE_FAIL because the pipeline, mapping, video access, and leakage invariants all pass. The failure is in candidate generator quality, not in infrastructure.

The next meaningful step is to add a representation-based candidate before drawing any conclusions about full-video candidate generation feasibility.
