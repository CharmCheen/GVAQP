# Budget Curve Comparison: N=123 (original) vs N=100 (clean)

All values are mean recall across 500 seeds. tp = recall × total_pos (rounded).

## A. Absolute Budget Alignment (same B)

| Strategy | B | N=123 recall | N=123 tp | N=100 recall | N=100 tp | Δ recall |
|----------|---|-------------|----------|-------------|----------|----------|
| 1_L3_baseline | 20 | N/A | N/A | 0.143 | 4.0/28 | N/A |
| 1_L3_baseline | 30 | 0.125 | 5.0/40 | 0.179 | 5.0/28 | +0.054 |
| 1_L3_baseline | 40 | 0.150 | 6.0/40 | 0.321 | 9.0/28 | +0.171 |
| 1_L3_baseline | 60 | 0.325 | 13.0/40 | 0.607 | 17.0/28 | +0.282 |
| 1_L3_baseline | 80 | 0.625 | 25.0/40 | 0.857 | 24.0/28 | +0.232 |
| 1_L3_baseline | 100 | 0.825 | 33.0/40 | 1.000 | 28.0/28 | +0.175 |
| 2_GLM_positive_only | 20 | N/A | N/A | 0.500 | 14.0/28 | N/A |
| 2_GLM_positive_only | 30 | 0.500 | 20.0/40 | 0.571 | 16.0/28 | +0.071 |
| 2_GLM_positive_only | 40 | 0.600 | 24.0/40 | 0.571 | 16.0/28 | -0.029 |
| 2_GLM_positive_only | 60 | 0.600 | 24.0/40 | 0.571 | 16.0/28 | -0.029 |
| 2_GLM_positive_only | 80 | 0.600 | 24.0/40 | 0.571 | 16.0/28 | -0.029 |
| 2_GLM_positive_only | 100 | 0.600 | 24.0/40 | 0.571 | 16.0/28 | -0.029 |
| 4_GLM_pos_unc_plus_L3_neg | 20 | N/A | N/A | 0.500 | 14.0/28 | N/A |
| 4_GLM_pos_unc_plus_L3_neg | 30 | 0.500 | 20.0/40 | 0.607 | 17.0/28 | +0.107 |
| 4_GLM_pos_unc_plus_L3_neg | 40 | 0.600 | 24.0/40 | 0.643 | 18.0/28 | +0.043 |
| 4_GLM_pos_unc_plus_L3_neg | 60 | 0.675 | 27.0/40 | 0.750 | 21.0/28 | +0.075 |
| 4_GLM_pos_unc_plus_L3_neg | 80 | 0.775 | 31.0/40 | 0.857 | 24.0/28 | +0.082 |
| 4_GLM_pos_unc_plus_L3_neg | 100 | 0.875 | 35.0/40 | 1.000 | 28.0/28 | +0.125 |
| 6_L3_plus_uniform_audit | 20 | N/A | N/A | 0.170 | 4.8/28 | N/A |
| 6_L3_plus_uniform_audit | 30 | 0.179 | 7.2/40 | 0.242 | 6.8/28 | +0.063 |
| 6_L3_plus_uniform_audit | 40 | 0.236 | 9.4/40 | 0.315 | 8.8/28 | +0.080 |
| 6_L3_plus_uniform_audit | 60 | 0.340 | 13.6/40 | 0.528 | 14.8/28 | +0.189 |
| 6_L3_plus_uniform_audit | 80 | 0.544 | 21.8/40 | 0.789 | 22.1/28 | +0.245 |
| 6_L3_plus_uniform_audit | 100 | 0.770 | 30.8/40 | 1.000 | 28.0/28 | +0.230 |
| 7_L3_plus_GLM_disagreement_audit | 20 | N/A | N/A | 0.214 | 6.0/28 | N/A |
| 7_L3_plus_GLM_disagreement_audit | 30 | 0.225 | 9.0/40 | 0.250 | 7.0/28 | +0.025 |
| 7_L3_plus_GLM_disagreement_audit | 40 | 0.275 | 11.0/40 | 0.393 | 11.0/28 | +0.118 |
| 7_L3_plus_GLM_disagreement_audit | 60 | 0.475 | 19.0/40 | 0.786 | 22.0/28 | +0.311 |
| 7_L3_plus_GLM_disagreement_audit | 80 | 0.775 | 31.0/40 | 0.857 | 24.0/28 | +0.082 |
| 7_L3_plus_GLM_disagreement_audit | 100 | 0.875 | 35.0/40 | 1.000 | 28.0/28 | +0.125 |

## B. Relative Budget Alignment (B_equiv = round(B * 100/123))

Controls for budget-as-fraction-of-pool. N=123 at B vs N=100 at B_equiv.

| Strategy | B (N=123) | B_equiv (N=100) | N=123 recall | N=100 recall | Δ recall |
|----------|-----------|-----------------|-------------|--------------|----------|

## C. Sanity Check: B=N (full pool)

| Pool | B | Strategy | Recall | tp |
|------|---|----------|--------|----|
| N=123 | 100 | 4_GLM_pos_unc_plus_L3_neg | 0.875 | 35.0/40 |
| N=100 | 100 | 4_GLM_pos_unc_plus_L3_neg | 1.000 | 28.0/28 |

B=100 on N=100 = full pool → recall=1.000 ✓
B=100 on N=123 = 81.3% of pool → recall=0.875 (not full)
