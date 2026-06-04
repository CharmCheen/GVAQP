# Nearest-Neighbor Stress Test

## Overview

This report analyzes when and how nearest-neighbor interpolation fails
under harder nonstationary perturbation regimes.

## NN Performance by Regime

| Regime | Clip Recall | Clip Prec | IoU | Frag | False Merge | False Split |
|--------|-------------|-----------|-----|------|-------------|-------------|
| regime_shift | 0.616 | 0.393 | 0.464 | 1.464 | 0.01 | 1.48 |
| long_gap | 0.995 | 0.999 | 0.995 | 0.000 | 0.01 | 0.00 |
| close_merge | 0.995 | 0.999 | 0.995 | 0.000 | 0.01 | 0.00 |
| boundary_ambig | 0.995 | 0.999 | 0.995 | 0.000 | 0.01 | 0.00 |
| mixed_hard | 0.461 | 0.309 | 0.338 | 1.640 | 0.01 | 1.66 |

## Failure Analysis

Cases where NN clip recall < 0.8:

Total failure cases: 5788 / 30000

| Regime | Failures | Total | Failure Rate |
|--------|----------|-------|--------------|
| regime_shift | 2335 | 6000 | 0.389 |
| long_gap | 63 | 6000 | 0.011 |
| close_merge | 63 | 6000 | 0.011 |
| boundary_ambig | 63 | 6000 | 0.011 |
| mixed_hard | 3264 | 6000 | 0.544 |

### Failure Mode Distribution

For NN failures (clip recall < 0.8), which metrics are worst:

- Recall failures (< 0.8): 5788
- Precision failures (< 0.8): 5513
- IoU failures (< 0.6): 5550
- False merge issues (> 0.5): 258
- False split issues (> 0.5): 5279

## NN Performance: Regime × Tau

| Regime | Tau | Clip Recall | Clip Prec | IoU | Frag |
|--------|-----|-------------|-----------|-----|------|
| regime_shift | 10 | 0.618 | 0.364 | 0.463 | 1.808 |
| regime_shift | 20 | 0.617 | 0.382 | 0.463 | 1.595 |
| regime_shift | 30 | 0.619 | 0.401 | 0.462 | 1.423 |
| regime_shift | 60 | 0.612 | 0.427 | 0.467 | 1.031 |
| long_gap | 10 | 0.994 | 1.000 | 0.995 | 0.000 |
| long_gap | 20 | 0.994 | 0.999 | 0.995 | 0.000 |
| long_gap | 30 | 0.995 | 0.999 | 0.995 | 0.000 |
| long_gap | 60 | 0.996 | 0.998 | 0.996 | 0.000 |
| close_merge | 10 | 0.994 | 1.000 | 0.995 | 0.000 |
| close_merge | 20 | 0.994 | 0.999 | 0.995 | 0.000 |
| close_merge | 30 | 0.995 | 0.999 | 0.995 | 0.000 |
| close_merge | 60 | 0.996 | 0.998 | 0.996 | 0.000 |
| boundary_ambig | 10 | 0.994 | 1.000 | 0.995 | 0.000 |
| boundary_ambig | 20 | 0.994 | 0.999 | 0.995 | 0.000 |
| boundary_ambig | 30 | 0.995 | 0.999 | 0.995 | 0.000 |
| boundary_ambig | 60 | 0.996 | 0.998 | 0.996 | 0.000 |
| mixed_hard | 10 | 0.462 | 0.258 | 0.341 | 2.519 |
| mixed_hard | 20 | 0.461 | 0.277 | 0.339 | 1.966 |
| mixed_hard | 30 | 0.461 | 0.304 | 0.338 | 1.493 |
| mixed_hard | 60 | 0.460 | 0.397 | 0.336 | 0.582 |