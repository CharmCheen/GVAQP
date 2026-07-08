# T033b-0 — Proxy-only start-router (LOSO)

Trains a RandomForest classifier to predict the best full-policy for each (segment, budget) cell using ONLY segment-level proxy statistics. No oracle calls consumed by the router. Evaluated via leave-one-segment-out.

Policy pool: B7, D3, EventLift-DC, ECP-c2

## Results

- **Learned router macro recall**: 0.134
- **B7 baseline macro recall**: 0.165
- **Router lift over B7**: -0.031
- **Router accuracy** (matching oracle): 12.5% (2/16)
- **Oracle ceiling (T033a)**: 0.228
- **Oracle lift captured**: -50.0%

## Per-cell predictions

| held_out | budget | predicted | oracle | correct | pred_recall | oracle_recall |
|---|---|---|---|---|---|---|
| realcartest_0_1570 | 0.10 | B7 | EventLift-DC | no | 0.150 | 0.200 |
| realcartest_0_1570 | 0.20 | B7 | EventLift-DC | no | 0.150 | 0.250 |
| realcartest_2000_3200 | 0.20 | B7 | ECP-c2 | no | 0.100 | 0.150 |
| realcartest_2000_3200 | 0.30 | EventLift-DC | ECP-c2 | no | 0.200 | 0.200 |
| realcartest_3200_3830 | 0.10 | EventLift-DC | B7 | no | 0.143 | 0.429 |
| realcartest_3200_3830 | 0.20 | EventLift-DC | B7 | no | 0.143 | 0.429 |
| realcartest_3200_3830 | 0.30 | EventLift-DC | B7 | no | 0.286 | 0.571 |
| dataset3_0_1200 | 0.10 | D3 | D3 | YES | 0.167 | 0.167 |
| dataset3_0_1200 | 0.20 | D3 | ECP-c2 | no | 0.167 | 0.167 |
| dataset3_0_1200 | 0.30 | D3 | ECP-c2 | no | 0.167 | 0.167 |
| dataset3_1200_2400 | 0.10 | D3 | D3 | YES | 0.083 | 0.083 |
| dataset3_1200_2400 | 0.20 | ECP-c2 | D3 | no | 0.083 | 0.167 |
| dataset3_1200_2400 | 0.30 | ECP-c2 | D3 | no | 0.083 | 0.167 |
| dataset3_2400_3462 | 0.10 | D3 | B7 | no | 0.000 | 0.111 |
| dataset3_2400_3462 | 0.20 | ECP-c2 | EventLift-DC | no | 0.111 | 0.222 |
| dataset3_2400_3462 | 0.30 | ECP-c2 | EventLift-DC | no | 0.111 | 0.222 |

## Policy confusion matrix (oracle → predicted)

| oracle \ predicted | B7 | D3 | EventLift-DC | ECP-c2 |
| - | - | - | - | - |
| B7 | 0 | 1 | 3 | 0 |
| D3 | 0 | 2 | 0 | 2 |
| EventLift-DC | 2 | 0 | 0 | 2 |
| ECP-c2 | 1 | 2 | 1 | 0 |

## Verdict

- **FAIL**: router (0.134) barely exceeds B7 (0.165).
  Proxy-only features insufficient. Warmup-router (T033b-1) is needed.

## Top feature importances

- budget_ratio: 0.1062
- proxy_gini: 0.0844
- proxy_mean: 0.0813
- proxy_min: 0.0761
- temporal_proxy_std: 0.0738
- top10_mass: 0.0656
- n_modes: 0.0649
- top5_mass: 0.0592
- n_bins: 0.0572
- n_zero_proxy: 0.0478