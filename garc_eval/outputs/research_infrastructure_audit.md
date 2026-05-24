# G-ARC Research Infrastructure Audit

Generated: 2026-05-22

---

## Executive Summary

G-ARC is a research project attempting to extend SUPG-style statistical guarantees from frame-level selection to clip-level video retrieval. The repository has **completed a solid frame-level SUPG pipeline** on real data (BDD100K), but is **nowhere near clip-level retrieval capability**. The project's strongest current asset is a working real-frame SUPG pipeline with 100-trial formal experiments on BDD100K. Its weakest point is the total absence of temporal video data, clip-level evaluation, and any mechanism for G-ARC's core contribution (guaranteed clip retrieval).

**Overall maturity: 25-30% toward a publishable paper.**

The project can honestly claim:
- Synthetic SUPG/ABae reproduction: DONE
- Real-frame SUPG on images: DONE (BDD100K, 10K images)
- Real-frame ABae on images: DONE (BDD100K, 100 trials)
- Temporal video pipeline: NOT STARTED
- Clip-level retrieval: NOT IMPLEMENTED
- G-ARC guarantee mechanism: CONCEPTUAL ONLY
- Publishable experiments: NOT READY

---

## A. Pipeline Completeness

### A.1 What Exists and Works

| Stage | Status | Quality |
|-------|--------|---------|
| Frame extraction from video | IMPLEMENTED | Basic cv2 extractor, works |
| Proxy inference (YOLOv8n) | IMPLEMENTED | Real model, batched, works |
| Oracle inference (YOLOv8x) | IMPLEMENTED | Real model as pseudo-oracle |
| Caching/materialization | IMPLEMENTED | Parquet-based, works |
| Frame table building | IMPLEMENTED | Schema-validated, works |
| Count threshold calibration | IMPLEMENTED | Works for count_at_least |
| SUPG adapter (RT/PT) | IMPLEMENTED | Wraps refe_repos/supg cleanly |
| ABae adapter (AVG/COUNT) | IMPLEMENTED | Custom implementation, not using refe_repos/abae |
| Selection metrics | IMPLEMENTED | Frame-level precision/recall |
| Guarantee metrics | IMPLEMENTED | Frame-level failure rate |
| Aggregation metrics | IMPLEMENTED | Error, CI width, coverage |
| Clip metrics | IMPLEMENTED | IoU, clip recall/precision, mIoU, GVR |
| Experiment runner | IMPLEMENTED | CLI-based, CSV/JSON output |
| Config system | IMPLEMENTED | YAML-based, env var resolution |
| Proxy score ablation | IMPLEMENTED | 6 rules tested |
| Boxplot generation | IMPLEMENTED | matplotlib-based |

### A.2 What Is Missing or Fragile

| Stage | Status | Issue |
|-------|--------|-------|
| **Video temporal continuity** | MISSING | BDD100K is images, not video. No temporal ordering exists. |
| **GT clip generation** | MISSING | No code generates ground-truth clips from continuous video. |
| **Clip-level oracle** | MISSING | Oracle is frame-level only. No clip-level predicate evaluation. |
| **Candidate clip generation from SUPG** | MISSING | No code merges SUPG-selected frames into candidate clips for real data. |
| **Clip-level SUPG integration** | MISSING | No code runs SUPG with clip-level evaluation on real temporal data. |
| **G-ARC guarantee mechanism** | CONCEPTUAL ONLY | The report describes boundary adjustment and stratified allocation, but zero code exists. |
| **Temporal dependence handling** | CONCEPTUAL ONLY | No cluster-aware blocking, no block bootstrap, no temporal CI correction. |
| **IoU-aware oracle allocation** | CONCEPTUAL ONLY | No code allocates oracle budget based on clip boundary uncertainty. |
| **Config for clip experiments** | MISSING | All configs are frame-level. No clip-level experiment config exists. |
| **Experiment orchestration** | FRAGILE | Scripts use hardcoded paths, no Makefile or proper orchestration. |
| **Reproducibility** | PARTIAL | Seeds are used but no lockfile, no docker, no environment spec. |
| **Logging** | MISSING | No structured logging. Print statements only. |

