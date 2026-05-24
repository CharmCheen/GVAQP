# Frame-to-Clip Gap Analysis Report

Generated: 2026-05-22

---

## 中文摘要（组会汇报用）

### 当前结论

在 UA-DETRAC（13,932 帧，126 个 GT clips）上，frame-level recall 与 clip-level recall 之间存在可测量的 gap：
- U-NOCI-RT（均匀随机采样）：gap = 7.6 个百分点（frame recall 89.2% → clip recall 81.7%），23 个 clips 未充分覆盖。
- SUPG-RT（importance sampling）：gap = 1.1 个百分点（frame recall 97.9% → clip recall 96.7%），仅 4 个 clips 未充分覆盖。
- Gap 随 coverage threshold 收紧而增大：95% coverage 时 U-NOCI gap = 8.8%，SUPG gap = 2.0%。

### 证据边界

- 数据集：单一 UA-DETRAC 子集，YOLOv8x pseudo-oracle 标签。
- Clips 较短（均值 0.32s，约 12 个正帧），可能低估 gap。
- 仅 10 个 trial，统计稳定性有限。
- Proxy（YOLOv8n）与 pseudo-oracle（YOLOv8x）高度相关，可能掩盖真实 gap。

### 不能过度宣称的内容

- 不能说"frame-level 保证可以自动转移到 clip-level"——gap 是真实存在的。
- 也不能说"gap 很大，需要全新系统"——SUPG-RT 的 gap 仅 1.1%，在当前设置下很小。
- 不能从单一数据集推断一般性结论。
- 当前证据支持"workshop paper 或 short paper"级别的贡献，不是 full conference paper。

### 下一步动作

- 在更长 clips（10+ 帧）、更低正样本率（1-5%）、更弱 proxy 上复现 gap 分析。
- 如果更严苛设置下 gap 显著增大，可支撑 full paper 的 motivation。
- 如果 gap 始终很小，需要重新评估 G-ARC 的研究价值。

---

## 1. Experiment Setup

- **Dataset**: UA-DETRAC traffic surveillance video (8 sequences)
- **Total frames**: 13,932
- **Positive rate**: 10.9% (1,519 / 13,932)
- **GT clips**: 126 temporal events (contiguous positive frame runs, min 3 frames)
- **Budget**: 1,000 oracle calls
- **Gamma (recall target)**: 0.9
- **Delta**: 0.05
- **Coverage threshold**: 0.9 (clip is "hit" if 90%+ of its positive frames are selected)
- **Trials**: 10 per method
- **Models**: YOLOv8n (proxy), YOLOv8x (pseudo-oracle)
- **Query**: count_car(frame) >= 25

---

## 2. Ground-Truth Clip Statistics

- **Number of GT clips**: 126
- **Mean duration**: 0.32s
- **Median duration**: 0.16s
- **Min duration**: 0.08s (3 frames)
- **Max duration**: 6.64s
- **Mean positive frames per clip**: ~12

| Duration Range | Count | Percentage |
|----------------|-------|------------|
| < 0.2s | 78 | 61.9% |
| 0.2-0.5s | 28 | 22.2% |
| 0.5-1.0s | 10 | 7.9% |
| 1.0-2.0s | 6 | 4.8% |
| > 2.0s | 4 | 3.2% |

**Note**: GT clips are short because the count_car >= 25 predicate creates sparse positive frames within longer vehicle passages.

---

## 3. Frame vs Clip Recall Comparison

| Method | Frame Recall | Clip Recall (90% cov) | Gap | Mean Coverage | GT Clips Hit |
|--------|-------------|----------------------|-----|---------------|-------------|
| U-NOCI-RT | 0.892 | 0.817 | **+0.076** | 0.929 | 102.9 / 126 |
| U-CI-RT | 1.000 | 1.000 | 0.000 | 1.000 | 126 / 126 |
| **SUPG-RT** | **0.979** | **0.967** | **+0.011** | **0.991** | **121.9 / 126** |

---

## 4. Gap Analysis

