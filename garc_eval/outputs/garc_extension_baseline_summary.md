# G-ARC Extension Baseline Summary

**IMPORTANT**: These experiments use BDD100K data and are G-ARC extensions.
They are NOT from the original SUPG or ABae papers. The original papers used
different datasets (ImageNet, OntoNotes, TACRED for SUPG; night-street, taipei,
celeba, Amazon, trec05p for ABae).

---

## 1. BDD100K Dataset

- **Source**: BDD100K validation subset (10,000 images, 1280x720)
- **Scene**: Driving/dashcam road scenes (urban, highway, residential)
- **Predicate**: count_car(frame) >= 13
- **Positive rate**: 9.92% (992 / 10,000)
- **Proxy**: YOLOv8n | **Oracle**: YOLOv8x pseudo-oracle
- **YOLO rerun**: NO (using cached data only)

---

## 2. SUPG Selection Results (100 trials, budget=1000, gamma=0.9, delta=0.05)

| Method | QType | Failure Rate | Mean Recall | Mean Precision | Selected N / N |
|--------|-------|-------------|-------------|----------------|----------------|
| U-NOCI-RT | RT | 0.40 | 0.907 | 0.336 | 0.277 |
| U-CI-RT | RT | 0.00 | 1.000 | 0.099 | 1.000 (vacuous) |
| **SUPG-RT** | **RT** | **0.00** | **0.977** | **0.185** | **0.542** |
| U-NOCI-PT | PT | 0.85 | 0.128 | 0.440 | 0.015 |
| SUPG-PT | PT | 0.00 | 0.275 | 1.000 | 0.027 |

**Key findings**:
- SUPG-RT achieves 0% failure rate with 97.7% recall, selecting 54% of data (non-vacuous)
- U-CI-RT is vacuous (selects 100% of data)
- U-NOCI-RT has 40% failure rate (cannot meet gamma=0.9 guarantee)
- SUPG-PT achieves perfect precision with 27.5% recall

---

## 3. ABae Aggregation Results (30 trials, budget=1000, alpha=0.05)

### AVG Estimation (oracle_count | label=1)

| Method | Abs Error | Rel Error | CI Width | Coverage |
|--------|-----------|-----------|----------|----------|
| Uniform | 0.1662 | 0.0109 | 0.9348 | 96.67% |
| ABae-paper | 0.1569 | 0.0103 | 0.6092 | 93.33% |
| ABae-full_variance | 0.1266 | 0.0083 | 0.5709 | 100.00% |

### COUNT Estimation (label=1)

| Method | Abs Error | Rel Error | CI Width | Coverage |
|--------|-----------|-----------|----------|----------|
| Uniform | 74.9 | 0.0755 | 374.6 | 96.67% |
| ABae-paper | 80.3 | 0.0810 | 246.8 | **80.00%** |
| ABae-full_variance | 78.1 | 0.0788 | 164.0 | **56.67%** |

### COUNT Coverage Diagnostic (100 trials)

| Method | AVG Coverage | COUNT Coverage |
|--------|-------------|----------------|
| Uniform | 97.00% | 97.00% |
| ABae-paper | 97.00% | **89.00%** |
| ABae-full_variance | 97.00% | **70.00%** |

**Key findings**:
- ABae-paper narrows AVG CI by 35% vs Uniform (0.609 vs 0.935)
- ABae-paper narrows COUNT CI by 34% vs Uniform (247 vs 375)
- **WARNING**: COUNT coverage for ABae-paper is 89% (below 95% target)
- **WARNING**: COUNT coverage for ABae-full_variance is 70% (well below 95% target)
- Uniform baseline has well-calibrated CIs (97% coverage)

---

## 4. COUNT Coverage Issue

The percentile bootstrap CI for COUNT is anti-conservative with stratified sampling:

- **Root cause**: Non-uniform allocation (more samples in high-positive strata) reduces
  bootstrap variability, making CIs too narrow
- **Impact**: ABae-paper COUNT CIs cover only 89% of trials (target: 95%)
- **Mitigation**: Use ABae-paper for AVG estimation (well-calibrated); interpret COUNT
  CIs with caution

---

## 5. Limitations

1. BDD100K is image-level, not temporal clip-level
2. Oracle is YOLOv8x pseudo-oracle, not human ground truth
3. Single predicate only (count_car >= 13)
4. Driving perspective, not surveillance
5. COUNT bootstrap CI is anti-conservative for ABae methods

---

Generated: 2026-05-20