### A.3 Fake/Simulated Components Still Remaining

1. **ABae adapter**: The `abae_adapter.py` is a **custom re-implementation**, not a wrapper around `refe_repos/abae`. The report notes "refe_repos/abae not found; implementation based on paper description only." This means ABae reproduction is **paper-description-based, not code-faithful**.

2. **Pseudo-oracle**: YOLOv8x is used as "oracle" but it is not ground truth. The failure_rate metric measures proxy-oracle consistency, not true accuracy. This is acknowledged but not resolved.

3. **Clip metrics are untested on real data**: `clip_metrics.py` exists and has unit tests (`test_clip_metrics.py`), but it has never been run on actual temporal video data. It was only tested on synthetic/mock data.

4. **SUPG-RT+ / SUPG-PT+ baselines**: The `garc_eval/baselines/` directory has `u_noci.py` and `u_ci.py`, but the clip-level baselines (`supg_rt_plus.py`, `supg_pt_plus.py`, `arc_simplified.py`, `abae_clip_stress.py`) mentioned in the build plan are **not implemented**.

### A.4 Places Still Assuming IID/Static CSV Settings

1. **`run_supg_real_frames.py`**: Takes a flat CSV with `(id, label, proxy_score)`. No video_id, no timestamp, no temporal ordering. This is the **core experiment runner** and it treats data as independent records.

2. **SUPG adapter**: `supg_adapter.py` passes data to SUPG as a flat DataFrame. SUPG internally assumes i.i.d. records. No temporal awareness.

3. **ABae adapter**: Stratification is by proxy_score quantile. No temporal stratification. No cluster-aware sampling.

4. **All experiment outputs**: Every result CSV has `method, qtype, seed, precision, recall, selected_n`. No clip-level columns exist in any output.

---

## B. Benchmark Validity

### B.1 Current Datasets

| Dataset | N | Type | Temporal? | SUPG-RT Vacuous? | Publishable? |
|---------|---|------|-----------|------------------|--------------|
| KITTI 0005 | 154 | Image sequence | Pseudo (ordered) | Yes (selects all) | No |
| KITTI combined | 1,176 | Image sequences | Pseudo (ordered) | Yes (selects all) | No |
| BDD100K val | 10,000 | Individual images | **No** | **No** (0.542) | Partial (frame-level only) |
| DRIV100 | 0 | Not available | N/A | N/A | No |
| Synthetic Beta | 1M | Generated | No | No | Yes (for SUPG paper reproduction) |

### B.2 Why KITTI Degenerates

Root cause analysis (confirmed by proxy ablation):

1. **N=1176 is too small**: With budget=117, SUPG's importance sampling cannot distinguish enough threshold candidates.
2. **Proxy score discretization**: `count_ratio` with K=15 produces only 16 unique scores. Even continuous rules (conf_sum_ratio, etc.) with 1102 unique scores did not fix the problem.
3. **Conservative RT threshold**: SUPG-RT's Hoeffding-based CI is too wide for small N, causing it to select all records to guarantee recall.
4. **High positive rate (13.78%)**: Combined with small N, the budget-to-positives ratio is too high for meaningful selection.

The ablation tested 6 proxy score rules. **None** made SUPG-RT non-vacuous. The problem is fundamental: N is too small.

### B.3 Why BDD100K Works for Frame-Level SUPG

- N=10,000 gives enough statistical power.
- 9,287 unique proxy scores give fine-grained threshold resolution.
- 9.92% positive rate is in the sweet spot.
- Budget=1,000 (10% ratio) creates meaningful selection pressure.
- **Result**: SUPG-RT selects 54% of data with 97.7% recall. Non-vacuous.

### B.4 BDD100K's Fatal Limitation

**BDD100K is an image dataset, not video.** The 10,000 images come from different driving clips with no temporal continuity between them. This means:

