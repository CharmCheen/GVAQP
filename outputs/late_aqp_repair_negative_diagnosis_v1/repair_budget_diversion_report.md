# Repair Budget Diversion Analysis

For each repair call we recorded the chunk-bandit state (expected theta) just before the call. We then asked: was there another unqueried chunk with strictly higher theta that the bandit would have preferred for global exploration?

- Total repair calls logged: 38
- Repair calls that diverted budget from a higher-theta chunk: 25 (65.8%)
- Mean number of higher-theta chunks available at repair time: 1.68

## Per-segment breakdown

| segment | repair calls | diversion calls | % diversion | mean higher-theta chunks |
|---|---|---|---|---|
| dataset3_1200_2400 | 4 | 0 | 0.0% | 0.00 |
| dataset3_2400_3462 | 2 | 1 | 50.0% | 1.00 |
| realcartest_0_1570 | 17 | 14 | 82.4% | 1.76 |
| realcartest_2000_3200 | 13 | 8 | 61.5% | 2.00 |
| realcartest_3200_3830 | 2 | 2 | 100.0% | 3.00 |

## Interpretation

Most repair calls occurred when the bandit would have preferred to explore a different chunk. This indicates genuine budget diversion on top of the accounting bug.