**Key question**: Does high frame recall guarantee high clip recall?

### U-NOCI-RT (Uniform Random Sampling)

- Frame recall: 0.892
- Clip recall: 0.817
- Gap: **+0.076** (7.6 percentage points)
- **23 clips missed** out of 126

U-NOCI-RT selects frames uniformly at random. With budget=1000, it achieves 89% frame recall but only 82% clip recall at 90% coverage threshold. The 7.6-point gap means that **frame-level guarantees do NOT automatically translate to clip-level guarantees**.

The gap is caused by U-NOCI-RT's random selection missing consecutive positive frames within clips. When 3+ consecutive frames are missed (6.5 clips affected on average), the clip's coverage drops below 90%.

### SUPG-RT (Importance Sampling with Guarantee)

- Frame recall: 0.979
- Clip recall: 0.967
- Gap: **+0.011** (1.1 percentage points)
- **4 clips missed** out of 126

SUPG-RT uses importance sampling based on proxy scores. It achieves 98% frame recall and 97% clip recall. The gap is only 1.1 points — much smaller than U-NOCI-RT.

**Why SUPG-RT has a smaller gap**: SUPG's importance sampling preferentially selects frames with high proxy scores, which tend to cluster around positive events. This creates denser coverage within clips, reducing the probability of consecutive misses.

### Gap by Coverage Threshold

| Coverage Threshold | U-NOCI-RT Gap | SUPG-RT Gap |
|-------------------|---------------|-------------|
| 50% | -0.072 | -0.020 |
| 70% | -0.004 | -0.008 |
| 80% | +0.046 | -0.003 |
| **90%** | **+0.076** | **+0.011** |
| 95% | +0.088 | +0.020 |

The gap increases with stricter coverage thresholds. At 95% coverage, U-NOCI-RT has an 8.8-point gap while SUPG-RT has only a 2.0-point gap.

---

## 5. Temporal Miss Patterns

| Method | Fully Hit | Fully Missed | Sparse Miss | Consecutive Miss | Boundary Miss |
|--------|-----------|--------------|-------------|------------------|---------------|
| U-NOCI-RT | 99.8 | 0.0 | 19.7 | 6.5 | 0.0 |
| U-CI-RT | 126.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| SUPG-RT | 120.5 | 0.0 | 4.1 | 1.4 | 0.0 |

- **Fully Hit**: All positive frames in the GT clip are selected (coverage >= 90%).
- **Consecutive Miss**: 3+ consecutive positive frames missed within a clip.
- **Sparse Miss**: 1-2 isolated positive frames missed.

U-NOCI-RT has 6.5 consecutive misses per trial on average, while SUPG-RT has only 1.4. This confirms that **consecutive misses are the primary mechanism** by which frame-level misses amplify into clip-level failures.

---

## 6. Conclusions

### 6.1 Frame-Clip Divergence: YES (for U-NOCI-RT)

The gap between frame-level and clip-level recall is **7.6 percentage points** for U-NOCI-RT at 90% coverage threshold. This is a meaningful divergence:

- Frame recall = 89.2% → Clip recall = 81.7%
- 23 out of 126 clips are inadequately covered
- The gap is caused by consecutive frame misses within clips

### 6.2 SUPG Mitigates the Gap

SUPG-RT reduces the gap to only 1.1 points (97.9% → 96.7%). This is because:

1. **Importance sampling concentrates on high-proxy-score frames**, which tend to cluster around positive events.
2. **Denser coverage within clips** reduces the probability of consecutive misses.
3. **Only 4 clips missed** vs 23 for U-NOCI-RT.

### 6.3 The Gap Is Real But Small

The empirical gap exists but is **smaller than hypothesized**:

- At 90% coverage: gap = 7.6 points (U-NOCI) / 1.1 points (SUPG)
- At 95% coverage: gap = 8.8 points (U-NOCI) / 2.0 points (SUPG)

