# Verdict Report — Hybrid Cold-Start Discovery

## Selected design parameter

r = **0.5** (chosen by pre-specified criterion: maximize number of segments with substantive improvement at both B=10 and B=20 vs v2, tie-break toward 0.5).

## Sensitivity of r

| r | segments improved at both B=10 and B=20 |
|---|------------------------------------------|
| 0.3 | 0/3 |
| 0.5 | 0/3 |
| 0.7 | 0/3 |

## 4a) Does v2_hybrid improve over v2 on >=2/3 segments at B=10/20?

| Segment | Budget | v2 mean | v2 std | hybrid mean | hybrid std | Δ | Δ > noise? |
|---------|--------|---------|--------|-------------|------------|---|------------|
| realcartest_0_1570 | 10 | 0.125 | 0.000 | 0.175 | 0.061 | 0.050 | No |
| realcartest_0_1570 | 20 | 0.250 | 0.000 | 0.200 | 0.061 | -0.050 | No |
| realcartest_2000_3200 | 10 | 0.333 | 0.000 | 0.333 | 0.105 | 0.000 | No |
| realcartest_2000_3200 | 20 | 0.500 | 0.000 | 0.567 | 0.170 | 0.067 | No |
| realcartest_3200_3830 | 10 | 0.250 | 0.000 | 0.300 | 0.100 | 0.050 | No |
| realcartest_3200_3830 | 20 | 0.500 | 0.000 | 0.500 | 0.000 | 0.000 | No |

Segments with substantive improvement at **both** B=10 and B=20: **0/3**.

**Answer 4a: No.**

## 4b) Does v2_hybrid reach or exceed B6?

| Segment | Budget | hybrid mean | hybrid std | B6 mean | B6 std | gap (hybrid−B6) |
|---------|--------|-------------|------------|---------|--------|-----------------|
| realcartest_0_1570 | 10 | 0.175 | 0.061 | 0.150 | 0.094 | 0.025 |
| realcartest_0_1570 | 20 | 0.200 | 0.061 | 0.275 | 0.050 | -0.075 |
| realcartest_2000_3200 | 10 | 0.333 | 0.105 | 0.200 | 0.163 | 0.133 |
| realcartest_2000_3200 | 20 | 0.567 | 0.170 | 0.400 | 0.249 | 0.167 |
| realcartest_3200_3830 | 10 | 0.300 | 0.100 | 0.450 | 0.187 | -0.150 |
| realcartest_3200_3830 | 20 | 0.500 | 0.000 | 0.650 | 0.255 | -0.150 |

v2_hybrid mean recall is >= B6 mean recall in **3/6** segment-budget combinations.

**Answer 4b: Partial.**

## 4c) Choice of r and sensitivity

Final `r = 0.5`. The sensitivity table above shows how many segments improve at both low budgets for each r. The default value 0.5 was selected (or tied and chosen by the tie-breaker), matching the design intuition of splitting the cold-start budget evenly between exploration and exploitation.

## 4d) High-budget behavior

Hybrid cold-start is only applied when `cold_start_fallback` is active, i.e. B <= 20. For B > 20 the method is identical to Frozen-LATE-AQP-v1 (audit + discovery + repair). Therefore high-budget behavior is unchanged from the already-validated v1 and is not expected to regress. The comparison CSV includes the existing v1 high-budget rows under both the v1 and v2_hybrid method names for reference.

## Overall verdict

**FAIL**: Even the hybrid cold-start does not substantively improve v2 on at least 2/3 segments. The low-budget discovery problem remains unresolved and requires a different fix.
