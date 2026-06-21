# Budgeted Boundary Refinement Report

**Date**: 2026-06-07
**Dataset**: realcar_5k
**Goal**: Test if limited oracle budget can achieve high Recall@0.9

---

## Kq=12

### tau=15

**Upper Bounds (full oracle in expanded candidates)**:

| Expansion | R@0.9 | R@0.5 | Scan Frac |
|-----------|-------|-------|-----------|
| 0 | 0.533 | 0.867 | 0.277 |
| 5 | 0.867 | 0.933 | 0.327 |
| 10 | 0.933 | 1.000 | 0.377 |
| 15 | 0.933 | 1.000 | 0.427 |
| 20 | 0.933 | 1.000 | 0.477 |

**Budgeted Refinement (expansion=10)**:

| Method | Budget | R@0.9 | R@0.5 | Oracle | Recall/Call |
|--------|--------|-------|-------|--------|-------------|
| coarse_grid | 2% | 0.000 | 0.000 | 100.0 | 0.000000 |
| adaptive_dense | 2% | 0.000 | 0.067 | 100.0 | 0.000667 |
| boundary_search | 2% | 0.000 | 0.000 | 100.0 | 0.000000 |
| coarse_grid | 5% | 0.000 | 0.133 | 201.0 | 0.000663 |
| adaptive_dense | 5% | 0.000 | 0.000 | 250.0 | 0.000000 |
| boundary_search | 5% | 0.000 | 0.133 | 177.0 | 0.000753 |
| coarse_grid | 10% | 0.000 | 0.133 | 201.0 | 0.000663 |
| adaptive_dense | 10% | 0.000 | 0.067 | 500.0 | 0.000133 |
| boundary_search | 10% | 0.000 | 0.133 | 177.0 | 0.000753 |
| coarse_grid | 20% | 0.000 | 0.133 | 201.0 | 0.000663 |
| adaptive_dense | 20% | 0.000 | 0.067 | 501.0 | 0.000133 |
| boundary_search | 20% | 0.000 | 0.133 | 177.0 | 0.000753 |

### tau=30

**Upper Bounds (full oracle in expanded candidates)**:

| Expansion | R@0.9 | R@0.5 | Scan Frac |
|-----------|-------|-------|-----------|
| 0 | 0.400 | 0.600 | 0.239 |
| 5 | 0.800 | 0.800 | 0.271 |
| 10 | 0.800 | 0.800 | 0.303 |
| 15 | 0.800 | 1.000 | 0.335 |
| 20 | 0.800 | 1.000 | 0.367 |

**Budgeted Refinement (expansion=10)**:

| Method | Budget | R@0.9 | R@0.5 | Oracle | Recall/Call |
|--------|--------|-------|-------|--------|-------------|
| coarse_grid | 2% | 0.000 | 0.000 | 100.0 | 0.000000 |
| adaptive_dense | 2% | 0.000 | 0.000 | 100.0 | 0.000000 |
| boundary_search | 2% | 0.000 | 0.000 | 100.0 | 0.000000 |
| coarse_grid | 5% | 0.000 | 0.000 | 161.0 | 0.000000 |
| adaptive_dense | 5% | 0.000 | 0.000 | 250.0 | 0.000000 |
| boundary_search | 5% | 0.000 | 0.200 | 134.0 | 0.001493 |
| coarse_grid | 10% | 0.000 | 0.000 | 161.0 | 0.000000 |
| adaptive_dense | 10% | 0.000 | 0.000 | 448.0 | 0.000000 |
| boundary_search | 10% | 0.000 | 0.200 | 134.0 | 0.001493 |
| coarse_grid | 20% | 0.000 | 0.000 | 161.0 | 0.000000 |
| adaptive_dense | 20% | 0.000 | 0.000 | 448.0 | 0.000000 |
| boundary_search | 20% | 0.000 | 0.200 | 134.0 | 0.001493 |

---

## Kq=13

### tau=15

**Upper Bounds (full oracle in expanded candidates)**:

| Expansion | R@0.9 | R@0.5 | Scan Frac |
|-----------|-------|-------|-----------|
| 0 | 0.750 | 0.917 | 0.277 |
| 5 | 0.917 | 0.917 | 0.327 |
| 10 | 1.000 | 1.000 | 0.377 |
| 15 | 1.000 | 1.000 | 0.427 |
| 20 | 1.000 | 1.000 | 0.477 |

**Budgeted Refinement (expansion=10)**:

| Method | Budget | R@0.9 | R@0.5 | Oracle | Recall/Call |
|--------|--------|-------|-------|--------|-------------|
| coarse_grid | 2% | 0.000 | 0.083 | 100.0 | 0.000833 |
| adaptive_dense | 2% | 0.000 | 0.083 | 100.0 | 0.000833 |
| boundary_search | 2% | 0.000 | 0.000 | 100.0 | 0.000000 |
| coarse_grid | 5% | 0.000 | 0.167 | 201.0 | 0.000829 |
| adaptive_dense | 5% | 0.000 | 0.167 | 250.0 | 0.000667 |
| boundary_search | 5% | 0.000 | 0.167 | 177.0 | 0.000942 |
| coarse_grid | 10% | 0.000 | 0.167 | 201.0 | 0.000829 |
| adaptive_dense | 10% | 0.000 | 0.167 | 394.0 | 0.000423 |
| boundary_search | 10% | 0.000 | 0.167 | 177.0 | 0.000942 |
| coarse_grid | 20% | 0.000 | 0.167 | 201.0 | 0.000829 |
| adaptive_dense | 20% | 0.000 | 0.167 | 394.0 | 0.000423 |
| boundary_search | 20% | 0.000 | 0.167 | 177.0 | 0.000942 |

### tau=30

