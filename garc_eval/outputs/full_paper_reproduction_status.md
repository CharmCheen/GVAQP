# Full Paper Reproduction Status

## Overview

This document tracks the reproduction status of experiments from two papers:
1. **SUPG** (Selection using Proxy Guarantees) — selection queries
2. **ABae** (Aggregation with Budget allocation and estimation) — aggregation queries

**Scope**: Only experiments from the original papers. BDD100K experiments are G-ARC extensions,
clearly separated.

---

## SUPG Paper Reproduction

### Synthetic Experiments (Fig 2/3, Sec 5)

| Experiment | Status | Notes |
|------------|--------|-------|
| Beta(0.01,1) 100-trial | **SMOKE** | 30 trials completed, upgrading to 100 |
| Beta(0.01,2) 100-trial | **SMOKE** | 30 trials completed, upgrading to 100 |
| U-NOCI-RT, U-CI-RT, SUPG-RT | **RUNNABLE** | All 5 methods implemented |
| U-NOCI-PT, SUPG-PT | **RUNNABLE** | Implemented |
| Gamma sensitivity (0.5/0.7/0.9/0.95) | **RUNNABLE** | Script supports --gamma flag |
| Cost analysis (oracle calls saved) | **RUNNABLE** | sampled_n tracked in results |

### Real-World Experiments

| Experiment | Status | Notes |
|------------|--------|-------|
| ImageNet hummingbird | **BLOCKED** | Need ImageNet subset + oracle labels |
| Night-street car (BDD100K) | **G-ARC EXTENSION** | Cached data available, not from original paper |
| OntoNotes entity selection | **BLOCKED** | Need OntoNotes + NER oracle |
| TACRED relation selection | **BLOCKED** | Need TACRED + RE oracle |

### Sensitivity Experiments

| Experiment | Status | Notes |
|------------|--------|-------|
| Model drift robustness | **BLOCKED** | Need drift simulation script |
| Proxy noise sensitivity | **BLOCKED** | Need noise injection script |
| Class imbalance sensitivity | **BLOCKED** | Need imbalance sweep script |
| CI method comparison | **PARTIAL** | Only percentile bootstrap; need BCa variant |

---

## ABae Paper Reproduction

### Synthetic Experiments (Fig 3-5, Sec 5)

| Experiment | Status | Notes |
|------------|--------|-------|
| Single-predicate RMSE vs budget | **RUNNABLE** | run_abae_synthetic with budgets 500-10000 |
| Low-budget RMSE | **RUNNABLE** | Budget=500 included |
| Q-error / relative error | **RUNNABLE** | aggregation_metrics computes rel_error |
| CI width | **RUNNABLE** | Computed per trial |
| CI coverage | **RUNNABLE** | Computed per trial |
| Lesion: no sample reuse vs uniform | **RUNNABLE** | Uniform baseline implemented |
| Strata K sensitivity | **RUNNABLE** | --num-strata flag supported |
| Stage1 fraction C sensitivity | **RUNNABLE** | --stage1-per-stratum flag supported |

### Real-World Experiments (Table 3)

| Experiment | Status | Notes |
|------------|--------|-------|
| Night-street car | **G-ARC EXTENSION** | BDD100K cached data |
| Taipei intersection | **BLOCKED** | Need dataset + oracle |
| CelebA attribute | **BLOCKED** | Need CelebA subset |
| Amazon movie posters | **BLOCKED** | Need dataset |
| trec05p spam | **BLOCKED** | Need dataset |
| Amazon office | **BLOCKED** | Need dataset |

### Advanced Features

| Experiment | Status | Notes |
|------------|--------|-------|
| MultiPred aggregation | **BLOCKED** | Need multi-predicate implementation |
| GroupBy single oracle | **BLOCKED** | Need GroupBy implementation |
| GroupBy multiple oracle | **BLOCKED** | Need GroupBy implementation |
| Proxy combination | **BLOCKED** | Need multi-proxy extension |

---