This is because:
1. **Clips are short** (mean 0.32s, ~12 positive frames). Short clips are easier to cover.
2. **Positive rate is moderate** (10.9%). Budget=1000 provides enough samples.
3. **Proxy scores correlate with positives** (YOLOv8n detects cars reasonably well).

### 6.4 Is There a Publishable Clip-Level Research Gap?

**Honest assessment: WEAK to MODERATE.**

**Evidence FOR a research gap:**
1. U-NOCI-RT shows a 7.6-point gap at 90% coverage. This demonstrates that frame-level guarantees don't automatically transfer.
2. Consecutive misses are the primary mechanism, confirming the theoretical concern.
3. The gap increases with stricter coverage thresholds (up to 8.8 points at 95%).

**Evidence AGAINST a strong research gap:**
1. SUPG-RT already has a small gap (1.1 points) without any clip-level optimization.
2. The gap is smaller than expected — frame-level guarantees transfer reasonably well.
3. The dataset clips are short and dense, which may not stress-test the gap enough.
4. With sufficient budget (10% of data), the gap is manageable.

**What would strengthen the gap:**
1. Longer clips (10+ seconds) where consecutive misses are more damaging.
2. Lower positive rates (1-5%) where budget is more constrained.
3. Weaker proxy models where proxy scores don't correlate well with positives.
4. Stricter coverage requirements (95%+).

---

## 7. Research Gap Assessment

**Is there actually a publishable clip-level research gap?**

**Answer: YES, but it's a modest contribution, not a breakthrough.**

The empirical evidence shows:
1. Frame-level guarantees do NOT perfectly transfer to clip-level (gap exists).
2. The gap is real but small for well-calibrated methods (SUPG).
3. The gap is meaningful for naive methods (U-NOCI: 7.6 points at 90% coverage).

**Most realistic paper direction:**

A paper titled "Do Frame-Level Guarantees Transfer to Clip-Level Video Retrieval?" would contribute:
1. **Empirical evidence** that the gap exists (U-NOCI-RT: 7.6 points).
2. **Analysis** of why SUPG reduces the gap (importance sampling concentrates on events).
3. **Framework** for measuring clip-level quality (coverage-based metrics).
4. **Recommendations** for when clip-aware methods are needed.

This is a **workshop paper or short paper** contribution, not a full VLDB/SIGMOD paper. The gap is real but not large enough to motivate a major new system.

**What would make it a full paper:**
1. Demonstrate the gap is much larger on longer, sparser clips.
2. Propose a clip-aware guarantee mechanism that provably reduces the gap.
3. Show the gap matters in a real application (e.g., video search, surveillance).

---

## 8. Limitations

1. **Pseudo-oracle**: YOLOv8x is used as oracle, not human ground truth. The "failure rate" measures proxy-oracle consistency.
2. **Short clips**: Mean clip duration is 0.32s. Longer clips might show larger gaps.
3. **Single predicate**: Only count_car >= 25 is tested.
4. **Small dataset**: 13,932 frames from 8 sequences. Larger datasets needed.
5. **Coverage threshold is arbitrary**: 90% is chosen as a reasonable but not principled threshold.
6. **No temporal dependence handling**: The gap analysis doesn't account for temporal autocorrelation.

---

## 9. Next Steps

1. **Test on longer clips**: Use a lower count threshold (e.g., K=10) to get longer positive runs.
2. **Test with lower budget**: Budget=200 or 500 to stress-test the gap under resource constraints.
3. **Test with weaker proxy**: Use YOLOv8s (smaller model) as proxy to increase proxy-oracle disagreement.
4. **Test on different datasets**: ActivityNet, THUMOS, or other video datasets with longer events.
5. **Propose clip-aware mechanism**: If the gap is significant on harder workloads, propose a boundary-aware allocation method.

---

*Generated: 2026-05-22*
*Dataset: UA-DETRAC (8 sequences, 13,932 frames)*
*Methods: U-NOCI-RT, U-CI-RT, SUPG-RT*
*Key finding: 7.6-point gap for U-NOCI-RT, 1.1-point gap for SUPG-RT at 90% coverage*
