# Repair Marginal Value After Accounting Fix

Comparison of D3-core-chunk120-fixed (chunk-bandit + repair + Core/Halo) vs D3-norepair-core-chunk120 (chunk-bandit + Core/Halo, no repair).

## Best unique event coverage under <=30% budget

| segment | fixed unique | norepair unique | delta | fixed long-R | norepair long-R | delta |
|---|---|---|---|---|---|---|
| realcartest_0_1570 | 10.0 | 8.0 | +2.0 | 0.875 | 0.750 | +0.125 |
| realcartest_2000_3200 | 8.0 | 8.0 | +0.0 | 0.500 | 0.667 | -0.167 |
| realcartest_3200_3830 | 2.0 | 2.0 | +0.0 | 0.500 | 0.500 | +0.000 |
| dataset3_0_1200 | 3.0 | 4.0 | -1.0 | 1.000 | 1.000 | +0.000 |
| dataset3_1200_2400 | 4.0 | 5.0 | -1.0 | 1.000 | 0.500 | +0.500 |
| dataset3_2400_3462 | 4.0 | 4.0 | +0.0 | 0.333 | 0.667 | -0.333 |

## B_90/90 comparison

| segment | fixed B_90/90 | norepair B_90/90 | fixed better? |
|---|---|---|---|
| dataset3_0_1200 | 80 | 80 | no |
| dataset3_1200_2400 | 100 | 80 | no |
| dataset3_2400_3462 | 100 | 100 | no |
| realcartest_0_1570 | 157 | 157 | no |
| realcartest_2000_3200 | 100 | 120 | yes |
| realcartest_3200_3830 | 60 | 60 | no |

## Best recall under P>=0.9 within <=30% budget

| segment | fixed R | norepair R | delta |
|---|---|---|---|
| dataset3_0_1200 | 0.500 | 0.667 | -0.167 |
| dataset3_1200_2400 | 0.333 | 0.417 | -0.083 |
| dataset3_2400_3462 | 0.444 | 0.444 | +0.000 |
| realcartest_0_1570 | 0.500 | 0.400 | +0.100 |
| realcartest_2000_3200 | 0.400 | 0.400 | +0.000 |
| realcartest_3200_3830 | 0.286 | 0.286 | +0.000 |

## Conclusion

**B. Repair is neutral after accounting fix** (D3-core-fixed is better on only 1/6 segments).
