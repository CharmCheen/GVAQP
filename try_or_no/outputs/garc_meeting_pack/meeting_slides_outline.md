# Meeting Slides Outline (6 Slides)

---

## Slide 1: Real Problem — Relevant Clip Query

**Title:** Relevant Clip Query Returns Clips, Not Frames

**Key points:**
- A relevant clip query returns continuous temporal clips, not individual frames.
- Each clip is a contiguous interval where a statistical frame condition holds for every frame, and the interval length meets a minimum duration constraint tau.
- The oracle predicate (e.g., precise vehicle count) is expensive to evaluate. Budget is limited.
- Examples: traffic congestion intervals, public safety monitoring windows, autonomous driving data audit, scientific video analysis.

**Visual:** Diagram showing a video timeline with oracle-positive frames grouped into clips, with tau filtering applied.

---

## Slide 2: Positioning — SUPG / ABae / ARC / G-ARC

**Title:** The Missing Cell in the Method Landscape

**Key points:**
- **SUPG** (PVLDB 2020): High-probability precision/recall guarantee, but output is a frame set. No clip support.
- **ABae** (PVLDB 2021): Confidence intervals for aggregation queries with expensive predicates. Not retrieval.
- **ARC**: Supports relevant clip query. Candidate-side confidence (precision-like quality estimate). Optimizes recall empirically but does not provide explicit clip-level recall guarantee.
- **G-ARC** (proposed): Targets the missing cell — relevant clip query + clip-level recall certification.

**Visual:** 2x2 table with rows = {frame, clip} and columns = {no guarantee, guarantee}. SUPG fills {frame, guarantee}. ARC fills {clip, no guarantee}. G-ARC targets {clip, guarantee}.

---

## Slide 3: Why Frame-Level Guarantee Does Not Imply Clip-Level Recall

**Title:** Five Reasons Frame Guarantees Are Not Enough

**Key points:**
1. **Continuity**: Clips require contiguous frame coverage, not just any frames. Random frame sampling is spatially uniform, not temporally clustered.
2. **Boundary**: Small boundary errors can shift clip start/end, reducing IoU below threshold.
3. **IoU**: Even 95% frame recall can yield 0% clip recall if missed frames cluster at boundaries.
4. **Fragmentation**: Oracle noise at clip boundaries can split a true clip into sub-tau segments, all of which are discarded.
5. **Merge/split**: Merging nearby candidates can distort IoU with individual true clips.
6. **tau**: Predicted positive segments shorter than tau are discarded, even if frame-level recall is high.

**Visual:** Diagram showing a true clip, then boundary errors causing IoU drop, then fragmentation causing clip loss.

---

## Slide 4: P1 Smoke — High Confidence but Low Recall

**Title:** Candidate-Side Confidence Does Not Certify Clip Coverage

**Key points:**
- Surrogate experiment on UA-DETRAC (60 videos, 83K frames). Not an ARC reproduction.
- At high proxy thresholds (p95–p99.5), the proxy has very high frame-level precision but low frame-level recall.
- Candidate-side confidence samples oracle labels inside the candidate region: sees high precision, reports high confidence.
- But most true clips are outside the candidate region and are completely missed.

**Table:**

| K  | tau | proxy | reported_confidence | actual_clip_recall |
| -- | --: | ----- | ------------------: | -----------------: |
| 20 |  20 | p99   |               1.000 |              0.000 |
| 20 |  20 | p95   |               0.975 |              0.314 |
| 25 |  20 | p99.5 |               0.996 |              0.154 |
| 25 |  30 | p99.5 |               0.995 |              0.091 |

**Core message:** This is not an ARC failure claim. It only shows that a natural candidate-side confidence estimator has a structural blind spot: it certifies candidate quality but not candidate coverage.

---

## Slide 5: G-ARC Initial Idea — Verification Sampling Layer

**Title:** ARC-Style Generation + Verification / Certification Layer

**Key points:**
- **Step 1:** Proxy candidate generation (ARC-style: proxy thresholding, temporal clustering).
- **Step 2:** Candidate verification — oracle samples inside and near candidates to verify quality and boundaries.
- **Step 3:** Non-candidate audit — oracle samples outside candidates to detect missed true clips.
- **Step 4:** Conservative missed-clip upper bound estimation.
- **Step 5:** Clip recall lower bound / certificate.

**Certificate target:** Pr[ClipRecall >= gamma] >= 1 - delta

**Visual:** Pipeline diagram: proxy candidates → candidate verification → non-candidate audit → recall certificate.

---

## Slide 6: Risks and Next Two-Week Plan

**Title:** Risks, Plan, and Questions

**Risks:**
- Bound may be too loose (requires too many oracle calls).
- Oracle cost may be too high for practical use.
- Missed frame mass does not directly equal missed clip count.
- Boundary / IoU / merge / split / tau constraints need careful treatment.
- Benchmark may be too easy or too small.
- Distribution-free wording must be used carefully.

**Two-week plan:**
- Week 1: Clean up ARC-style surrogate on real data. Finalize formal problem definition. Implement first verification sampling MVP.
- Week 2: Compare full_oracle, proxy-only, SUPG-style, ARC-style surrogate, and G-ARC verification layer. Measure GVR, actual clip recall, precision, mIoU, oracle ratio, certificate pass rate, bound tightness. Decide if direction is strong enough.

**Questions for advisor:**
1. Is ARC confidence best interpreted as candidate-side precision-like quality?
2. Is clip-level recall guarantee a reasonable primary target?
3. Is verification sampling after ARC-style candidate generation a valid direction?
4. If the bound is loose, is conservative clip-aware AQP still valuable?
5. Can we obtain ARC code or implementation details?
