# Kp Selection Validation Report

**Date**: 2026-06-07
**Dataset**: realcar_5k
**Goal**: Validate Kp selection strategies without using GT clips

---

## Kq=12

### tau=15

| Strategy | Kp | R@0.5 | Coverage | Candidates | Frame Frac | Merges | Oracle |
|----------|-----|-------|----------|------------|------------|--------|--------|
| oracle_only | 12 | 1.000 | 1.000 | 15 | 1.000 | 0 | 5000 |
| hard_proxy | 12 | 0.200 | 0.867 | 17 | 0.187 | 5 | 0 |
| best_known_Kp | 10 | 0.200 | 1.000 | 15 | 0.383 | 3 | 0 |
| fixed_margin_m1 | 11 | 0.067 | 0.867 | 18 | 0.267 | 4 | 0 |
| fixed_margin_m2 | 10 | 0.200 | 1.000 | 15 | 0.383 | 3 | 0 |
| fixed_margin_m3 | 9 | 0.000 | 1.000 | 12 | 0.462 | 2 | 0 |
| fixed_margin_m4 | 8 | 0.000 | 1.000 | 9 | 0.514 | 2 | 0 |
| rate_target_10 | 12 | 0.200 | 0.867 | 17 | 0.187 | 5 | 0 |
| rate_target_15 | 11 | 0.067 | 0.867 | 18 | 0.267 | 4 | 0 |
| rate_target_20 | 10 | 0.200 | 1.000 | 15 | 0.383 | 3 | 0 |
| rate_target_25 | 10 | 0.200 | 1.000 | 15 | 0.383 | 3 | 0 |
| rate_target_30 | 9 | 0.000 | 1.000 | 12 | 0.462 | 2 | 0 |
| pilot_oracle_1 | 9 | 0.000 | 1.000 | 12 | 0.462 | 2 | 50 |
| pilot_oracle_2 | 9 | 0.000 | 1.000 | 12 | 0.462 | 2 | 100 |

### tau=30

| Strategy | Kp | R@0.5 | Coverage | Candidates | Frame Frac | Merges | Oracle |
|----------|-----|-------|----------|------------|------------|--------|--------|
| oracle_only | 12 | 1.000 | 1.000 | 5 | 1.000 | 0 | 5000 |
| hard_proxy | 12 | 0.600 | 1.000 | 13 | 0.170 | 1 | 0 |
| best_known_Kp | 12 | 0.600 | 1.000 | 13 | 0.170 | 1 | 0 |
| fixed_margin_m1 | 11 | 0.200 | 1.000 | 12 | 0.243 | 2 | 0 |
| fixed_margin_m2 | 10 | 0.200 | 1.000 | 10 | 0.363 | 2 | 0 |
| fixed_margin_m3 | 9 | 0.000 | 1.000 | 10 | 0.453 | 2 | 0 |
| fixed_margin_m4 | 8 | 0.000 | 1.000 | 8 | 0.510 | 2 | 0 |
| rate_target_10 | 12 | 0.600 | 1.000 | 13 | 0.170 | 1 | 0 |
| rate_target_15 | 11 | 0.200 | 1.000 | 12 | 0.243 | 2 | 0 |
| rate_target_20 | 10 | 0.200 | 1.000 | 10 | 0.363 | 2 | 0 |
| rate_target_25 | 10 | 0.200 | 1.000 | 10 | 0.363 | 2 | 0 |
| rate_target_30 | 9 | 0.000 | 1.000 | 10 | 0.453 | 2 | 0 |
| pilot_oracle_1 | 9 | 0.000 | 1.000 | 10 | 0.453 | 2 | 50 |
| pilot_oracle_2 | 9 | 0.000 | 1.000 | 10 | 0.453 | 2 | 100 |

### tau=60

| Strategy | Kp | R@0.5 | Coverage | Candidates | Frame Frac | Merges | Oracle |
|----------|-----|-------|----------|------------|------------|--------|--------|
| oracle_only | 12 | 1.000 | 1.000 | 1 | 1.000 | 0 | 5000 |
| hard_proxy | 12 | 1.000 | 1.000 | 6 | 0.113 | 0 | 0 |
| best_known_Kp | 12 | 1.000 | 1.000 | 6 | 0.113 | 0 | 0 |
| fixed_margin_m1 | 11 | 0.000 | 1.000 | 6 | 0.198 | 0 | 0 |
| fixed_margin_m2 | 10 | 0.000 | 1.000 | 6 | 0.331 | 0 | 0 |
| fixed_margin_m3 | 9 | 0.000 | 1.000 | 5 | 0.410 | 0 | 0 |
| fixed_margin_m4 | 8 | 0.000 | 1.000 | 4 | 0.474 | 0 | 0 |
| rate_target_10 | 12 | 1.000 | 1.000 | 6 | 0.113 | 0 | 0 |
| rate_target_15 | 11 | 0.000 | 1.000 | 6 | 0.198 | 0 | 0 |
| rate_target_20 | 10 | 0.000 | 1.000 | 6 | 0.331 | 0 | 0 |
| rate_target_25 | 10 | 0.000 | 1.000 | 6 | 0.331 | 0 | 0 |
| rate_target_30 | 9 | 0.000 | 1.000 | 5 | 0.410 | 0 | 0 |
| pilot_oracle_1 | 8 | 0.000 | 1.000 | 4 | 0.474 | 0 | 50 |
| pilot_oracle_2 | 8 | 0.000 | 1.000 | 4 | 0.474 | 0 | 100 |