- No temporal ordering between frames (images from different video clips).
- No meaningful clip-level events to evaluate.
- Cannot compute temporal IoU, clip recall, or GVR on real data.
- Frame labels are independent, not part of temporal sequences.

The project's own protocol document (`garc_experiment_protocol.md`) explicitly states: "BDD100K is an image-level benchmark. Clip-level evaluation requires continuous video with temporal ground-truth events."

### B.5 Properties a Valid Benchmark Should Satisfy

For a publishable G-ARC benchmark:

| Property | Requirement | Current Status |
|----------|-------------|----------------|
| N (sampled frames) | >= 10,000 | BDD100K: YES. Video: NOT AVAILABLE |
| Positive frame rate | 1%-20% | BDD100K: 9.92%. Video: UNKNOWN |
| Continuous timestamps | Required | BDD100K: NO. Video: NOT AVAILABLE |
| GT clips | >= 10 temporal events | BDD100K: N/A. Video: NOT AVAILABLE |
| Proxy/oracle pair | YOLOv8n/YOLOv8x or equivalent | YES (implemented) |
| Traffic/road scenes | Preferred | BDD100K: YES |
| Non-vacuous SUPG-RT | Required | BDD100K: YES. Video: UNKNOWN |
| Temporal continuity | Required for clip eval | BDD100K: NO |

### B.6 What Prevents Meaningful RT Evaluation at Clip Level

The exact missing workload characteristics:

1. **No continuous video data**: The project has never processed a single continuous video through the pipeline. All "video" work was on individual image sequences (KITTI) or standalone images (BDD100K).

2. **No ground-truth temporal clips**: No code exists to define, generate, or evaluate ground-truth clips from continuous video. The `frame_labels_to_clips()` function in `clip_metrics.py` can convert frame labels to clips, but it has never been fed real temporal data.

3. **No frame-to-clip merge pipeline**: The build plan describes SUPG-RT+ (run SUPG on frames, merge selected frames into candidate clips, evaluate clip metrics), but this pipeline is not implemented for real data.

4. **No temporal proxy score**: Current proxy scores are per-frame YOLO confidences. No temporal aggregation or smoothing exists. In real video, proxy reliability varies over time (e.g., motion blur, occlusion), which is central to G-ARC's motivation.

---

## C. Clip-Level Support

### C.1 What Exists

| Component | File | Status |
|-----------|------|--------|
| `frame_labels_to_clips()` | `metrics/clip_metrics.py` | IMPLEMENTED, TESTED (unit) |
| `clip_iou()` | `metrics/clip_metrics.py` | IMPLEMENTED, TESTED (unit) |
| `clip_recall()` | `metrics/clip_metrics.py` | IMPLEMENTED, TESTED (unit) |
| `clip_precision()` | `metrics/clip_metrics.py` | IMPLEMENTED, TESTED (unit) |
| `mean_iou()` | `metrics/clip_metrics.py` | IMPLEMENTED, TESTED (unit) |
| `gvr()` | `metrics/clip_metrics.py` | IMPLEMENTED, TESTED (unit) |
| `compute_clip_metrics()` | `metrics/clip_metrics.py` | IMPLEMENTED, TESTED (unit) |
| `run_clip_metrics_from_cached_frames.py` | `experiments/` | IMPLEMENTED (CLI) |
| `test_clip_metrics.py` | `tests/` | IMPLEMENTED (unit tests) |

### C.2 What Does NOT Exist

