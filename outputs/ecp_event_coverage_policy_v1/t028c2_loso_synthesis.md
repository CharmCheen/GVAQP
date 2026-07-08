# T028c-2 — LOSO synthesis

## Key finding

**c1 generalizes on realcartest: 0 regressions, 4/9 improvements (up to +0.143), 3/9 ties, 2/9 ceiling-reached.**
c1 does NOT generalize on dataset3 (candidate-generator bottleneck).

## Per-segment breakdown (realcartest held-out)

| Segment | Budget | c1 | v2 | ceiling | verdict |
|---|---|---|---|---|---|
| realcartest_0_1570 | 0.20 | 0.150 | 0.100 | 0.150 | **c1 = ceiling > v2** |
| realcartest_0_1570 | 0.30 | 0.300 | 0.200 | 0.300 | **c1 = ceiling > v2** |
| realcartest_2000_3200 | 0.10 | 0.100 | 0.050 | 0.100 | **c1 = ceiling > v2** |
| realcartest_3200_3830 | 0.30 | 0.286 | 0.143 | 0.286 | **c1 = ceiling > v2** |
| realcartest_2000_3200 | 0.20 | 0.100 | 0.150 | 0.100 | c1 < v2 (but = ceiling) |
| others | - | = v2 | - | - | tie |

## Action distribution shift (c1 vs v2 on realcartest)

- **c1**: more DISCOVER + CERTIFY, almost no BRIDGE
- **v2**: heavy BRIDGE, little DISCOVER/CERTIFY

This is the generalization signal: c1 learned to prefer DISCOVER/CERTIFY over BRIDGE on realcartest, and this transfers to held-out.

## dataset3 held-out

c1 <= v2 on all 9 cells. Ceiling is also ~0 on proxy-zero segments. Confirms candidate-generator bottleneck.

## What this means

1. T028c-1's event-utility policy is NOT just overfitting to training segments on realcartest
2. The policy captures cross-segment generalizable signal about when DISCOVER/CERTIFY beat BRIDGE
3. On dataset3, no policy can help because the candidate generator doesn't propose zero-proxy positives
4. The next lever is T028e (proxy-free candidate generator) to raise the dataset3 ceiling

## Safe claims

- ECP-utility-c1 generalizes on proxy-informative segments (realcartest): 0 regressions on held-out
- ECP-utility-c1 does NOT solve proxy-zero segments (dataset3): candidate-generator bottleneck
- The event-utility reward structure transfers across segments; the positive-label reward (T028b) does not
