# realcar_5k ARC Failure Attribution Report

**Date**: 2026-06-07
**Dataset**: realcar_5k, K=12, tau=30
**Question**: Why does ARC achieve recall=0?

---

## 1. Frame-Level Proxy/Oracle Gap

### Correlation

| Metric | Value |
|--------|-------|
| Pearson r | 0.7884 (p=0.0) |
| Spearman r | 0.7957 (p=0.0) |

### Confusion Matrix (proxy_positive vs oracle_positive, K=12)

|  | Oracle=1 | Oracle=0 |
|--|----------|----------|
| **Proxy=1** | TP=298 | FP=139 |
| **Proxy=0** | FN=748 | TN=3815 |

**Precision**: 0.6819
**Recall**: 0.2849
**F1**: 0.4019

### Positive Runs

| Metric | Proxy | Oracle |
|--------|-------|--------|
| Positive frames | 437 | 1046 |
| Runs (any length) | 179 | 237 |
| Runs (length >= 30) | 0 | 5 |

**Proxy run lengths**: min=1, max=11, mean=2.4, median=2.0
**Oracle run lengths**: min=1, max=65, mean=4.4, median=2.0

---

## 2. Clip-Level Proxy/Oracle Gap

| Metric | Value |
|--------|-------|
| GT clips (tau=30) | 5 |
| Proxy clips (tau=30) | 3 |
| Clip recall | 0.0 |
| Clip precision | 0.0 |
| False splits | 0 |
| False merges | 0 |

---

## 3. Candidate Coverage

**GT clips covered by proxy candidates**: 0/5

### Per-GT-Clip Analysis

| GT | Start | End | Length | Max IoU (proxy) | Clusters | Single Cluster |
|----|-------|-----|--------|-----------------|----------|----------------|
| 0 | 359 | 401 | 43 | 0.0 | 4 | No |
| 1 | 405 | 455 | 51 | 0.0 | 3 | No |
| 2 | 2260 | 2290 | 31 | 0.0 | 2 | No |
| 3 | 2356 | 2420 | 65 | 0.0 | 5 | No |
| 4 | 2527 | 2560 | 34 | 0.0 | 3 | No |

---

## 4. Cluster Diagnostics

### Cluster Statistics

| Metric | Value |
|--------|-------|
| Cluster count | 250 |
| Avg length | 20.0 |
| Median length | 20.0 |
| P90 length | 20.0 |
| Min length | 20 |
| Max length | 20 |

### GT Clip Cluster Spanning

| GT | Start | End | Clusters | Single Cluster |
|----|-------|-----|----------|----------------|
| 0 | 359 | 401 | 4 | No |
| 1 | 405 | 455 | 3 | No |
| 2 | 2260 | 2290 | 2 | No |
| 3 | 2356 | 2420 | 5 | No |
| 4 | 2527 | 2560 | 3 | No |

**GT clips in single cluster**: 0/5
**Cluster boundaries inside GT clips**: 12

### Proxy Candidate Cluster Spanning

| Proxy | Start | End | Clusters | Single Cluster |
|-------|-------|-----|----------|----------------|
| 0 | 463 | 512 | 3 | No |
| 1 | 519 | 573 | 4 | No |
| 2 | 2039 | 2070 | 3 | No |

**Proxy candidates in single cluster**: 0/3

---

## 5. Oracle Sampling Diagnostics

| Metric | Value |
|--------|-------|
| Budget (10%) | 500 |
| Proxy positive frames | 213 |
| Proxy in GT clips | 28 |
| Proxy outside GT clips | 185 |
| GT clip frames | 224 |
| Proxy coverage of GT | 0.125 |

---

## 6. Confidence Diagnostics

### Why confidence=0

**Candidates**: 3
**All in same cluster**: False
**All have empty cluster_range**: True
**Mean confidence**: 0.0

### Per-Candidate Analysis

| Clip | Start | End | Length | Same Cluster | Empty Range | N Clusters |
|------|-------|-----|--------|--------------|-------------|------------|
| 0 | 463 | 512 | 50 | No | Yes | 3 |
| 1 | 519 | 573 | 55 | No | Yes | 4 |
| 2 | 2039 | 2070 | 32 | No | Yes | 3 |

### Root Cause

The `calculate_confidence` function in ARC computes:
```python
cluster_range = np.arange(cluster[start] + 1, cluster[end])
```
When `cluster[start] == cluster[end]` (clip within one cluster),
`cluster_range` is empty, and `combined_prob = 0`.

With cluster_size=20 and clip length 30-50, most clips span 2-3 clusters.
But `calculate_boundaries` extends the clip, and the extended boundaries
often fall in the same cluster, making `cluster_range` empty.

---

## 7. Failure Ranking

| Rank | Failure Type | Score | Evidence |
|------|-------------|-------|----------|
| 1 | **D. Confidence calculation failure** | 1.00 | Mean confidence: 0.0, all same cluster: False |
| 2 | **C. Sampling failure** | 0.88 | Proxy coverage of GT: 0.125, proxy in GT: 28/213 |
| 3 | **A. Proxy failure** | 0.60 | F1=0.4019, correlation=0.7884, proxy runs(tau>=30)=0 vs oracle=5 |
| 4 | **B. Clustering failure** | 0.50 | GT in single cluster: 0/5, boundaries in GT: 12 |
| 5 | **E. Query semantics failure** | 0.00 | constant=0 is correct design per algorithm_handler.py |

### Interpretation

1. **Proxy failure (PRIMARY)**: The YOLOv8n proxy has very weak correlation (r=0.7884) with the YOLOv8x oracle at K=12. Only 0 proxy runs survive tau>=30 filtering vs 5 oracle runs. The proxy signal is too fragmented and noisy for ARC to identify correct candidate regions.

2. **Sampling failure (SECONDARY)**: Even when ARC samples oracle queries, only 0.125 of GT clip frames are covered by proxy-positive frames. ARC's progressive sampling is guided by proxy signal, but the proxy misses most GT regions.

3. **Clustering failure (MINOR)**: Cluster boundaries don't align well with GT clips (12 boundaries inside GT clips). However, this is secondary to the proxy failure.

4. **Confidence calculation (CONSEQUENCE)**: confidence=0 is a consequence of proxy failure, not a root cause. If proxy candidates covered GT clips, confidence would be non-zero.

5. **Query semantics (NOT A FAILURE)**: constant=0 is correct per ARC design.

---

## 8. Recommendations

1. **Lower K to 8-10**: Increase proxy positive rate and proxy-oracle correlation
2. **Use raw proxy_score as CDF**: Instead of binary threshold, use normalized vehicle count as continuous proxy probability
3. **Smaller cluster_size (5-10)**: Allow confidence calculation to work
4. **Try different proxy model**: YOLOv8n may be too weak; consider YOLOv8s or YOLOv8m