| Component | Status | Impact |
|-----------|--------|--------|
| **Candidate clip generation from SUPG output** | NOT IMPLEMENTED | Cannot convert frame selections to clips |
| **GT clip generation from continuous video** | NOT IMPLEMENTED | Cannot define ground truth clips |
| **Clip-level oracle** | NOT IMPLEMENTED | No way to evaluate clip predicates |
| **Clip IoU sweep** | NOT IMPLEMENTED | No parameter sweep over IoU thresholds |
| **Temporal gap tolerance tuning** | NOT IMPLEMENTED | No exploration of merge parameters |
| **Clip-level SUPG integration** | NOT IMPLEMENTED | No end-to-end clip experiment |
| **ARC-style candidate generation** | NOT IMPLEMENTED | No proxy-based temporal clustering |
| **Temporal proxy smoothing** | NOT IMPLEMENTED | No temporal-aware proxy scores |
| **Clip boundary uncertainty** | NOT IMPLEMENTED | No boundary-aware sampling |
| **Clip merge/split handling** | NOT IMPLEMENTED | No non-monotonicity handling |

### C.3 Frame-Level vs Clip-Level: Honest Assessment

The project currently operates at **three levels**, none of which is "clip-level retrieval":

1. **Frame-level selection** (DONE): SUPG selects individual frames. Evaluation is frame precision/recall. This is what all current experiments measure.

2. **Frame-to-clip conversion** (IMPLEMENTED BUT UNTESTED ON REAL DATA): `clip_metrics.py` can convert frame labels to clips and compute clip IoU. But it has only been tested on synthetic data, never on real temporal video.

3. **Clip-level retrieval** (NOT IMPLEMENTED): No code generates candidate clips from proxy scores, evaluates clip-level predicates, or provides clip-level guarantees.

The project **cannot honestly claim ARC-style retrieval support**. It has:
- Frame-level selection (SUPG) ✓
- Clip metrics code (untested on real data) ✓
- Clip-level retrieval pipeline: ✗
- Clip-level guarantee mechanism: ✗

---

## D. Experimental Rigor

### D.1 What Has Been Run

| Experiment | Trials | Dataset | Non-Vacuous? | Publishable? |
|-----------|--------|---------|--------------|--------------|
| SUPG synthetic Beta(0.01,1) | 100 | Synthetic 1M | Yes | Yes (paper reproduction) |
| SUPG synthetic Beta(0.01,2) | 100 | Synthetic 1M | Yes | Yes (paper reproduction) |
| ABae synthetic N=100K | 30 | Synthetic | Partial | Yes (paper reproduction) |
| KITTI 0005 smoke | 5 | Real images | No (vacuous) | No |
| KITTI combined smoke | 5 | Real images | No (vacuous) | No |
| KITTI proxy ablation | 5 | Real images | No (all vacuous) | No |
| BDD100K smoke | 20 | Real images | Yes | Partial (frame-level only) |
| BDD100K formal | 100 | Real images | Yes | Partial (frame-level only) |
| ABae BDD100K smoke | 30 | Real images | N/A | Partial |
| ABae BDD100K coverage | 100 | Real images | N/A | Partial |

### D.2 Statistical Significance Assessment

**What is statistically meaningful:**
- SUPG synthetic reproduction (100 trials): Failure rate = 0.0 for SUPG, 0.47-0.57 for U-NOCI. Clear method differentiation.
- BDD100K formal (100 trials): SUPG-RT failure_rate = 0.0, mean_recall = 0.977. U-NOCI-RT failure_rate = 0.40. Clear differentiation.

**What is NOT statistically meaningful:**
- KITTI experiments (5 trials): Too few trials, vacuous results.
- ABae synthetic (30 trials): Coverage varies wildly (63-100%). Anti-conservative COUNT CIs.
- No clip-level experiments exist.

### D.3 Missing Experiments

**Critical missing experiments (block publication):**

1. **Temporal video SUPG experiment**: Run SUPG on continuous video frames with temporal ordering. Measure whether frame-level recall guarantee transfers to clip-level recall.

2. **Frame-to-clip gap analysis**: For each method, measure `frame_recall - clip_recall` on real temporal data. This is the core research question.

3. **GVR (Guarantee Violation Rate) experiment**: Run 100 trials on temporal data, measure fraction of trials where clip_recall < gamma. Compare SUPG-RT vs U-NOCI-RT.

4. **IoU threshold sensitivity**: Sweep IoU from 0.3 to 0.9, measure clip recall degradation.