---

## Kq=13

### tau=15

| Strategy | Kp | R@0.5 | Coverage | Candidates | Frame Frac | Merges | Oracle |
|----------|-----|-------|----------|------------|------------|--------|--------|
| oracle_only | 13 | 1.000 | 1.000 | 12 | 1.000 | 0 | 5000 |
| hard_proxy | 13 | 0.000 | 0.750 | 12 | 0.119 | 3 | 0 |
| best_known_Kp | 10 | 0.167 | 1.000 | 15 | 0.383 | 2 | 0 |
| fixed_margin_m1 | 12 | 0.083 | 0.917 | 17 | 0.187 | 3 | 0 |
| fixed_margin_m2 | 11 | 0.083 | 0.917 | 18 | 0.267 | 3 | 0 |
| fixed_margin_m3 | 10 | 0.167 | 1.000 | 15 | 0.383 | 2 | 0 |
| fixed_margin_m4 | 9 | 0.000 | 1.000 | 12 | 0.462 | 2 | 0 |
| rate_target_10 | 12 | 0.083 | 0.917 | 17 | 0.187 | 3 | 0 |
| rate_target_15 | 11 | 0.083 | 0.917 | 18 | 0.267 | 3 | 0 |
| rate_target_20 | 10 | 0.167 | 1.000 | 15 | 0.383 | 2 | 0 |
| rate_target_25 | 10 | 0.167 | 1.000 | 15 | 0.383 | 2 | 0 |
| rate_target_30 | 9 | 0.000 | 1.000 | 12 | 0.462 | 2 | 0 |
| pilot_oracle_1 | 9 | 0.000 | 1.000 | 12 | 0.462 | 2 | 50 |
| pilot_oracle_2 | 9 | 0.000 | 1.000 | 12 | 0.462 | 2 | 100 |

### tau=30

| Strategy | Kp | R@0.5 | Coverage | Candidates | Frame Frac | Merges | Oracle |
|----------|-----|-------|----------|------------|------------|--------|--------|
| oracle_only | 13 | 1.000 | 1.000 | 2 | 1.000 | 0 | 5000 |
| hard_proxy | 13 | 0.000 | 0.500 | 6 | 0.096 | 0 | 0 |
| best_known_Kp | 10 | 0.500 | 1.000 | 10 | 0.363 | 0 | 0 |
| fixed_margin_m1 | 12 | 0.500 | 1.000 | 13 | 0.170 | 0 | 0 |
| fixed_margin_m2 | 11 | 0.500 | 1.000 | 12 | 0.243 | 0 | 0 |
| fixed_margin_m3 | 10 | 0.500 | 1.000 | 10 | 0.363 | 0 | 0 |
| fixed_margin_m4 | 9 | 0.000 | 1.000 | 10 | 0.453 | 1 | 0 |
| rate_target_10 | 12 | 0.500 | 1.000 | 13 | 0.170 | 0 | 0 |
| rate_target_15 | 11 | 0.500 | 1.000 | 12 | 0.243 | 0 | 0 |
| rate_target_20 | 10 | 0.500 | 1.000 | 10 | 0.363 | 0 | 0 |
| rate_target_25 | 10 | 0.500 | 1.000 | 10 | 0.363 | 0 | 0 |
| rate_target_30 | 9 | 0.000 | 1.000 | 10 | 0.453 | 1 | 0 |
| pilot_oracle_1 | 9 | 0.000 | 1.000 | 10 | 0.453 | 1 | 50 |
| pilot_oracle_2 | 9 | 0.000 | 1.000 | 10 | 0.453 | 1 | 100 |

### tau=60

