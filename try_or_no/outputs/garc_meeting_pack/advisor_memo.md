# Advisor Memo: G-ARC Research Direction

## 1. Proposed Topic

**Guaranteed Approximate Relevant Clip Query Processing over Large-Scale Video Repositories.**

### Target Guarantee

Given:
- A video repository (set of videos, each a sequence of frames)
- An expensive oracle predicate O(f) that labels each frame
- A cheap proxy score A(f) available for all frames
- A minimum clip duration tau (in frames)
- An IoU threshold theta for matching predicted clips to true clips
- An oracle budget B (maximum number of oracle evaluations)
- A recall target gamma in [0, 1]
- A failure probability delta in (0, 1)

The algorithm returns a set of candidate clips C_hat such that:

**Pr[ClipRecall(C_hat, C*) >= gamma] >= 1 - delta**

where C* is the set of ground-truth relevant clips, and ClipRecall is the fraction of true clips hit by at least one candidate clip with IoU >= theta.

---

## 2. Why This Is a Real Problem

Relevant clip query returns **continuous clips**, not individual frames. A clip is a contiguous temporal interval where the oracle predicate holds for every frame and the interval length meets a minimum duration constraint. This is fundamentally different from frame-level selection, where each frame is evaluated independently.

Queries combine **frame-level statistical predicates** (e.g., vehicle count >= K) with **temporal constraints** (e.g., duration >= tau). The output is a set of variable-length temporal intervals, not a set of records.

**Application domains include:**
- **Traffic congestion analysis**: Find all time windows where traffic density exceeds a threshold for at least tau seconds.
- **Public safety monitoring**: Find all intervals where suspicious activity persists for a minimum duration.
- **Autonomous driving data audit**: Find all clips where a pedestrian is in the ego vehicle's field of view for at least tau keyframes.
- **Scientific video analysis**: Find all intervals where a biological event (e.g., cell division) is ongoing.

Exact oracle evaluation is **expensive**. For example, counting vehicles precisely may require a large detection model or human annotation. Budget constraints are realistic: a practitioner may only afford oracle calls on 5-10% of frames.

ARC has already formalized relevant clip query, so the scenario is not invented.

---

## 3. Existing Methods and Gap

### SUPG

SUPG (PVLDB 2020) provides high-probability precision and recall targets for approximate selection. Given a proxy, an oracle, and a budget, SUPG returns a set of records (frames) that satisfies:

Pr[Recall >= gamma] >= 1 - delta  or  Pr[Precision >= gamma] >= 1 - delta

**Strengths:** Rigorous guarantee. Distribution-free under sampling assumptions. Proxy quality affects efficiency, not validity.

**Limitation for G-ARC:** SUPG's output is a **record/frame set**, not a set of clips. It does not model variable-length clips, IoU-based hit semantics, minimum duration tau, merge/split operations, or temporal fragmentation. Frame-level recall does not imply clip-level recall.

### ABae

ABae (PVLDB 2021) addresses aggregation queries with expensive predicates. It uses proxy-stratified sampling and provides confidence intervals for aggregate estimates (e.g., AVG, SUM) under expensive predicate evaluation.

**Strengths:** Valid confidence intervals under sampling assumptions. Efficient proxy-stratified allocation.

**Limitation for G-ARC:** ABae targets **aggregation**, not **retrieval**. It returns a scalar estimate with a confidence interval, not a set of clips. Clip retrieval is a different query type.

### ARC

ARC supports relevant clip query. Its pipeline includes proxy pruning, temporal clustering, oracle refinement, and label propagation. ARC reports a **candidate-side confidence** that measures the quality of the returned candidates (are they pointing at real things?).

**Strengths:** Handles clip-level query semantics. Practical pipeline with proxy pruning and temporal clustering.

**Limitation for G-ARC:** ARC's confidence is **candidate-side / precision-like**. It estimates the quality of the returned candidates but does **not** estimate coverage of true clips outside the candidate set. ARC optimizes recall empirically but does not provide an explicit guarantee of the form:

Pr[ClipRecall >= gamma] >= 1 - delta

### G-ARC

G-ARC is the proposed gap-filling direction. It targets the missing cell in the method landscape:

**Relevant clip query + clip-level recall certification.**

G-ARC aims to combine ARC-style candidate generation with a verification / certification layer that provides a high-probability clip-level recall lower bound.

---

## 4. Evidence From Exploration

### Synthetic Evidence

Synthetic / factorial experiments suggest a **frame-to-clip quality mismatch**:

- The audit-confirmed factorial ablation (240 parameter combinations, 5 seeds each) shows that clip-level degradation is **5-20x larger** than frame-level degradation.
- Propagation strategy has ~5x larger impact than allocation strategy.
- Proxy noise (which causes frame-level label errors at clip boundaries) is the dominant failure source, causing 20-27x amplification from frame to clip level.

### Real-Data Evidence

- **UA-DETRAC** (60 sequences, 83K frames): Real continuous video with bounding box annotations. Shows frame-to-clip gap on real continuous video. Fixed camera, no ego motion.
- **nuScenes mini** (10 scenes, 404 keyframes, 18,538 annotations): Real 3D geometry with ego pose, calibrated cameras, 3D boxes. Baselines degrade meaningfully: fixed_rate_k10 achieves 0.81-0.88 ClipF1 at ~12% oracle budget.

### P1 Smoke: Candidate-Side Confidence vs. Clip-Level Recall