5. **Budget sensitivity**: Sweep budget from 100 to 5000, measure clip recall vs oracle calls.

6. **Temporal gap tolerance sensitivity**: Sweep gap_tolerance from 0 to 2.0 seconds, measure clip merge behavior.

**Important missing experiments (strengthen paper):**

7. **Proxy reliability sensitivity**: Test with different proxy/oracle pairs (e.g., YOLOv8s vs YOLOv8x).

8. **Positive rate sensitivity**: Test with different count thresholds (5%, 10%, 20% positive rates).

9. **Video length sensitivity**: Test on short (1K frames) vs long (100K frames) videos.

10. **ARC baseline comparison**: Implement ARC-style proxy pruning + temporal clustering as a baseline.

### D.4 Missing Sanity Checks

1. **Proxy-oracle correlation**: No formal analysis of how well YOLOv8n proxy scores predict YOLOv8x oracle labels. The proxy ablation tested score rules but not the fundamental proxy quality.

2. **Temporal autocorrelation**: No analysis of how correlated adjacent frames are. This is critical for understanding whether i.i.d. assumptions break down.

3. **Positive event duration distribution**: No analysis of how long positive events last in continuous video. This determines whether clip-level evaluation is meaningful.

4. **Proxy score stability over time**: No analysis of whether proxy scores are stable within a temporal event or vary significantly.

---

## E. Research Positioning

### E.1 Current Alignment

The project currently aligns most closely with:

| Dimension | Alignment Strength | Evidence |
|-----------|-------------------|----------|
| **Systems** | STRONG | Working proxy/oracle pipeline, materialization, YOLO integration |
| **Database Systems (AQP)** | STRONG | SUPG/ABae adapters, statistical guarantee framework, budget-constrained queries |
| **IR / Video Retrieval** | WEAK | No temporal video processing, no clip-level retrieval, no ARC implementation |
| **Computer Vision** | WEAK | Uses YOLO as black box, no novel CV contribution |

### E.2 Strongest Current Narrative

The strongest publishable narrative right now is:

**"Approximate Selection with Guarantees on Real Video Frame Data"**

This would be a systems paper showing:
1. SUPG works on real image data (BDD100K) with non-trivial selection.
2. Frame-level guarantees transfer to real proxy/oracle pairs (YOLOv8n/x).
3. Proxy score design matters (ablation shows continuous scores needed).
4. Budget/proxy quality tradeoffs on real data.

**But this is NOT G-ARC.** This is a SUPG-on-real-data paper, not a clip-level guarantee paper.

### E.3 What Would Make It G-ARC

To be a G-ARC paper, the project needs:

1. Continuous video data with temporal ground-truth clips.
2. Frame-to-clip merge pipeline with temporal IoU evaluation.
3. Demonstration that frame-level guarantees do NOT transfer to clip level (the motivation).
4. A mechanism to improve clip-level guarantee (boundary-aware allocation, temporal smoothing, etc.).
5. GVR experiments showing the mechanism works.

None of these exist.

### E.4 Realistic Paper Directions

**Direction A: SUPG-on-Real-Video (achievable in 4-6 weeks)**
- Use BDD100K results as-is.
- Add UA-DETRAC temporal video.
- Show frame-level SUPG works on real proxy/oracle.
- Show frame-to-clip gap exists.
- No clip-level guarantee mechanism.
- Target: workshop paper or short paper.

**Direction B: Frame-to-Clip Gap Analysis (achievable in 8-12 weeks)**
- Acquire UA-DETRAC or similar temporal video.
- Implement frame-to-clip pipeline.
- Measure frame_recall vs clip_recall gap systematically.
- Show SUPG-RT frame guarantee does NOT transfer to clips.
- Propose heuristic mitigation (gap tolerance, temporal smoothing).
- Target: full paper at SIGIR/ICDE.

**Direction C: G-ARC Full (12-24 weeks)**
- Everything in Direction B.
- Implement boundary-aware oracle allocation.
- Implement temporal dependence handling.
- Implement clip-level guarantee mechanism.
- GVR experiments.
- Target: VLDB/SIGMOD.