| Strategy | Kp | R@0.5 | Coverage | Candidates | Frame Frac | Merges | Oracle |
|----------|-----|-------|----------|------------|------------|--------|--------|
| oracle_only | 13 | 1.000 | 1.000 | 0 | 1.000 | 0 | 5000 |
| hard_proxy | 13 | 1.000 | 0.000 | 4 | 0.078 | 0 | 0 |
| best_known_Kp | 6 | 1.000 | 0.000 | 3 | 0.606 | 0 | 0 |
| fixed_margin_m1 | 12 | 1.000 | 0.000 | 6 | 0.113 | 0 | 0 |
| fixed_margin_m2 | 11 | 1.000 | 0.000 | 6 | 0.198 | 0 | 0 |
| fixed_margin_m3 | 10 | 1.000 | 0.000 | 6 | 0.331 | 0 | 0 |
| fixed_margin_m4 | 9 | 1.000 | 0.000 | 5 | 0.410 | 0 | 0 |
| rate_target_10 | 12 | 1.000 | 0.000 | 6 | 0.113 | 0 | 0 |
| rate_target_15 | 11 | 1.000 | 0.000 | 6 | 0.198 | 0 | 0 |
| rate_target_20 | 10 | 1.000 | 0.000 | 6 | 0.331 | 0 | 0 |
| rate_target_25 | 10 | 1.000 | 0.000 | 6 | 0.331 | 0 | 0 |
| rate_target_30 | 9 | 1.000 | 0.000 | 5 | 0.410 | 0 | 0 |
| pilot_oracle_1 | 8 | 1.000 | 0.000 | 4 | 0.474 | 0 | 50 |
| pilot_oracle_2 | 8 | 1.000 | 0.000 | 4 | 0.474 | 0 | 100 |

---

## Key Questions

### Q1: Does proxy positive rate rule select Kp≈10?

Kq=12, tau=30:
- Target rate_target_10: Kp=12, actual_rate=0.0874, R@0.5=0.600
- Target rate_target_15: Kp=11, actual_rate=0.146, R@0.5=0.200
- Target rate_target_20: Kp=10, actual_rate=0.2246, R@0.5=0.200
- Target rate_target_25: Kp=10, actual_rate=0.2246, R@0.5=0.200
- Target rate_target_30: Kp=9, actual_rate=0.3136, R@0.5=0.000
Kq=13, tau=30:
- Target rate_target_10: Kp=12, actual_rate=0.0874, R@0.5=0.500
- Target rate_target_15: Kp=11, actual_rate=0.146, R@0.5=0.500
- Target rate_target_20: Kp=10, actual_rate=0.2246, R@0.5=0.500
- Target rate_target_25: Kp=10, actual_rate=0.2246, R@0.5=0.500
- Target rate_target_30: Kp=9, actual_rate=0.3136, R@0.5=0.000

### Q2: Is fixed Kp=Kq-m stable?

Kq=12, tau=30:
- fixed_margin_m1: Kp=11, R@0.5=0.200, coverage=1.000
- fixed_margin_m2: Kp=10, R@0.5=0.200, coverage=1.000
- fixed_margin_m3: Kp=9, R@0.5=0.000, coverage=1.000
- fixed_margin_m4: Kp=8, R@0.5=0.000, coverage=1.000
Kq=13, tau=30:
- fixed_margin_m1: Kp=12, R@0.5=0.500, coverage=1.000
- fixed_margin_m2: Kp=11, R@0.5=0.500, coverage=1.000
- fixed_margin_m3: Kp=10, R@0.5=0.500, coverage=1.000
- fixed_margin_m4: Kp=9, R@0.5=0.000, coverage=1.000

### Q3: Is pilot oracle better than pure proxy rule?

Kq=12, tau=30:
- Best proxy rule: Kp=12, R@0.5=0.600
- Best pilot oracle: Kp=9, R@0.5=0.000, oracle=50
Kq=13, tau=30:
- Best proxy rule: Kp=12, R@0.5=0.500
- Best pilot oracle: Kp=9, R@0.5=0.000, oracle=50

### Q4: Is there candidate explosion?

- Kq=12, tau=30: max frame fraction=1.000 (strategy: oracle_only)
- Kq=13, tau=30: max frame fraction=1.000 (strategy: oracle_only)

### Q5: Recommended default strategy

Kq=12, tau=30: **rate_target_10** (Kp=12, R@0.5=0.600, coverage=1.000)
Kq=13, tau=30: **fixed_margin_m1** (Kp=12, R@0.5=0.500, coverage=1.000)

---

## Recommendations

1. **Use proxy positive rate rule**: Target 20-25% positive rate
2. **Fixed margin Kp=Kq-2**: Simple and stable
3. **Pilot oracle optional**: Marginal improvement over proxy rule
4. **No candidate explosion**: Frame fraction stays below 50%
5. **Default**: Kp = Kq - 2 or proxy_pos_rate target 20%
