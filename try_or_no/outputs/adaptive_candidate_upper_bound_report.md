# Adaptive Candidate Upper Bound Analysis Report

**Date**: 2026-06-07
**Dataset**: realcar_5k
**Goal**: Determine if adaptive candidates theoretically support strict IoU@0.9

---

## Kq=12

### tau=15

| Method | Cand Count | Frame Frac | Scan Frac | R@0.9 | R@0.7 | R@0.5 | mIoU | Coverage |
|--------|------------|------------|-----------|-------|-------|-------|------|----------|
| full_oracle | 15 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| oracle_in_candidates | 25 | 0.277 | 0.277 | 0.533 | 0.867 | 0.867 | 0.833 | 0.933 |
| oracle_in_expanded | 25 | 0.277 | 0.377 | 0.933 | 0.933 | 1.000 | 0.975 | 1.000 |
| hard_proxy | 16 | 0.100 | 0.000 | 0.000 | 0.067 | 0.200 | 0.243 | 0.600 |
| adaptive_no_oracle | 25 | 0.277 | 0.000 | 0.000 | 0.200 | 0.267 | 0.347 | 1.000 |

### tau=30

| Method | Cand Count | Frame Frac | Scan Frac | R@0.9 | R@0.7 | R@0.5 | mIoU | Coverage |
|--------|------------|------------|-----------|-------|-------|-------|------|----------|
| full_oracle | 5 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| oracle_in_candidates | 16 | 0.239 | 0.239 | 0.400 | 0.600 | 0.600 | 0.563 | 0.600 |
| oracle_in_expanded | 16 | 0.239 | 0.303 | 0.800 | 0.800 | 0.800 | 0.800 | 0.800 |
| hard_proxy | 7 | 0.060 | 0.000 | 0.000 | 0.000 | 0.200 | 0.105 | 0.200 |
| adaptive_no_oracle | 16 | 0.239 | 0.000 | 0.000 | 0.200 | 0.400 | 0.459 | 1.000 |

### tau=60

| Method | Cand Count | Frame Frac | Scan Frac | R@0.9 | R@0.7 | R@0.5 | mIoU | Coverage |
|--------|------------|------------|-----------|-------|-------|-------|------|----------|
| full_oracle | 1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| oracle_in_candidates | 8 | 0.167 | 0.167 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| oracle_in_expanded | 8 | 0.167 | 0.199 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| hard_proxy | 1 | 0.013 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| adaptive_no_oracle | 8 | 0.167 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

---

## Kq=13

### tau=15

| Method | Cand Count | Frame Frac | Scan Frac | R@0.9 | R@0.7 | R@0.5 | mIoU | Coverage |
|--------|------------|------------|-----------|-------|-------|-------|------|----------|
| full_oracle | 12 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| oracle_in_candidates | 25 | 0.277 | 0.277 | 0.750 | 0.917 | 0.917 | 0.877 | 0.917 |
| oracle_in_expanded | 25 | 0.277 | 0.377 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hard_proxy | 9 | 0.045 | 0.000 | 0.000 | 0.083 | 0.083 | 0.163 | 0.500 |
| adaptive_no_oracle | 25 | 0.277 | 0.000 | 0.000 | 0.083 | 0.250 | 0.308 | 1.000 |

### tau=30

| Method | Cand Count | Frame Frac | Scan Frac | R@0.9 | R@0.7 | R@0.5 | mIoU | Coverage |
|--------|------------|------------|-----------|-------|-------|-------|------|----------|
| full_oracle | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| oracle_in_candidates | 16 | 0.239 | 0.239 | 0.500 | 0.500 | 0.500 | 0.471 | 0.500 |
| oracle_in_expanded | 16 | 0.239 | 0.303 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hard_proxy | 2 | 0.015 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| adaptive_no_oracle | 16 | 0.239 | 0.000 | 0.000 | 0.000 | 1.000 | 0.628 | 1.000 |

### tau=60