---

## F. Next-Step Prioritization

### F.1 Immediate Blockers

1. **No temporal video data**: The single most critical blocker. Without continuous video, no clip-level experiments are possible. UA-DETRAC is identified as the primary candidate (100K+ frames, traffic surveillance, direct download). **Must acquire and process this first.**

2. **No frame-to-clip pipeline for real data**: `clip_metrics.py` exists but has never been connected to real SUPG output on temporal data. Need to implement: (a) SUPG selects frames, (b) merge selected frames into candidate clips, (c) evaluate against GT clips.

3. **No GT clip definition**: Need to define what constitutes a "ground-truth clip" in continuous video. Options: (a) contiguous positive frames, (b) annotated events, (c) temporal clustering of positive frames.

### F.2 Highest-Value Next Experiments

1. **UA-DETRAC materialization** (1-2 days): Download, extract frames at 5fps, run YOLOv8n proxy + YOLOv8x oracle, calibrate count threshold, build frames.parquet.

2. **Frame-to-clip gap measurement** (2-3 days): Run SUPG-RT on UA-DETRAC frames, merge selected frames into candidate clips, compute clip_recall vs frame_recall. This is the **single most important experiment** for the paper.

3. **GVR on temporal data** (2-3 days): 100 trials on UA-DETRAC, measure fraction of trials where clip_recall < gamma. Compare SUPG-RT vs U-NOCI-RT.

4. **IoU threshold sweep** (1 day): Sweep IoU from 0.3 to 0.9, plot clip_recall vs IoU for each method.

### F.3 Missing Infrastructure

| Component | Priority | Effort |
|-----------|----------|--------|
| UA-DETRAC download + frame extraction | CRITICAL | 1 day |
| UA-DETRAC YOLO materialization | CRITICAL | 1-2 days |
| Frame-to-clip merge from SUPG output | CRITICAL | 2-3 days |
| GT clip generation from continuous labels | CRITICAL | 1-2 days |
| Clip-level experiment runner | HIGH | 2-3 days |
| Clip-level config system | HIGH | 1 day |
| Temporal autocorrelation analysis | MEDIUM | 1 day |
| Proxy score temporal smoothing | MEDIUM | 2-3 days |
| ARC-style baseline | MEDIUM | 3-5 days |
| Boundary-aware oracle allocation | LOW (future) | 1-2 weeks |
| Temporal dependence CI correction | LOW (future) | 2-4 weeks |

### F.4 Most Dangerous Dead-End Directions

1. **More KITTI tuning**: KITTI is too small. No amount of proxy score engineering will fix N=1176. Stop investing time here.

2. **More BDD100K experiments**: BDD100K is images, not video. Additional experiments on BDD100K will not advance the clip-level story. Use BDD100K results as-is for the frame-level contribution.

3. **Implementing G-ARC guarantee mechanism before having clip-level data**: The boundary-aware allocation and temporal dependence handling are theoretical contributions that need experimental validation. Without temporal video data, implementing these is wasted effort.

4. **ABae reproduction deepening**: ABae is a secondary contribution. The COUNT CI coverage issue is a known problem with stratified bootstrap. Spending more time on this diverts from the core G-ARC story.

5. **CS2-insight-agent integration**: The build plan includes CS2 as a "candidate generator," but CS2 is domain-specific to gaming, not video retrieval. This is a distraction.

### F.5 Recommended 2-Week Roadmap

**Week 1: Temporal Data Acquisition + Frame-Level Pipeline**

