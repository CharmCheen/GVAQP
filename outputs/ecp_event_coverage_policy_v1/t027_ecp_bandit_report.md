# T027 — ECP hand-designed bandit (strict replay)

ECP bandit (DISCOVER/BRIDGE/CERTIFY/ZERO_PROXY/STOP, heuristic U(a)/cost, online-only state) run under strict replay. Compared to HTS-EC-safe and B7-strict-replay on event_recall / event_precision (VLM-oracle-relative, IoU>=0.3).

## Mean event_recall by segment x budget (ECP vs baselines)

| segment | budget | ECP_recall | HTS-EC-safe_recall | B7-strict_recall | ECP_prec | HTS_prec | B7_prec |
|---|---|---|---|---|---|---|---|
| dataset3_0_1200 | 0.10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_0_1200 | 0.20 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_0_1200 | 0.30 | 0.000 | 0.000 | 0.167 | 0.000 | 0.000 | 0.333 |
| dataset3_1200_2400 | 0.10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_1200_2400 | 0.20 | 0.083 | 0.000 | 0.083 | 0.500 | 0.000 | 1.000 |
| dataset3_1200_2400 | 0.30 | 0.083 | 0.000 | 0.083 | 0.333 | 0.000 | 0.200 |
| dataset3_2400_3462 | 0.10 | 0.000 | 0.000 | 0.111 | 0.000 | 0.000 | 0.500 |
| dataset3_2400_3462 | 0.20 | 0.000 | 0.000 | 0.111 | 0.000 | 0.000 | 0.333 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.111 | 0.111 | 0.333 | 0.333 | 0.333 |
| realcartest_0_1570 | 0.10 | 0.050 | 0.067 | 0.150 | 0.500 | 0.722 | 0.500 |
| realcartest_0_1570 | 0.20 | 0.150 | 0.117 | 0.150 | 0.500 | 0.806 | 0.375 |
| realcartest_0_1570 | 0.30 | 0.300 | 0.183 | 0.250 | 0.636 | 0.624 | 0.500 |
| realcartest_2000_3200 | 0.10 | 0.050 | 0.100 | 0.050 | 0.333 | 0.667 | 0.500 |
| realcartest_2000_3200 | 0.20 | 0.150 | 0.100 | 0.100 | 0.600 | 0.333 | 0.500 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.200 | 0.150 | 0.375 | 0.400 | 0.375 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 0.429 | 1.000 | 0.667 | 1.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 0.429 | 0.500 | 0.667 | 1.000 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.143 | 0.571 | 0.667 | 0.667 | 1.000 |

## Reading

- This is a FIRST hand-designed bandit; weights are heuristics, not learned. It validates that event-level arm selection is a viable strict-replay policy layer and isolates which arms earn their budget.
- T026 action-utility table (t026_action_utility.csv) logs the per-step U(a) of every arm and the chosen arm — the offline-labeled training signal for a future learned policy (T027 step 4).
- Strict-replay compliant: reference events read only at final evaluation; no event_id online; 1 oracle call per arm execution.