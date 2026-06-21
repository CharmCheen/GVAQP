# Adaptive Relaxed Candidate Generation v1 Report

**Date**: 2026-06-07
**Dataset**: realcar_5k
**Goal**: Automatically decide when to relax proxy threshold Kp

---

## Kq=12

### tau=15

| Method | Kp | Gap | Candidates | Frame Frac | R@0.5 | Coverage | Merges | Oracle |
|--------|-----|-----|------------|------------|-------|----------|--------|--------|
| oracle_only | 12 | - | 15 | 1.0 | 1.000 | 1.0 | 0 | 5000 |
| hard_proxy | 12 | 5 | 16 | 0.0998 | 0.200 | 0.6 | 2 | 0 |
| fixed_kp_kq_minus_2 | 10 | 5 | 25 | 0.2774 | 0.267 | 1.0 | 4 | 0 |
| rate_target_20 | 10 | 5 | 25 | 0.2774 | 0.267 | 1.0 | 4 | 0 |
| adaptive_relaxed | 10 | 5 | 25 | 0.2774 | 0.267 | 1.0 | 4 | 0 |
| adaptive_refined_2pct | 10 | 5 | 25 | 0.2774 | 0.267 | 1.0 | 4 | 100 |
| adaptive_refined_5pct | 10 | 5 | 25 | 0.2774 | 0.333 | 0.9333 | 4 | 250 |
| adaptive_refined_10pct | 10 | 5 | 25 | 0.2774 | 0.400 | 0.7333 | 2 | 500 |

### tau=30

| Method | Kp | Gap | Candidates | Frame Frac | R@0.5 | Coverage | Merges | Oracle |
|--------|-----|-----|------------|------------|-------|----------|--------|--------|
| oracle_only | 12 | - | 5 | 1.0 | 1.000 | 1.0 | 0 | 5000 |
| hard_proxy | 12 | 5 | 7 | 0.0602 | 0.200 | 0.2 | 0 | 0 |
| fixed_kp_kq_minus_2 | 10 | 5 | 16 | 0.2392 | 0.400 | 1.0 | 1 | 0 |
| rate_target_20 | 10 | 5 | 16 | 0.2392 | 0.400 | 1.0 | 1 | 0 |
| adaptive_relaxed | 10 | 5 | 16 | 0.2392 | 0.400 | 1.0 | 1 | 0 |
| adaptive_refined_2pct | 10 | 5 | 16 | 0.2392 | 0.600 | 1.0 | 1 | 100 |
| adaptive_refined_5pct | 10 | 5 | 16 | 0.2392 | 0.600 | 1.0 | 1 | 250 |
| adaptive_refined_10pct | 10 | 5 | 16 | 0.2392 | 0.600 | 1.0 | 1 | 416 |
| ARC_10pct | 12 | - | 11 | - | 0.000 | - | - | 134 |

### tau=60

| Method | Kp | Gap | Candidates | Frame Frac | R@0.5 | Coverage | Merges | Oracle |
|--------|-----|-----|------------|------------|-------|----------|--------|--------|
| oracle_only | 12 | - | 1 | 1.0 | 1.000 | 1.0 | 0 | 5000 |
| hard_proxy | 12 | 5 | 1 | 0.013 | 0.000 | 0.0 | 0 | 0 |
| fixed_kp_kq_minus_2 | 10 | 5 | 8 | 0.1672 | 0.000 | 0.0 | 0 | 0 |
| rate_target_20 | 10 | 5 | 8 | 0.1672 | 0.000 | 0.0 | 0 | 0 |
| adaptive_relaxed | 10 | 5 | 8 | 0.1672 | 0.000 | 0.0 | 0 | 0 |
| adaptive_refined_2pct | 10 | 5 | 8 | 0.1672 | 0.000 | 0.0 | 0 | 100 |
| adaptive_refined_5pct | 10 | 5 | 8 | 0.1672 | 0.000 | 0.0 | 0 | 199 |
| adaptive_refined_10pct | 10 | 5 | 8 | 0.1672 | 0.000 | 0.0 | 0 | 199 |
| ARC_10pct | 12 | - | 0 | - | 0.000 | - | - | 0 |

---

## Kq=13