The P1 smoke experiment (ARC-style surrogate on UA-DETRAC) provides direct surrogate motivation. A simple candidate-side confidence estimator was tested against actual clip recall:

| K  | tau | proxy | reported_confidence | actual_clip_recall |
| -- | --: | ----- | ------------------: | -----------------: |
| 20 |  20 | p99   |               1.000 |              0.000 |
| 20 |  20 | p95   |               0.975 |              0.314 |
| 25 |  20 | p99.5 |               0.996 |              0.154 |
| 25 |  30 | p99.5 |               0.995 |              0.091 |

**This is not an ARC reproduction.** It only shows that a natural candidate-side confidence estimator can be high while clip-level recall is low. The mechanism is the **candidate-side blind spot**: at high proxy thresholds, the proxy has very high frame-level precision (candidate quality is excellent) but low frame-level recall (most true clips are outside the candidate region). The confidence metric samples oracle labels inside the candidate region, so it sees high precision and reports high confidence — but it never checks whether true clips were missed outside.

### Limitations of Evidence

- Evidence is not yet sufficient to claim a complete method.
- Synthetic perturbation may not represent real-world proxy noise.
- The nuScenes pipeline has only smoke baselines, no guarantee method tested.
- No real-data guarantee violation rates exist yet.

---

## 5. Proposed First Technical Idea

**ARC-style candidate generation + G-ARC verification / certification layer.**

### Steps

1. **Generate candidate clips** using proxy thresholding and temporal clustering (ARC-style).
2. **Verify candidate clips and boundaries** with oracle samples drawn from within and near candidate regions.
3. **Audit non-candidate regions** using verification sampling to detect missed true clips.
4. **Estimate conservative upper bound** on the number of missed true clips.
5. **Produce clip recall lower bound / certificate**: if the estimated upper bound on missed clips is small enough, certify that ClipRecall >= gamma.
6. **If certificate fails**, either sample more (adaptive budget allocation) or report insufficient budget.

### Key Intuition

The verification layer addresses the candidate-side blind spot by explicitly auditing what the candidates missed. If the non-candidate region is sampled and found to contain few oracle-positive frames, the algorithm can certify that few true clips were missed. If the non-candidate region contains many oracle-positive frames, the algorithm can expand candidates or report insufficient budget.

---

## 6. Main Risks

1. **Bound may be too loose.** The conservative upper bound on missed clips may require too many oracle calls to be tight enough for practical use.
2. **Oracle cost may be too high.** The verification sampling layer adds oracle cost on top of the candidate generation budget. Total cost may exceed practical limits.
3. **Missed frame mass does not directly equal missed clip count.** A region with many positive frames may contain one long clip or many short clips. Converting frame-level observations to clip-level bounds requires careful treatment.
4. **Boundary / IoU / merge / split / tau constraints need careful treatment.** The gap between frame-level observations and clip-level guarantees involves multiple non-trivial transformations.
5. **Benchmark may be too easy or too small.** Current datasets (UA-DETRAC 60 videos, nuScenes 10 scenes) may not stress-test the method sufficiently.
6. **Distribution-free wording must be used carefully.** The MVP should be stated as a finite-population / sampling-based certificate unless additional assumptions are added. Long-term distribution-free guarantee is a target, not a claim.

---

## 7. Next Two-Week Plan

### Week 1

1. **Clean up ARC-style surrogate** on one real continuous dataset (UA-DETRAC or nuScenes). Finalize the baseline pipeline: proxy thresholding, temporal clustering, oracle refinement, label propagation, and clip construction.
2. **Finalize formal problem definition.** Write the minimal formulation (video, oracle, proxy, tau, theta, budget, gamma, delta, ClipRecall, guarantee).
3. **Implement first verification sampling MVP.** After ARC-style candidate generation, draw oracle samples from non-candidate regions. Estimate missed-clip upper bound. Derive clip recall lower bound.

### Week 2

1. **Compare five methods** on one real dataset:
   - full_oracle (upper bound)
   - proxy-only (no oracle)
   - SUPG-style frame selection (frame-level guarantee, no clip awareness)
   - ARC-style surrogate (candidate generation + candidate-side confidence)
   - G-ARC verification layer (candidate generation + verification sampling + recall certificate)
2. **Measure metrics:** GVR (guarantee violation rate), actual clip recall, precision, mIoU, oracle ratio, certificate pass rate, and bound tightness.
3. **Decide** whether the direction is strong enough for a paper-style project.

---

## 8. Questions for Advisor

1. **Is ARC confidence better interpreted as candidate-side precision-like quality rather than recall guarantee?** The P1 smoke suggests this interpretation. Is it fair and accurate?

2. **Is clip-level recall guarantee a reasonable primary target, while precision / mIoU are secondary empirical metrics?** The proposed guarantee only certifies recall, not precision. Is this acceptable?

3. **Is verification sampling after ARC-style candidate generation a valid research direction?** The idea is to add a certification layer on top of existing candidate generation. Is this a meaningful contribution, or is it too incremental?

4. **If the guarantee bound is loose, is conservative clip-aware AQP still valuable?** If the bound requires 50% oracle budget to certify 90% recall, is that still useful? What is the minimum acceptable tightness?

5. **Can we obtain ARC code or implementation details?** Having ARC's actual candidate generation and confidence calibration would help us build a closer surrogate and understand the gap more precisely.