| Day | Task | Deliverable |
|-----|------|-------------|
| 1 | Download UA-DETRAC training set (~5.6GB) | Raw video files |
| 1-2 | Extract frames at 5fps from 5-10 sequences | frame_metadata.parquet |
| 2-3 | Run YOLOv8n proxy + YOLOv8x oracle on UA-DETRAC | proxy_scores.parquet, oracle_scores.parquet |
| 3 | Calibrate count threshold K for 5-15% positive rate | count_calibration.json |
| 3-4 | Build frames.parquet with temporal columns | frames.parquet with video_id, frame_idx, timestamp |
| 4 | Run SUPG-RT 20-trial smoke on UA-DETRAC | summary.csv with frame-level results |
| 5 | Run SUPG-RT 100-trial formal if non-vacuous | Formal frame-level results |

**Week 2: Clip-Level Pipeline + Gap Analysis**

| Day | Task | Deliverable |
|-----|------|-------------|
| 6-7 | Implement frame-to-clip merge from SUPG output | Code: selected frames -> candidate clips |
| 7 | Generate GT clips from contiguous positive frames | gt_clips.json |
| 7-8 | Run clip-level evaluation on SUPG-RT output | clip_recall, clip_precision, mIoU |
| 8 | **Measure frame_recall vs clip_recall gap** | Gap analysis report |
| 9 | Run 100-trial GVR experiment | GVR = fraction of trials where clip_recall < gamma |
| 9-10 | IoU threshold sensitivity sweep | Plot: clip_recall vs IoU |
| 10 | Budget sensitivity sweep | Plot: clip_recall vs budget |
| 10 | Write up results | Draft experiment section |

**Success criteria after 2 weeks:**
- UA-DETRAC materialized with proxy/oracle scores.
- SUPG-RT non-vacuous on UA-DETRAC (frame-level).
- Frame-to-clip gap measured on real data.
- GVR computed on real temporal data.
- Clear answer to: "Does frame-level guarantee transfer to clip level?"

---

## G. Detailed Component Audit

### G.1 Adapters

| Adapter | Faithful to Paper? | Tested? | Issues |
|---------|-------------------|---------|--------|
| `supg_adapter.py` | Yes (wraps refe_repos/supg) | Yes (smoke + formal) | Clean, no issues |
| `abae_adapter.py` | Partially (custom impl, not using refe_repos/abae) | Yes (smoke + formal) | COUNT CI anti-conservative. Not code-faithful to ABae repo. |
| `cs2_adapter.py` | N/A (build plan only) | No | Not implemented |

### G.2 Baselines

| Baseline | Implemented? | Tested? | Issues |
|----------|-------------|---------|--------|
| `u_noci.py` (U-NOCI-RT/PT) | Yes | Yes | Works correctly |
| `u_ci.py` (U-CI-RT) | Yes | Yes | Always vacuous (selects all). Implementation may not match SUPG Algorithm 2. |
| `uniform_aggregation.py` | Yes | Yes | Works correctly |
| `supg_rt_plus.py` | **No** | No | Not implemented |
| `supg_pt_plus.py` | **No** | No | Not implemented |
| `abae_record.py` | **No** | No | Not implemented (ABae adapter serves this role) |
| `abae_clip_stress.py` | **No** | No | Not implemented |
| `arc_simplified.py` | **No** | No | Not implemented |

### G.3 Metrics

| Metric | Implemented? | Tested? | Issues |
|--------|-------------|---------|--------|
| Frame precision/recall | Yes | Yes | Clean |
| Clip IoU | Yes | Yes (unit) | Never tested on real temporal data |
| Clip recall/precision | Yes | Yes (unit) | Never tested on real temporal data |
| mIoU | Yes | Yes (unit) | Never tested on real temporal data |
| GVR | Yes | Yes (unit) | Never tested on real data. Definition may be wrong: `gvr()` checks `clip_recall >= iou_threshold`, but GVR should check `clip_recall >= gamma` (the recall target). |
| Failure rate | Yes | Yes | Works correctly |
| Aggregation error | Yes | Yes | Works correctly |
| CI coverage | Yes | Yes | Works correctly |

**GVR implementation bug**: `gvr()` in `clip_metrics.py:148-165` uses `iou_threshold` as the threshold for clip_recall, but GVR should use `gamma` (the recall target). The current implementation conflates IoU threshold with recall target.

