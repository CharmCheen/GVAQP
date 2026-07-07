# T028c-0 — candidate-level event-utility ORACLE CEILING

At each step, ALL candidate arms are enumerated and their offline marginal event-utility is computed (using true label + reference); the max-utility candidate is executed. This is a CEILING (selection reads reference) and is NOT a deployable strict-replay policy. It answers: does the candidate action set contain event-level decisions better than v2? If not, training a policy (T028c-1) is moot.

## Mean event_recall: oracle-ceiling vs v2 (strict-replay)

| segment | budget | ceiling_recall | v2_recall | ceiling_prec | v2_prec | delta_recall |
|---|---|---|---|---|---|---|
| dataset3_0_1200 | 0.10 | 0.000 | 0.000 | 0.000 | 0.000 | +0.000 |
| dataset3_0_1200 | 0.20 | 0.000 | 0.000 | 0.000 | 0.000 | +0.000 |
| dataset3_0_1200 | 0.30 | 0.000 | 0.000 | 0.000 | 0.000 | +0.000 |
| dataset3_1200_2400 | 0.10 | 0.000 | 0.000 | 0.000 | 0.000 | +0.000 |
| dataset3_1200_2400 | 0.20 | 0.000 | 0.083 | 0.000 | 1.000 | -0.083 |
| dataset3_1200_2400 | 0.30 | 0.000 | 0.083 | 0.000 | 0.333 | -0.083 |
| dataset3_2400_3462 | 0.10 | 0.111 | 0.000 | 0.500 | 0.000 | +0.111 |
| dataset3_2400_3462 | 0.20 | 0.111 | 0.000 | 0.500 | 0.000 | +0.111 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.000 | 0.333 | 0.000 | +0.111 |
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | 0.500 | 1.000 | +0.000 |
| realcartest_0_1570 | 0.20 | 0.150 | 0.100 | 0.429 | 0.500 | +0.050 |
| realcartest_0_1570 | 0.30 | 0.300 | 0.200 | 0.600 | 0.500 | +0.100 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.050 | 0.667 | 0.333 | +0.050 |
| realcartest_2000_3200 | 0.20 | 0.100 | 0.150 | 0.333 | 0.600 | -0.050 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.150 | 0.273 | 0.375 | +0.000 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 1.000 | 1.000 | +0.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 1.000 | 1.000 | +0.000 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.143 | 0.667 | 0.500 | +0.143 |

## Oracle-ceiling arm usage

| arm | n_calls | positive_rate | mean_chosen_u |
|---|---|---|---|
| DISCOVER | 1188 | 0.278 | 0.099 |
| BRIDGE | 39 | 1.000 | 0.330 |
| CERTIFY | 9 | 1.000 | 1.150 |
| ZERO_PROXY | 0 | 0.000 | 0.000 |

## Reading / verdict

- If ceiling_recall >> v2 on every segment, the candidate set HAS learnable event-level signal -> proceed to T028c-1 (train event-utility ranker).
- If ceiling ≈ v2, the candidate arms do not contain better event-level decisions than v2 already makes -> the bottleneck is the CANDIDATE GENERATOR or the proxy-zero regime, not the selection policy. Training T028c-1 would just re-learn v2. In that case T028d/DR cannot help either (no counterfactual support).
- This is an OFFLINE CEILING: it reads reference to select, so it is NOT a strict-replay result and must never be reported as one. v2 (strict-replay) is the fair baseline in the table above.