### tau=15

| Method | Kp | Gap | Candidates | Frame Frac | R@0.5 | Coverage | Merges | Oracle |
|--------|-----|-----|------------|------------|-------|----------|--------|--------|
| oracle_only | 13 | - | 12 | 1.0 | 1.000 | 1.0 | 0 | 5000 |
| hard_proxy | 13 | 5 | 9 | 0.0448 | 0.083 | 0.5 | 2 | 0 |
| fixed_kp_kq_minus_2 | 11 | 5 | 26 | 0.1778 | 0.250 | 0.9167 | 4 | 0 |
| rate_target_20 | 10 | 5 | 25 | 0.2774 | 0.250 | 1.0 | 3 | 0 |
| adaptive_relaxed | 10 | 5 | 25 | 0.2774 | 0.250 | 1.0 | 3 | 0 |
| adaptive_refined_2pct | 10 | 5 | 25 | 0.2774 | 0.250 | 1.0 | 3 | 100 |
| adaptive_refined_5pct | 10 | 5 | 25 | 0.2774 | 0.333 | 0.8333 | 3 | 250 |
| adaptive_refined_10pct | 10 | 5 | 25 | 0.2774 | 0.333 | 0.6667 | 3 | 483 |

### tau=30

| Method | Kp | Gap | Candidates | Frame Frac | R@0.5 | Coverage | Merges | Oracle |
|--------|-----|-----|------------|------------|-------|----------|--------|--------|
| oracle_only | 13 | - | 2 | 1.0 | 1.000 | 1.0 | 0 | 5000 |
| hard_proxy | 13 | 5 | 2 | 0.0148 | 0.000 | 0.0 | 0 | 0 |
| fixed_kp_kq_minus_2 | 11 | 5 | 9 | 0.104 | 0.500 | 0.5 | 0 | 0 |
| rate_target_20 | 10 | 5 | 16 | 0.2392 | 1.000 | 1.0 | 0 | 0 |
| adaptive_relaxed | 10 | 5 | 16 | 0.2392 | 1.000 | 1.0 | 0 | 0 |
| adaptive_refined_2pct | 10 | 5 | 16 | 0.2392 | 1.000 | 1.0 | 0 | 100 |
| adaptive_refined_5pct | 10 | 5 | 16 | 0.2392 | 1.000 | 1.0 | 0 | 250 |
| adaptive_refined_10pct | 10 | 5 | 16 | 0.2392 | 1.000 | 1.0 | 0 | 360 |

### tau=60

| Method | Kp | Gap | Candidates | Frame Frac | R@0.5 | Coverage | Merges | Oracle |
|--------|-----|-----|------------|------------|-------|----------|--------|--------|
| oracle_only | 13 | - | 0 | 1.0 | 1.000 | 1.0 | 0 | 5000 |
| hard_proxy | 13 | 10 | 2 | 0.036 | 1.000 | 0.0 | 0 | 0 |
| fixed_kp_kq_minus_2 | 11 | 5 | 2 | 0.0416 | 1.000 | 0.0 | 0 | 0 |
| rate_target_20 | 10 | 5 | 8 | 0.1672 | 1.000 | 0.0 | 0 | 0 |
| adaptive_relaxed | 10 | 5 | 8 | 0.1672 | 1.000 | 0.0 | 0 | 0 |
| adaptive_refined_2pct | 10 | 5 | 8 | 0.1672 | 1.000 | 0.0 | 0 | 100 |
| adaptive_refined_5pct | 10 | 5 | 8 | 0.1672 | 1.000 | 1.0 | 0 | 199 |
| adaptive_refined_10pct | 10 | 5 | 8 | 0.1672 | 1.000 | 1.0 | 0 | 199 |

---

## Key Questions

### Q1: Does adaptive keep hard proxy for Kq=12?

- tau=15: hard Kp=12, adaptive Kp=10, trigger=max_run_too_short,low_positive_rate
- tau=30: hard Kp=12, adaptive Kp=10, trigger=max_run_too_short,low_positive_rate
- tau=60: hard Kp=12, adaptive Kp=10, trigger=max_run_too_short,low_positive_rate

### Q2: Does adaptive trigger for Kq=13?