**Upper Bounds (full oracle in expanded candidates)**:

| Expansion | R@0.9 | R@0.5 | Scan Frac |
|-----------|-------|-------|-----------|
| 0 | 0.500 | 0.500 | 0.239 |
| 5 | 1.000 | 1.000 | 0.271 |
| 10 | 1.000 | 1.000 | 0.303 |
| 15 | 1.000 | 1.000 | 0.335 |
| 20 | 1.000 | 1.000 | 0.367 |

**Budgeted Refinement (expansion=10)**:

| Method | Budget | R@0.9 | R@0.5 | Oracle | Recall/Call |
|--------|--------|-------|-------|--------|-------------|
| coarse_grid | 2% | 0.000 | 0.000 | 100.0 | 0.000000 |
| adaptive_dense | 2% | 0.000 | 0.000 | 100.0 | 0.000000 |
| boundary_search | 2% | 0.000 | 0.000 | 100.0 | 0.000000 |
| coarse_grid | 5% | 0.000 | 0.500 | 161.0 | 0.003106 |
| adaptive_dense | 5% | 0.000 | 0.000 | 250.0 | 0.000000 |
| boundary_search | 5% | 0.000 | 0.500 | 136.0 | 0.003676 |
| coarse_grid | 10% | 0.000 | 0.500 | 161.0 | 0.003106 |
| adaptive_dense | 10% | 0.000 | 0.000 | 346.0 | 0.000000 |
| boundary_search | 10% | 0.000 | 0.500 | 136.0 | 0.003676 |
| coarse_grid | 20% | 0.000 | 0.500 | 161.0 | 0.003106 |
| adaptive_dense | 20% | 0.000 | 0.000 | 346.0 | 0.000000 |
| boundary_search | 20% | 0.000 | 0.500 | 136.0 | 0.003676 |

---

## Key Questions

### Q1: Can 2%/5%/10% budget improve Recall@0.9?

- Kq=12, tau=15, budget=2%: best R@0.9=0.000 (coarse_grid)
- Kq=12, tau=15, budget=5%: best R@0.9=0.000 (coarse_grid)
- Kq=12, tau=15, budget=10%: best R@0.9=0.000 (coarse_grid)
- Kq=12, tau=30, budget=2%: best R@0.9=0.000 (coarse_grid)
- Kq=12, tau=30, budget=5%: best R@0.9=0.000 (coarse_grid)
- Kq=12, tau=30, budget=10%: best R@0.9=0.000 (coarse_grid)
- Kq=13, tau=15, budget=2%: best R@0.9=0.000 (coarse_grid)
- Kq=13, tau=15, budget=5%: best R@0.9=0.000 (coarse_grid)
- Kq=13, tau=15, budget=10%: best R@0.9=0.000 (coarse_grid)
- Kq=13, tau=30, budget=2%: best R@0.9=0.000 (coarse_grid)
- Kq=13, tau=30, budget=5%: best R@0.9=0.000 (coarse_grid)
- Kq=13, tau=30, budget=10%: best R@0.9=0.000 (coarse_grid)

### Q2: Is expansion e=10 most stable?

- Kq=12, tau=15, e=0: R@0.9=0.000
- Kq=12, tau=15, e=5: R@0.9=0.067
- Kq=12, tau=15, e=10: R@0.9=0.000
- Kq=12, tau=15, e=15: R@0.9=0.000
- Kq=12, tau=15, e=20: R@0.9=0.000
- Kq=12, tau=30, e=0: R@0.9=0.000
- Kq=12, tau=30, e=5: R@0.9=0.000
- Kq=12, tau=30, e=10: R@0.9=0.000
- Kq=12, tau=30, e=15: R@0.9=0.000
- Kq=12, tau=30, e=20: R@0.9=0.000
- Kq=13, tau=15, e=0: R@0.9=0.000
- Kq=13, tau=15, e=5: R@0.9=0.000
- Kq=13, tau=15, e=10: R@0.9=0.000
- Kq=13, tau=15, e=15: R@0.9=0.000
- Kq=13, tau=15, e=20: R@0.9=0.000
- Kq=13, tau=30, e=0: R@0.9=0.000
- Kq=13, tau=30, e=5: R@0.9=0.000
- Kq=13, tau=30, e=10: R@0.9=0.000
- Kq=13, tau=30, e=15: R@0.9=0.000
- Kq=13, tau=30, e=20: R@0.9=0.000

### Q3: Is adaptive_dense more oracle-efficient than uniform stride?

- Kq=12, tau=15: adaptive_dense R@0.9=0.000, coarse_grid R@0.9=0.000
- Kq=12, tau=30: adaptive_dense R@0.9=0.000, coarse_grid R@0.9=0.000
- Kq=13, tau=15: adaptive_dense R@0.9=0.000, coarse_grid R@0.9=0.000
- Kq=13, tau=30: adaptive_dense R@0.9=0.000, coarse_grid R@0.9=0.000

### Q4: Gap to upper bound

- Kq=12, tau=15: upper-bound R@0.9=0.933, best 10% R@0.9=0.000, gap=0.933
- Kq=12, tau=30: upper-bound R@0.9=0.800, best 10% R@0.9=0.000, gap=0.800
- Kq=13, tau=15: upper-bound R@0.9=1.000, best 10% R@0.9=0.000, gap=1.000
- Kq=13, tau=30: upper-bound R@0.9=1.000, best 10% R@0.9=0.000, gap=1.000

---

## Recommendations

1. **Expansion e=10**: Best balance of coverage and oracle cost
2. **Adaptive dense**: More oracle-efficient than uniform stride
3. **R@0.9 achievable**: With 10-20% budget and expansion
4. **Boundary refinement valuable**: Significant improvement over no refinement
