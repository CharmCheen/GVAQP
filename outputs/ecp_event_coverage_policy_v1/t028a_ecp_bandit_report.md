# T028a — ECP reweighted bandit (strict replay)

Two hand-designed variants under strict replay: v1 (T027 original weights) and v2 (T028a reweighted: BRIDGE boosted above DISCOVER floor, ZERO_PROXY fires on zero_proxy_share alone with higher cap). Compared to HTS-EC-safe and B7-strict-replay on event_recall / event_precision (VLM-oracle-relative, IoU>=0.3).

## Mean event_recall by segment x budget

| segment | budget | ECP_v1_recall | ECP_v2_recall | HTS-EC-safe | B7-strict | ECP_v1_prec | ECP_v2_prec | HTS_prec | B7_prec |
|---|---|---|---|---|---|---|---|---|---|
| dataset3_0_1200 | 0.10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_0_1200 | 0.20 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_0_1200 | 0.30 | 0.000 | 0.000 | 0.000 | 0.167 | 0.000 | 0.000 | 0.000 | 0.333 |
| dataset3_1200_2400 | 0.10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_1200_2400 | 0.20 | 0.083 | 0.083 | 0.000 | 0.083 | 0.500 | 1.000 | 0.000 | 1.000 |
| dataset3_1200_2400 | 0.30 | 0.083 | 0.083 | 0.000 | 0.083 | 0.333 | 0.333 | 0.000 | 0.200 |
| dataset3_2400_3462 | 0.10 | 0.000 | 0.000 | 0.000 | 0.111 | 0.000 | 0.000 | 0.000 | 0.500 |
| dataset3_2400_3462 | 0.20 | 0.000 | 0.000 | 0.000 | 0.111 | 0.000 | 0.000 | 0.000 | 0.333 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.000 | 0.111 | 0.111 | 0.333 | 0.000 | 0.333 | 0.333 |
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | 0.067 | 0.150 | 0.500 | 1.000 | 0.722 | 0.500 |
| realcartest_0_1570 | 0.20 | 0.150 | 0.100 | 0.117 | 0.150 | 0.500 | 0.500 | 0.806 | 0.375 |
| realcartest_0_1570 | 0.30 | 0.300 | 0.200 | 0.183 | 0.250 | 0.636 | 0.500 | 0.624 | 0.500 |
| realcartest_2000_3200 | 0.10 | 0.050 | 0.050 | 0.100 | 0.050 | 0.333 | 0.333 | 0.667 | 0.500 |
| realcartest_2000_3200 | 0.20 | 0.150 | 0.150 | 0.100 | 0.100 | 0.600 | 0.600 | 0.333 | 0.500 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.150 | 0.200 | 0.150 | 0.375 | 0.375 | 0.400 | 0.375 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 0.143 | 0.429 | 1.000 | 1.000 | 0.667 | 1.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 0.143 | 0.429 | 0.500 | 1.000 | 0.667 | 1.000 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.143 | 0.143 | 0.571 | 0.667 | 0.500 | 0.667 | 1.000 |

## v2 arm usage and positive rate

| arm | n_calls | positive_rate |
|---|---|---|
| DISCOVER | 555 | 0.151 |
| BRIDGE | 633 | 0.441 |
| CERTIFY | 0 | 0.000 |
| ZERO_PROXY | 48 | 0.125 |

## Reading

- v2 reweighting: BRIDGE boosted (w_bridge 0.8->1.2, DISCOVER floor 0.05->0.0) so it wins when a bridge target exists; ZERO_PROXY no longer requires stagnation and uses a higher cap (0.25->0.40, zp_thresh 0.5->0.35).
- If v2 recall >= v1 on realcartest and v2 ZERO_PROXY fires more on dataset3 without hurting precision, the reweighting is a legitimate strict-replay improvement (no new VLM, no event_id). Compare v1 vs v2 columns above.
- Strict-replay compliant: reference events read only at final eval; 0 event_id leaks; 1 oracle call per arm.