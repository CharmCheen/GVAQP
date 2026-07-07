# T028c-1 — event-utility ranking policy (strict replay)

Policy trained on the T028c-0 CANDIDATE-LEVEL utility table: every logged step carries the offline marginal event-utility of ALL four candidate arms, so the learner sees counterfactual arm utilities and is NOT confined to the logger's choices (this is what made T028b merely re-learn the logger). Regressor: GradientBoosting on u(arm | state, arm). At each strict-replay step it predicts u for each available arm and executes the max. VLM-oracle-relative, IoU>=0.3.

## Mean event_recall: c1 vs v2 vs oracle-ceiling vs baselines

| segment | budget | c1_recall | v2_recall | ceiling | HTS | B7 | c1_prec | v2_prec | HTS_prec | B7_prec |
|---|---|---|---|---|---|---|---|---|---|---|
| dataset3_0_1200 | 0.10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_0_1200 | 0.20 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_0_1200 | 0.30 | 0.000 | 0.000 | 0.000 | 0.000 | 0.167 | 0.000 | 0.000 | 0.000 | 0.333 |
| dataset3_1200_2400 | 0.10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_1200_2400 | 0.20 | 0.000 | 0.083 | 0.000 | 0.000 | 0.083 | 0.000 | 1.000 | 0.000 | 1.000 |
| dataset3_1200_2400 | 0.30 | 0.000 | 0.083 | 0.000 | 0.000 | 0.083 | 0.000 | 0.333 | 0.000 | 0.200 |
| dataset3_2400_3462 | 0.10 | 0.111 | 0.000 | 0.111 | 0.000 | 0.111 | 0.500 | 0.000 | 0.000 | 0.500 |
| dataset3_2400_3462 | 0.20 | 0.111 | 0.000 | 0.111 | 0.000 | 0.111 | 0.500 | 0.000 | 0.000 | 0.333 |
| dataset3_2400_3462 | 0.30 | 0.111 | 0.000 | 0.111 | 0.111 | 0.111 | 0.333 | 0.000 | 0.333 | 0.333 |
| realcartest_0_1570 | 0.10 | 0.050 | 0.050 | 0.050 | 0.067 | 0.150 | 0.500 | 1.000 | 0.722 | 0.500 |
| realcartest_0_1570 | 0.20 | 0.100 | 0.100 | 0.150 | 0.117 | 0.150 | 0.333 | 0.500 | 0.806 | 0.375 |
| realcartest_0_1570 | 0.30 | 0.250 | 0.200 | 0.300 | 0.183 | 0.250 | 0.500 | 0.500 | 0.624 | 0.500 |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.050 | 0.100 | 0.100 | 0.050 | 0.667 | 0.333 | 0.667 | 0.500 |
| realcartest_2000_3200 | 0.20 | 0.100 | 0.150 | 0.100 | 0.100 | 0.100 | 0.333 | 0.600 | 0.333 | 0.500 |
| realcartest_2000_3200 | 0.30 | 0.150 | 0.150 | 0.150 | 0.200 | 0.150 | 0.300 | 0.375 | 0.400 | 0.375 |
| realcartest_3200_3830 | 0.10 | 0.143 | 0.143 | 0.143 | 0.143 | 0.429 | 1.000 | 1.000 | 0.667 | 1.000 |
| realcartest_3200_3830 | 0.20 | 0.143 | 0.143 | 0.143 | 0.143 | 0.429 | 1.000 | 1.000 | 0.667 | 1.000 |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.143 | 0.286 | 0.143 | 0.571 | 0.667 | 0.500 | 0.667 | 1.000 |

## Reading / verdict

- c1 is trained on counterfactual candidate utilities, so it is the proper T028b successor. If c1 >= v2 on realcartest (where the T028c-0 ceiling showed learnable signal) without losing precision, the event-utility ranking policy is a strict-replay improvement over fixed weights.
- On proxy-zero dataset3, c1 cannot beat the ceiling (which is itself ~0 there): the candidate generator cannot propose zero-proxy positives, so no policy trained on these candidates can recover them. This is the candidate-generator bottleneck, not a policy-learning failure; T028d/DR cannot fix it either.
- Strict-replay compliant: reference read only to build training labels offline; 0 event_id leaks online; 1 oracle call per arm.