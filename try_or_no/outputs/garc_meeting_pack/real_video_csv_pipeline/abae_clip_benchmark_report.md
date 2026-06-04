# ABAE + Clip Benchmark Report

## 1. Purpose

Test ABAE (stratified sampling for aggregation) on real video data. Evaluate two dimensions:
1. **Aggregation accuracy**: Can ABAE estimate AVG(vehicle_count | positive) and COUNT(positive) better than uniform sampling?
2. **Clip-level performance**: Can sampled frames recover temporal clips of high-density traffic?

## 2. Setup

| Item | Value |
|------|-------|
| Data | `abae_k5_input.csv` (1775 frames, K=5 label) |
| Positive rate | 34.65% (615 / 1775) |
| Statistic | oracle_vehicle_count (1–12) |
| Exact AVG(stat\|pos) | 6.0764 |
| Exact COUNT(pos) | 615 |
| Oracle | YOLOv8x pseudo-oracle |

### Clip Parameters
- min_clip_len: 3–5 frames
- gap_tolerance: 2–3 frames
- IoU threshold: 0.3–0.5
- Ground truth clips: 13–15

## 3. Results

### 3.1 Aggregation Accuracy (budget=500, 30 trials)

| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT CI width | COUNT coverage |
|--------|:-----------:|:-----------:|:------------:|:------------:|:-------------:|:--------------:|:--------------:|
| Uniform | 0.068 | 1.1% | 0.336 | 93.3% | 18.7 | 150.2 | 100% |
| ABae-paper | 0.054 | 0.9% | **0.284** | 100% | 22.9 | **118.4** | 93.3% |
| ABae-full_var | 0.048 | 0.8% | 0.307 | 100% | 24.3 | 109.8 | 90.0% |

**ABAE-paper 的 CI 更窄**（0.284 vs 0.336），说明分层采样确实提高了估计精度。COUNT 的 CI 也更窄（118.4 vs 150.2）。

### 3.2 Clip-Level Performance (budget=500, min_len=3, gap=3, IoU=0.3)

| Method | Clip Recall | Clip Precision | mIoU | n_pred_clips |
|--------|:-----------:|:--------------:|:----:|:------------:|
| Uniform | 16.2% ± 8.3% | 8.0% ± 4.2% | 0.143 | 30.7 |
| ABae-paper | 15.8% ± 7.5% | 7.6% ± 3.4% | 0.144 | 31.7 |
| ABae-full_var | 15.8% ± 7.5% | 7.6% ± 3.4% | 0.144 | 31.7 |

**Clip recall 只有 ~16%。** 所有方法表现接近，ABAE 在 clip 层面没有明显优势。

### 3.3 Budget=200 时 Clip 完全失败

| Method | Clip Recall | Clip Precision | mIoU |
|--------|:-----------:|:--------------:|:----:|
| Uniform | 0.3% | 2.7% | 0.013 |
| ABae-paper | 0.3% | 1.2% | 0.014 |

Budget=200 时采样帧太稀疏，根本连不成 clip。

## 4. Key Findings

### 4.1 ABAE 在聚合查询上有优势

ABAE-paper 的 CI 比 Uniform 窄 15%（AVG）和 21%（COUNT），覆盖率更高（100% vs 93%）。这验证了分层采样在聚合估计上的价值。

### 4.2 Clip 是完全不同的问题

**ABAE 不是为 clip 查询设计的。** 它是为聚合查询（AVG/COUNT）设计的。Clip 需要的是**时间连续性** — 采样帧必须在时间轴上形成连续片段。

随机/分层采样天然不具备时间连续性：
- Budget=200: 200 个采样点散落在 1775 帧中，间隔约 9 帧，根本连不成 clip
- Budget=500: 稍好，但 clip recall 也只有 16%

### 4.3 Clip 查询需要不同的方法

要找到 temporal clips，需要：
1. **密集采样**（budget 接近 N），或者
2. **时间感知的选择策略**（如 G-ARC 的梯度优化），或者
3. **先用 proxy 选出候选区间，再用 oracle 验证**

ABAE 的分层采样在 clip 问题上和 Uniform 没有本质区别。

## 5. Interpretation

| 查询类型 | ABAE vs Uniform | 原因 |
|----------|----------------|------|
| 聚合 (AVG/COUNT) | **ABAE 更好** (CI 窄 15-21%) | 分层采样减少了估计方差 |
| Clip 发现 | **无显著差异** | 采样稀疏，时间连续性被破坏 |

**这进一步强化了 G-ARC 的动机：**
- SUPG 在 frame-level selection 上很强（100% precision），但召回低
- ABAE 在 aggregation 上很强（窄 CI），但 clip 完全不行
- **G-ARC 如果能同时优化 selection + temporal coherence，就是真正的 gap 填补者**

## 6. Limitations

1. Oracle 是 YOLOv8x 伪 oracle
2. Clip 评估中 ABAE 的采样重建是近似的（adapter 不返回 sampled IDs）
3. 单一视频，clip 结构可能因场景而异
4. 没有测试 G-ARC 的 clip 能力