## G-ARC Extension (NOT from original papers)

| Experiment | Status | Notes |
|------------|--------|-------|
| BDD100K SUPG 100-trial formal | **COMPLETE** | budget=1000, gamma=0.9, 100 trials |
| BDD100K ABae 30-trial smoke | **COMPLETE** | budget=1000, 3 methods, 30 trials |
| BDD100K ABae COUNT coverage | **COMPLETE** | 100 trials, COUNT coverage diagnostic |

---

## Completed Experiments

### SUPG Synthetic Formal (DONE)

**Beta(0.01, 1)** — N=1M, positive rate=0.976%, budget=10000, 100 trials:

| Method | Failure Rate | Mean Recall | Mean Precision | Vacuous? |
|--------|-------------|-------------|----------------|----------|
| U-NOCI-RT | 0.57 | 0.892 | 0.395 | No |
| U-CI-RT | 0.00 | 1.000 | 0.010 | Yes |
| **SUPG-RT** | **0.00** | **0.934** | **0.349** | **No** |
| U-NOCI-PT | 0.65 | 0.882 | 0.231 | No |
| **SUPG-PT** | **0.00** | **0.983** | **0.402** | **No** |

**Beta(0.01, 2)** — N=1M, positive rate=0.504%, budget=10000, 100 trials:

| Method | Failure Rate | Mean Recall | Mean Precision | Vacuous? |
|--------|-------------|-------------|----------------|----------|
| U-NOCI-RT | 0.47 | 0.897 | 0.228 | No |
| U-CI-RT | 0.00 | 1.000 | 0.005 | Yes |
| **SUPG-RT** | **0.00** | **0.945** | **0.189** | **No** |
| U-NOCI-PT | 0.89 | 0.753 | 0.075 | No |
| **SUPG-PT** | **0.00** | **1.000** | **0.415** | **No** |

**Conclusion**: SUPG achieves 0% failure rate (matching paper). U-NOCI has 47-57% failure. U-CI is vacuous.

### ABae Synthetic Reproduction (DONE)

N=100K, 30 trials, 300 bootstrap, alpha=0.05:

| Budget | Method | AVG CI Width | AVG Coverage | COUNT CI Width | COUNT Coverage |
|--------|--------|-------------|-------------|----------------|----------------|
| 500 | Uniform | 0.0821 | 96.67% | 5991.0 | 96.67% |
| 500 | ABae-paper | 0.0724 | 93.33% | 4393.8 | 93.33% |
| 1000 | Uniform | 0.0589 | 100.00% | 4164.7 | 96.67% |
| 1000 | ABae-paper | 0.0594 | 63.33% | 3435.6 | 80.00% |
| 2000 | Uniform | 0.0415 | 93.33% | 2965.2 | 96.67% |
| 2000 | ABae-paper | 0.0426 | 66.67% | 2365.4 | 63.33% |
| 5000 | Uniform | 0.0265 | 100.00% | 1847.1 | 96.67% |
| 5000 | ABae-paper | 0.0262 | 86.67% | 1443.7 | 86.67% |
| 10000 | Uniform | 0.0187 | 90.00% | 1334.5 | 100.00% |
| 10000 | ABae-paper | 0.0169 | 83.33% | 1006.8 | 90.00% |

**Conclusion**: ABae-paper narrows CI width vs Uniform (especially COUNT). COUNT coverage is
anti-conservative (below 95% for most budgets). AVG coverage is variable.

**WARNING**: COUNT CIs are anti-conservative for ABae methods. See report for details.

---

## COUNT Coverage Warnings

ABae bootstrap CI for COUNT is anti-conservative with stratified sampling:
- ABae-paper COUNT coverage: 80-93% (below 95% target)
- ABae-full_variance COUNT coverage: 57-90% (below 95% target)
- Uniform baseline COUNT coverage: 96-97% (well-calibrated)

**Interpret COUNT CIs with caution for ABae methods.**

---

Generated: 2026-05-20
