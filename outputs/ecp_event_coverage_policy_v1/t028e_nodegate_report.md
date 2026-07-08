# T028e nodegate ablation — globalcap vs soft gate vs strict gate

Compares three candidate gating modes for zero-proxy arms. All use GBM event-utility policy on 9-arm extended candidates, strict-replay LOSO, with `MAX_ZERO_PROXY_SHARE=0.10` policy cap.

## Gate definitions

- **globalcap**: Always generate all 9 arms; cap at policy level only (current ECP-c2).
- **soft_gate**: Generate zp arms only when `zp_share >= 0.40`, `>=6 zp bins remain`, AND (`n_probe >= 2 with 0 positives` OR `negative_streak >= 2`).
- **strict_gate**: Generate zp arms only when `zp_share >= 0.50`, `>=8 zp bins`, `n_probe >= 3`, AND `n_pos == 0`.

## Per-segment mean event_recall

| segment | budget | globalcap | soft_gate | strict_gate | soft-global | strict-global |
|---|---|---|---|---|---|---|
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | 0.050 | +0.000 | +0.000 |
| realcartest_0_1570 | 0.20 | 0.150 | 0.150 | 0.150 | +0.000 | +0.000 |
| realcartest_0_1570 | 0.30 | 0.300 | 0.300 | 0.300 | +0.000 | +0.000 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.100 | 0.100 | +0.000 | +0.000 |
| realcartest_2000_3200 | 0.20 | 0.150 | 0.150 | 0.150 | +0.000 | +0.000 |
| realcartest_2000_3200 | 0.30 | 0.200 | 0.200 | 0.200 | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 0.143 | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 0.143 | +0.000 | +0.000 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.286 | 0.286 | +0.000 | +0.000 |
| dataset3_0_1200 | 0.10 | 0.000 | 0.000 | 0.000 | +0.000 | +0.000 |
| dataset3_0_1200 | 0.20 | 0.167 | 0.000 | 0.000 | -0.167 | -0.167 |
| dataset3_0_1200 | 0.30 | 0.167 | 0.000 | 0.000 | -0.167 | -0.167 |
| dataset3_1200_2400 | 0.10 | 0.000 | 0.000 | 0.000 | +0.000 | +0.000 |
| dataset3_1200_2400 | 0.20 | 0.083 | 0.000 | 0.000 | -0.083 | -0.083 |
| dataset3_1200_2400 | 0.30 | 0.083 | 0.083 | 0.083 | +0.000 | +0.000 |
| dataset3_2400_3462 | 0.10 | 0.000 | 0.111 | 0.111 | +0.111 | +0.111 |
| dataset3_2400_3462 | 0.20 | 0.111 | 0.111 | 0.111 | +0.000 | +0.000 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.111 | 0.111 | +0.000 | +0.000 |

## Zero-proxy arm calls per gate mode

| gate_mode | segment | budget | total_zp_calls |
|---|---|---|---|
| globalcap | dataset3_0_1200 | 0.10 | 12.0 |
| globalcap | dataset3_0_1200 | 0.20 | 13.0 |
| globalcap | dataset3_0_1200 | 0.30 | 13.0 |
| globalcap | dataset3_1200_2400 | 0.10 | 4.0 |
| globalcap | dataset3_1200_2400 | 0.20 | 4.0 |
| globalcap | dataset3_1200_2400 | 0.30 | 5.0 |
| globalcap | dataset3_2400_3462 | 0.10 | 10.0 |
| globalcap | dataset3_2400_3462 | 0.20 | 13.0 |
| globalcap | dataset3_2400_3462 | 0.30 | 20.0 |
| globalcap | realcartest_0_1570 | 0.10 | 0.0 |
| globalcap | realcartest_0_1570 | 0.20 | 0.0 |
| globalcap | realcartest_0_1570 | 0.30 | 0.0 |
| globalcap | realcartest_2000_3200 | 0.10 | 0.0 |
| globalcap | realcartest_2000_3200 | 0.20 | 0.0 |
| globalcap | realcartest_2000_3200 | 0.30 | 0.0 |
| globalcap | realcartest_3200_3830 | 0.10 | 0.0 |
| globalcap | realcartest_3200_3830 | 0.20 | 0.0 |
| globalcap | realcartest_3200_3830 | 0.30 | 0.0 |
| soft_gate | dataset3_0_1200 | 0.10 | 2.0 |
| soft_gate | dataset3_0_1200 | 0.20 | 3.0 |
| soft_gate | dataset3_0_1200 | 0.30 | 4.0 |
| soft_gate | dataset3_1200_2400 | 0.10 | 2.0 |
| soft_gate | dataset3_1200_2400 | 0.20 | 3.0 |
| soft_gate | dataset3_1200_2400 | 0.30 | 4.0 |
| soft_gate | dataset3_2400_3462 | 0.10 | 2.0 |
| soft_gate | dataset3_2400_3462 | 0.20 | 3.0 |
| soft_gate | dataset3_2400_3462 | 0.30 | 4.0 |
| soft_gate | realcartest_0_1570 | 0.10 | 0.0 |
| soft_gate | realcartest_0_1570 | 0.20 | 0.0 |
| soft_gate | realcartest_0_1570 | 0.30 | 0.0 |
| soft_gate | realcartest_2000_3200 | 0.10 | 0.0 |
| soft_gate | realcartest_2000_3200 | 0.20 | 0.0 |
| soft_gate | realcartest_2000_3200 | 0.30 | 0.0 |
| soft_gate | realcartest_3200_3830 | 0.10 | 0.0 |
| soft_gate | realcartest_3200_3830 | 0.20 | 0.0 |
| soft_gate | realcartest_3200_3830 | 0.30 | 0.0 |
| strict_gate | dataset3_0_1200 | 0.10 | 2.0 |
| strict_gate | dataset3_0_1200 | 0.20 | 3.0 |
| strict_gate | dataset3_0_1200 | 0.30 | 4.0 |
| strict_gate | dataset3_1200_2400 | 0.10 | 2.0 |
| strict_gate | dataset3_1200_2400 | 0.20 | 3.0 |
| strict_gate | dataset3_1200_2400 | 0.30 | 3.0 |
| strict_gate | dataset3_2400_3462 | 0.10 | 0.0 |
| strict_gate | dataset3_2400_3462 | 0.20 | 0.0 |
| strict_gate | dataset3_2400_3462 | 0.30 | 0.0 |
| strict_gate | realcartest_0_1570 | 0.10 | 0.0 |
| strict_gate | realcartest_0_1570 | 0.20 | 0.0 |
| strict_gate | realcartest_0_1570 | 0.30 | 0.0 |
| strict_gate | realcartest_2000_3200 | 0.10 | 0.0 |
| strict_gate | realcartest_2000_3200 | 0.20 | 0.0 |
| strict_gate | realcartest_2000_3200 | 0.30 | 0.0 |
| strict_gate | realcartest_3200_3830 | 0.10 | 0.0 |
| strict_gate | realcartest_3200_3830 | 0.20 | 0.0 |
| strict_gate | realcartest_3200_3830 | 0.30 | 0.0 |

## Pass/fail

- dataset3_0_1200 globalcap max: 0.167
- dataset3_0_1200 soft_gate max: 0.000
- dataset3_0_1200 strict_gate max: 0.000
- **soft_gate FAIL**: regresses vs globalcap on dataset3_0_1200.
- **strict_gate FAIL**: regresses vs globalcap on dataset3_0_1200.
- **realcartest**: 0 gate-mode regressions.