| Method | Cand Count | Frame Frac | Scan Frac | R@0.9 | R@0.7 | R@0.5 | mIoU | Coverage |
|--------|------------|------------|-----------|-------|-------|-------|------|----------|
| full_oracle | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| oracle_in_candidates | 8 | 0.167 | 0.167 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| oracle_in_expanded | 8 | 0.167 | 0.199 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| hard_proxy | 0 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| adaptive_no_oracle | 8 | 0.167 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 |

---

## Key Questions

### Q1: Do adaptive candidates contain enough information for strict IoU@0.9?

- Kq=12, tau=15: oracle-in-candidates R@0.9=0.533, R@0.5=0.867, coverage=0.933
- Kq=12, tau=30: oracle-in-candidates R@0.9=0.400, R@0.5=0.600, coverage=0.600
- Kq=12, tau=60: oracle-in-candidates R@0.9=0.000, R@0.5=0.000, coverage=0.000
- Kq=13, tau=15: oracle-in-candidates R@0.9=0.750, R@0.5=0.917, coverage=0.917
- Kq=13, tau=30: oracle-in-candidates R@0.9=0.500, R@0.5=0.500, coverage=0.500
- Kq=13, tau=60: oracle-in-candidates R@0.9=1.000, R@0.5=1.000, coverage=1.000

### Q2: If R@0.9=0 with full oracle, is it candidate structure or GT semantics?

- Kq=12, tau=15: oracle-in-candidates R@0.9=0.533, full-oracle R@0.9=1.000
  → Candidates contain enough info, refinement can work
- Kq=12, tau=30: oracle-in-candidates R@0.9=0.400, full-oracle R@0.9=1.000
  → Candidates contain enough info, refinement can work
- Kq=12, tau=60: oracle-in-candidates R@0.9=0.000, full-oracle R@0.9=1.000
  → Candidate structure issue: candidates miss GT clips
- Kq=13, tau=15: oracle-in-candidates R@0.9=0.750, full-oracle R@0.9=1.000
  → Candidates contain enough info, refinement can work
- Kq=13, tau=30: oracle-in-candidates R@0.9=0.500, full-oracle R@0.9=1.000
  → Candidates contain enough info, refinement can work
- Kq=13, tau=60: oracle-in-candidates R@0.9=1.000, full-oracle R@0.9=1.000
  → Candidates contain enough info, refinement can work

### Q3: Upper bound vs current refinement

- Kq=12, tau=15: adaptive R@0.5=0.267, upper-bound R@0.5=0.867
- Kq=12, tau=30: adaptive R@0.5=0.400, upper-bound R@0.5=0.600
- Kq=12, tau=60: adaptive R@0.5=0.000, upper-bound R@0.5=0.000
- Kq=13, tau=15: adaptive R@0.5=0.250, upper-bound R@0.5=0.917
- Kq=13, tau=30: adaptive R@0.5=1.000, upper-bound R@0.5=0.500
- Kq=13, tau=60: adaptive R@0.5=1.000, upper-bound R@0.5=1.000

### Q4: Candidate frame fraction vs full video

- Kq=12, tau=15: candidate fraction=0.277, oracle scan fraction=0.277
- Kq=12, tau=30: candidate fraction=0.239, oracle scan fraction=0.239
- Kq=12, tau=60: candidate fraction=0.167, oracle scan fraction=0.167
- Kq=13, tau=15: candidate fraction=0.277, oracle scan fraction=0.277
- Kq=13, tau=30: candidate fraction=0.239, oracle scan fraction=0.239
- Kq=13, tau=60: candidate fraction=0.167, oracle scan fraction=0.167

---

## Recommendations

1. **If upper-bound R@0.9 > 0**: Boundary refinement can potentially achieve it
2. **If upper-bound R@0.9 = 0**: Need to expand candidates or accept R@0.5 as target
3. **Candidate fraction**: Adaptive candidates cover significantly less than full video
4. **Oracle efficiency**: Scanning only candidate regions saves oracle budget
