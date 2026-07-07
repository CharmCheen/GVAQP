# T028b — ECP offline-learned contextual bandit (strict replay)

Policy trained on the T026/v2 logged table (logistic regression on P(positive | state, arm); supervised-to-bandit reduction, biased by the v2 logging policy). Evaluated as a strict-replay method vs v2 hand-designed, HTS-EC-safe, B7-strict-replay. VLM-oracle-relative, IoU>=0.3.

## Mean event_recall by segment x budget

| segment | budget | ECP_learned | ECP_v2 | HTS-EC-safe | B7-strict | learn_prec | v2_prec | HTS_prec | B7_prec |
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
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | 0.067 | 0.150 | 1.000 | 1.000 | 0.722 | 0.500 |
| realcartest_0_1570 | 0.20 | 0.100 | 0.100 | 0.117 | 0.150 | 0.500 | 0.500 | 0.806 | 0.375 |
| realcartest_0_1570 | 0.30 | 0.200 | 0.200 | 0.183 | 0.250 | 0.500 | 0.500 | 0.624 | 0.500 |
| realcartest_2000_3200 | 0.10 | 0.050 | 0.050 | 0.100 | 0.050 | 0.333 | 0.333 | 0.667 | 0.500 |
| realcartest_2000_3200 | 0.20 | 0.150 | 0.150 | 0.100 | 0.100 | 0.600 | 0.600 | 0.333 | 0.500 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.150 | 0.200 | 0.150 | 0.375 | 0.375 | 0.400 | 0.375 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 0.143 | 0.429 | 1.000 | 1.000 | 0.667 | 1.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 0.143 | 0.429 | 1.000 | 1.000 | 0.667 | 1.000 |
| realcartest_3200_3830 | 0.30 | 0.143 | 0.143 | 0.143 | 0.571 | 0.500 | 0.500 | 0.667 | 1.000 |

## Reading

- The learned policy picks arms by predicted P(positive | state, arm). It is trained only on logged choices (the arm actually taken each step), so it inherits the v2 logging policy's exploration pattern and cannot discover arms the logger never tried. This is a known offline-bandit limitation; report as such.
- If ECP-learned >= ECP-v2 on realcartest without losing precision, the offline learned policy is a strict-replay improvement over fixed weights. The proxy-zero regime (dataset3) remains the open gap; a learned policy trained only on v2 logs cannot invent zero-proxy discoveries the logger did not sample.
- Strict-replay compliant: reference read only at final eval; 0 event_id leaks; 1 oracle call per arm.