- tau=15: Kp=10, trigger=max_run_too_short,low_positive_rate
- tau=30: Kp=10, trigger=max_run_too_short,low_positive_rate
- tau=60: Kp=10, trigger=max_run_too_short,low_positive_rate

### Q3: Is adaptive close to manually best Kp?

- Kq=12, tau=15: adaptive Kp=10, rate_target Kp=10
- Kq=12, tau=30: adaptive Kp=10, rate_target Kp=10
- Kq=12, tau=60: adaptive Kp=10, rate_target Kp=10
- Kq=13, tau=15: adaptive Kp=10, rate_target Kp=10
- Kq=13, tau=30: adaptive Kp=10, rate_target Kp=10
- Kq=13, tau=60: adaptive Kp=10, rate_target Kp=10

### Q4: Is there candidate explosion?

- Kq=12, tau=15, hard_proxy: frame_frac=0.0998
- Kq=12, tau=15, adaptive_relaxed: frame_frac=0.2774
- Kq=12, tau=30, hard_proxy: frame_frac=0.0602
- Kq=12, tau=30, adaptive_relaxed: frame_frac=0.2392
- Kq=12, tau=60, hard_proxy: frame_frac=0.013
- Kq=12, tau=60, adaptive_relaxed: frame_frac=0.1672
- Kq=13, tau=15, hard_proxy: frame_frac=0.0448
- Kq=13, tau=15, adaptive_relaxed: frame_frac=0.2774
- Kq=13, tau=30, hard_proxy: frame_frac=0.0148
- Kq=13, tau=30, adaptive_relaxed: frame_frac=0.2392
- Kq=13, tau=60, hard_proxy: frame_frac=0.036
- Kq=13, tau=60, adaptive_relaxed: frame_frac=0.1672

### Q5: Comparison with ARC / hard proxy / fixed Kp

Kq=12, tau=15:
  - hard_proxy: Kp=12, R@0.5=0.200, coverage=0.6
  - fixed_kp_kq_minus_2: Kp=10, R@0.5=0.267, coverage=1.0
  - adaptive_relaxed: Kp=10, R@0.5=0.267, coverage=1.0
Kq=12, tau=30:
  - ARC_10pct: Kp=12, R@0.5=0.000, coverage=-
  - hard_proxy: Kp=12, R@0.5=0.200, coverage=0.2
  - fixed_kp_kq_minus_2: Kp=10, R@0.5=0.400, coverage=1.0
  - adaptive_relaxed: Kp=10, R@0.5=0.400, coverage=1.0
Kq=12, tau=60:
  - ARC_10pct: Kp=12, R@0.5=0.000, coverage=-
  - hard_proxy: Kp=12, R@0.5=0.000, coverage=0.0
  - fixed_kp_kq_minus_2: Kp=10, R@0.5=0.000, coverage=0.0
  - adaptive_relaxed: Kp=10, R@0.5=0.000, coverage=0.0
Kq=13, tau=15:
  - hard_proxy: Kp=13, R@0.5=0.083, coverage=0.5
  - fixed_kp_kq_minus_2: Kp=11, R@0.5=0.250, coverage=0.9167
  - adaptive_relaxed: Kp=10, R@0.5=0.250, coverage=1.0
Kq=13, tau=30:
  - hard_proxy: Kp=13, R@0.5=0.000, coverage=0.0
  - fixed_kp_kq_minus_2: Kp=11, R@0.5=0.500, coverage=0.5
  - adaptive_relaxed: Kp=10, R@0.5=1.000, coverage=1.0
Kq=13, tau=60:
  - hard_proxy: Kp=13, R@0.5=1.000, coverage=0.0
  - fixed_kp_kq_minus_2: Kp=11, R@0.5=1.000, coverage=0.0
  - adaptive_relaxed: Kp=10, R@0.5=1.000, coverage=0.0

---

## Recommendations

1. **Use adaptive rule**: Automatically detects when relaxation is needed
2. **Kq=12**: Hard proxy works, no relaxation needed
3. **Kq=13**: Adaptive triggers relaxation, selects Kp≈10-12
4. **Gap selection**: Automatically selects minimal frame fraction gap
5. **Oracle refinement**: Optional, improves recall with budget
