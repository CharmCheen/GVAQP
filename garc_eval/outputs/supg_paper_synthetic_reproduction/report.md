# SUPG Paper Synthetic Reproduction Report

Reproduction of SUPG paper Fig 2/3 synthetic experiments.

---

## Experiment 1: Beta(0.01, 1)

- **Dataset**: N=1,000,000, proxy_score ~ Beta(0.01, 1), label ~ Bernoulli(proxy_score)
- **True positive rate**: 0.976%
- **Budget**: 10,000 | **gamma**: 0.9 | **delta**: 0.05 | **Trials**: 100

### RT Methods (Recall Target)

| Method | Failure Rate | Mean Recall | Median Recall | Mean Precision | Selected N / N |
|--------|-------------|-------------|---------------|----------------|----------------|
| U-NOCI-RT | **0.57** | 0.892 | 0.896 | 0.395 | 0.022 |
| U-CI-RT | 0.00 | 1.000 | 1.000 | 0.010 | 1.000 (vacuous) |
| **SUPG-RT** | **0.00** | **0.934** | **0.935** | **0.349** | **0.026** |

### PT Methods (Precision Target)

| Method | Failure Rate | Mean Precision | Median Precision | Mean Recall | Selected N |
|--------|-------------|----------------|------------------|-------------|------------|
| U-NOCI-PT | **0.65** | 0.882 | 0.886 | 0.231 | 2,623 |
| **SUPG-PT** | **0.00** | **0.983** | **0.983** | **0.402** | 3,988 |

### Analysis

- **SUPG-RT**: 0% failure rate, 93.4% mean recall. Selects 2.6% of data. Non-vacuous.
- **U-NOCI-RT**: 57% failure rate — cannot reliably meet gamma=0.9 recall target.
- **U-CI-RT**: 0% failure but vacuous (selects 100% of data).
- **SUPG-PT**: 0% failure rate, 98.3% precision. Perfect precision guarantee.
- **U-NOCI-PT**: 65% failure rate — cannot reliably meet precision target.

**Conclusion**: SUPG achieves its theoretical guarantees (0% failure rate) while U-NOCI fails
to meet the gamma/delta targets. This matches the SUPG paper's findings.

---

## Experiment 2: Beta(0.01, 2)

- **Dataset**: N=1,000,000, proxy_score ~ Beta(0.01, 2), label ~ Bernoulli(proxy_score)
- **True positive rate**: 0.504%
- **Budget**: 10,000 | **gamma**: 0.9 | **delta**: 0.05 | **Trials**: 100

### RT Methods (Recall Target)

| Method | Failure Rate | Mean Recall | Median Recall | Mean Precision | Selected N / N |
|--------|-------------|-------------|---------------|----------------|----------------|
| U-NOCI-RT | **0.47** | 0.897 | 0.902 | 0.228 | 0.020 |
| U-CI-RT | 0.00 | 1.000 | 1.000 | 0.005 | 1.000 (vacuous) |
| **SUPG-RT** | **0.00** | **0.945** | **0.942** | **0.189** | **0.026** |

### PT Methods (Precision Target)

| Method | Failure Rate | Mean Precision | Median Precision | Mean Recall | Selected N |
|--------|-------------|----------------|------------------|-------------|------------|
| U-NOCI-PT | **0.89** | 0.753 | 0.825 | 0.075 | 490 |
| **SUPG-PT** | **0.00** | **1.000** | **1.000** | **0.415** | 2,092 |

### Analysis

- **SUPG-RT**: 0% failure rate, 94.5% mean recall. Selects 2.6% of data. Non-vacuous.
- **U-NOCI-RT**: 47% failure rate — fails to meet gamma=0.9 guarantee.
- **U-CI-RT**: 0% failure but vacuous (selects 100% of data).
- **SUPG-PT**: 0% failure rate, 100% precision. Perfect precision guarantee.
- **U-NOCI-PT**: 89% failure rate — severely fails precision target.

---

## Comparison with SUPG Paper

The SUPG paper (Fig 2/3) shows:
- U-NOCI has high failure rate on low-positive-rate datasets
- U-CI is vacuous (selects all)
- SUPG achieves 0% failure with meaningful selection

Our reproduction confirms these findings on both Beta(0.01, 1) and Beta(0.01, 2) with N=1M:

| Dataset | Method | Failure Rate | Recall | Precision | Vacuous? |
|---------|--------|-------------|--------|-----------|----------|
| Beta(0.01,1) | U-NOCI-RT | 0.57 | 0.892 | 0.395 | No |
| Beta(0.01,1) | U-CI-RT | 0.00 | 1.000 | 0.010 | Yes |
| Beta(0.01,1) | SUPG-RT | 0.00 | 0.934 | 0.349 | No |
| Beta(0.01,2) | U-NOCI-RT | 0.47 | 0.897 | 0.228 | No |
| Beta(0.01,2) | U-CI-RT | 0.00 | 1.000 | 0.005 | Yes |
| Beta(0.01,2) | SUPG-RT | 0.00 | 0.945 | 0.189 | No |

**Key insight**: As the positive rate decreases (Beta(0.01,2) has ~0.5% vs Beta(0.01,1) ~1%),
U-NOCI's failure rate remains high (47-57%) while SUPG maintains 0% failure. U-CI remains
vacuous in both cases. This is consistent with the paper's theoretical analysis.

---

Generated: 2026-05-20