### G.4 Experiments

| Experiment | File | Status | Notes |
|-----------|------|--------|-------|
| `run_supg_synthetic.py` | `experiments/` | DONE | Beta experiments, 100 trials |
| `run_supg_real_frames.py` | `experiments/` | DONE | BDD100K, 100 trials |
| `run_abae_synthetic.py` | `experiments/` | DONE | Synthetic, 30 trials |
| `run_abae_real_frames.py` | `experiments/` | DONE | BDD100K, 100 trials |
| `materialize_frame_scores.py` | `experiments/` | DONE | YOLO pipeline |
| `calibrate_count_threshold.py` | `experiments/` | DONE | Count calibration |
| `run_proxy_score_ablation.py` | `experiments/` | DONE | 6 rules tested |
| `run_clip_metrics_from_cached_frames.py` | `experiments/` | IMPLEMENTED | Never run on real data |
| `run_supg_clip.py` | `experiments/` | **NOT IMPLEMENTED** | In build plan only |
| `run_abae_clip_stress.py` | `experiments/` | **NOT IMPLEMENTED** | In build plan only |
| `run_cs2_probe.py` | `experiments/` | **NOT IMPLEMENTED** | In build plan only |
| `run_gvr_sweep.py` | `experiments/` | **NOT IMPLEMENTED** | In build plan only |

### G.5 Tests

| Test | File | Coverage |
|------|------|----------|
| `test_clip_metrics.py` | `tests/` | Unit tests for clip IoU, recall, precision, mIoU, GVR, frame_labels_to_clips |
| `test_abae_adapter.py` | `tests/` | Unit tests for ABae stratification, allocation, bootstrap CI |
| `test_fake_real_integration.py` | `tests/` | Integration test with mock data |

No test covers:
- Temporal continuity
- Real video data
- Clip-level SUPG integration
- GVR on real experiments
- Edge cases in frame-to-clip merge

---

## H. Summary of Findings

### H.1 Completed (Solid)

1. Synthetic SUPG reproduction (Beta experiments, 100 trials each).
2. Synthetic ABae reproduction (30 trials, multiple budgets).
3. Real-frame SUPG on BDD100K (100 trials, non-vacuous).
4. Real-frame ABae on BDD100K (100 trials, CI coverage measured).
5. YOLO proxy/oracle materialization pipeline.
6. Count threshold calibration.
7. Proxy score ablation (6 rules).
8. Clip metrics module (code exists, unit tested).

### H.2 Partially Completed (Fragile)

1. ABae adapter (custom reimplementation, not code-faithful to repo).
2. U-CI-RT baseline (always vacuous, may not match paper).
3. Clip metrics (unit tested only, never on real data).
4. Experiment orchestration (scripts exist but use hardcoded paths).

### H.3 Not Started (Critical Gaps)

1. Temporal video data acquisition and processing.
2. Frame-to-clip pipeline on real data.
3. GT clip generation from continuous video.
4. Clip-level SUPG experiment.
5. GVR experiment on real temporal data.
6. Frame-to-clip gap analysis.
7. G-ARC guarantee mechanism (boundary-aware allocation, temporal dependence handling).
8. ARC-style baseline.
9. Clip-level experiment configs.
10. Any experiment demonstrating the core research contribution.

### H.4 Honest Assessment

The project is at **25-30% completion** toward a publishable G-ARC paper:

- **Frame-level contribution**: 80% complete. BDD100K results are solid. Needs UA-DETRAC for temporal context.
- **Clip-level contribution**: 10% complete. Metrics code exists but no real experiments.
- **G-ARC guarantee mechanism**: 0% complete. Conceptual only.
- **Paper writing**: 20% complete. Research report and protocol exist, but no experiment results for the core contribution.

The **most realistic near-term paper** is a systems paper on "SUPG on Real Video Frame Data" using BDD100K results. The **G-ARC contribution** (clip-level guarantees) requires 3-6 months of additional work, starting with temporal video data acquisition.
