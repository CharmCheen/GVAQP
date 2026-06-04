# Hard Synthetic Benchmark Report

## Research Question

Was the previous synthetic benchmark too easy? Does nearest-neighbor
still dominate under harder nonstationary perturbation regimes?

## Configuration

- Regimes: ['regime_shift', 'long_gap', 'close_merge', 'boundary_ambig', 'mixed_hard']
- Propagation strategies: ['strict_threshold_stitching', 'nearest_neighbor_interpolation', 'conservative_boundary_expansion', 'gap_tolerant_merge', 'risk_aware_gap_bridge']
- Tau values: [10, 20, 30, 60]
- Budget values: [0.05, 0.1, 0.2]
- Total observations: 150000

## 1. Propagation Strategy Comparison (All Regimes)

| Propagation | Clip Recall | Clip Prec | IoU | Frag | False Merge | False Split |
|-------------|-------------|-----------|-----|------|-------------|-------------|
| strict_threshold_stitching | 0.000 | 0.913 | 0.000 | 0.064 | 0.00 | 1.00 |
| nearest_neighbor_interpolation | 0.812 | 0.740 | 0.757 | 0.621 | 0.01 | 0.63 |
| conservative_boundary_expansion | 0.955 | 0.882 | 0.903 | 0.241 | 0.01 | 0.24 |
| gap_tolerant_merge | 0.001 | 0.493 | 0.002 | 0.913 | 0.00 | 1.42 |
| risk_aware_gap_bridge | 0.154 | 0.302 | 0.125 | 1.118 | 0.00 | 1.30 |

## 2. Per-Regime Analysis

### Regime: regime_shift

| Propagation | Clip Recall | Clip Prec | IoU | Frag |
|-------------|-------------|-----------|-----|------|
| strict_threshold_stitching | 0.000 | 0.918 | 0.000 | 0.048 |
| nearest_neighbor_interpolation | 0.616 | 0.393 | 0.464 | 1.464 |
| conservative_boundary_expansion | 0.926 | 0.744 | 0.807 | 0.530 |
| gap_tolerant_merge | 0.001 | 0.521 | 0.002 | 0.857 |
| risk_aware_gap_bridge | 0.073 | 0.244 | 0.049 | 1.226 |

### Regime: long_gap

| Propagation | Clip Recall | Clip Prec | IoU | Frag |
|-------------|-------------|-----------|-----|------|
| strict_threshold_stitching | 0.000 | 0.906 | 0.000 | 0.078 |
| nearest_neighbor_interpolation | 0.995 | 0.999 | 0.995 | 0.000 |
| conservative_boundary_expansion | 0.994 | 0.999 | 0.994 | 0.000 |
| gap_tolerant_merge | 0.001 | 0.464 | 0.002 | 0.976 |
| risk_aware_gap_bridge | 0.219 | 0.337 | 0.183 | 1.095 |

### Regime: close_merge

| Propagation | Clip Recall | Clip Prec | IoU | Frag |
|-------------|-------------|-----------|-----|------|
| strict_threshold_stitching | 0.000 | 0.906 | 0.000 | 0.078 |
| nearest_neighbor_interpolation | 0.995 | 0.999 | 0.995 | 0.000 |
| conservative_boundary_expansion | 0.994 | 0.999 | 0.994 | 0.000 |
| gap_tolerant_merge | 0.001 | 0.464 | 0.002 | 0.976 |
| risk_aware_gap_bridge | 0.219 | 0.337 | 0.183 | 1.095 |

### Regime: boundary_ambig

| Propagation | Clip Recall | Clip Prec | IoU | Frag |
|-------------|-------------|-----------|-----|------|
| strict_threshold_stitching | 0.000 | 0.906 | 0.000 | 0.078 |
| nearest_neighbor_interpolation | 0.995 | 0.999 | 0.995 | 0.000 |
| conservative_boundary_expansion | 0.994 | 0.999 | 0.994 | 0.000 |
| gap_tolerant_merge | 0.001 | 0.464 | 0.002 | 0.976 |
| risk_aware_gap_bridge | 0.219 | 0.337 | 0.183 | 1.095 |

### Regime: mixed_hard

| Propagation | Clip Recall | Clip Prec | IoU | Frag |
|-------------|-------------|-----------|-----|------|
| strict_threshold_stitching | 0.000 | 0.928 | 0.000 | 0.036 |
| nearest_neighbor_interpolation | 0.461 | 0.309 | 0.338 | 1.640 |
| conservative_boundary_expansion | 0.866 | 0.670 | 0.727 | 0.672 |
| gap_tolerant_merge | 0.001 | 0.552 | 0.001 | 0.780 |
| risk_aware_gap_bridge | 0.040 | 0.256 | 0.026 | 1.078 |

## 3. Key Questions

### Q1: Was the previous synthetic benchmark too easy?

- NN mean clip recall across all hard regimes: 0.812
- Fraction of cases where NN recall < 0.9: 0.193

**Answer: Yes, significantly harder.** NN recall drops below 85%.

### Q2: Does nearest-neighbor still dominate?

- **regime_shift**: NN rank = 2/5, NN recall = 0.616, Best = conservative_boundary_expansion (0.926)
- **long_gap**: NN rank = 1/5, NN recall = 0.995, Best = nearest_neighbor_interpolation (0.995)
- **close_merge**: NN rank = 1/5, NN recall = 0.995, Best = nearest_neighbor_interpolation (0.995)
- **boundary_ambig**: NN rank = 1/5, NN recall = 0.995, Best = nearest_neighbor_interpolation (0.995)
- **mixed_hard**: NN rank = 2/5, NN recall = 0.461, Best = conservative_boundary_expansion (0.866)

### Q3: Which failure mode is most relevant?

For NN failures (recall < 0.85, n=5788):
- Mean clip recall: 0.027
- Mean clip precision: 0.052
- Mean IoU: 0.037
- Mean fragmentation: 2.275
- Mean false merges: 0.047
- Mean false splits: 2.302

**Primary failure mode: Recall** (missing clips)

### Q4: Is there still a research gap in robust clip reconstruction?

**Yes, there is a research gap.** NN fails significantly on: ['regime_shift', 'mixed_hard']

These regimes create conditions where simple nearest-neighbor interpolation
cannot correctly reconstruct clips. A robust method would need to:
- Handle nonstationary proxy reliability
- Detect and bridge visibility gaps without over-merging
- Maintain boundary precision under ambiguity

### Q5: Should the project continue to real BDD100K data, pivot to semantics, or stop?

**Recommendation: Continue development.**

Clear failure modes have been identified. Next steps:
1. Develop robust reconstruction methods targeting identified failure modes
2. Validate on real data

## Appendix: Detailed Statistics

### By Regime × Tau × Budget

| Regime | Tau | Budget | NN Recall | NN Prec | NN IoU | NN Frag |
|--------|-----|--------|-----------|---------|--------|---------|
| regime_shift | 10 | 0.05 | 0.820 | 0.585 | 0.662 | 0.876 |
| regime_shift | 10 | 0.1 | 0.687 | 0.367 | 0.499 | 1.607 |
| regime_shift | 10 | 0.2 | 0.347 | 0.139 | 0.228 | 2.941 |
| regime_shift | 20 | 0.05 | 0.821 | 0.603 | 0.663 | 0.794 |
| regime_shift | 20 | 0.1 | 0.687 | 0.388 | 0.499 | 1.467 |
| regime_shift | 20 | 0.2 | 0.344 | 0.154 | 0.227 | 2.524 |
| regime_shift | 30 | 0.05 | 0.823 | 0.626 | 0.663 | 0.698 |
| regime_shift | 30 | 0.1 | 0.688 | 0.416 | 0.498 | 1.287 |
| regime_shift | 30 | 0.2 | 0.345 | 0.163 | 0.227 | 2.284 |
| regime_shift | 60 | 0.05 | 0.866 | 0.672 | 0.702 | 0.561 |
| regime_shift | 60 | 0.1 | 0.637 | 0.414 | 0.467 | 1.044 |
| regime_shift | 60 | 0.2 | 0.332 | 0.194 | 0.231 | 1.488 |
| long_gap | 10 | 0.05 | 0.993 | 1.000 | 0.994 | 0.000 |
| long_gap | 10 | 0.1 | 0.994 | 0.999 | 0.994 | 0.000 |
| long_gap | 10 | 0.2 | 0.995 | 1.000 | 0.995 | 0.000 |
| long_gap | 20 | 0.05 | 0.994 | 0.999 | 0.994 | 0.000 |
| long_gap | 20 | 0.1 | 0.994 | 0.999 | 0.994 | 0.000 |
| long_gap | 20 | 0.2 | 0.995 | 1.000 | 0.996 | 0.000 |
| long_gap | 30 | 0.05 | 0.995 | 0.999 | 0.994 | 0.000 |
| long_gap | 30 | 0.1 | 0.994 | 0.999 | 0.995 | 0.000 |
| long_gap | 30 | 0.2 | 0.996 | 0.999 | 0.996 | 0.000 |
| long_gap | 60 | 0.05 | 0.996 | 0.998 | 0.995 | 0.000 |
| long_gap | 60 | 0.1 | 0.995 | 0.999 | 0.995 | 0.000 |
| long_gap | 60 | 0.2 | 0.996 | 0.998 | 0.996 | 0.000 |
| close_merge | 10 | 0.05 | 0.993 | 1.000 | 0.994 | 0.000 |
| close_merge | 10 | 0.1 | 0.994 | 0.999 | 0.994 | 0.000 |
| close_merge | 10 | 0.2 | 0.995 | 1.000 | 0.995 | 0.000 |
| close_merge | 20 | 0.05 | 0.994 | 0.999 | 0.994 | 0.000 |
| close_merge | 20 | 0.1 | 0.994 | 0.999 | 0.994 | 0.000 |
| close_merge | 20 | 0.2 | 0.995 | 1.000 | 0.996 | 0.000 |
| close_merge | 30 | 0.05 | 0.995 | 0.999 | 0.994 | 0.000 |
| close_merge | 30 | 0.1 | 0.994 | 0.999 | 0.995 | 0.000 |
| close_merge | 30 | 0.2 | 0.996 | 0.999 | 0.996 | 0.000 |
| close_merge | 60 | 0.05 | 0.996 | 0.998 | 0.995 | 0.000 |
| close_merge | 60 | 0.1 | 0.995 | 0.999 | 0.995 | 0.000 |
| close_merge | 60 | 0.2 | 0.996 | 0.998 | 0.996 | 0.000 |
| boundary_ambig | 10 | 0.05 | 0.993 | 1.000 | 0.994 | 0.000 |
| boundary_ambig | 10 | 0.1 | 0.994 | 0.999 | 0.994 | 0.000 |
| boundary_ambig | 10 | 0.2 | 0.995 | 1.000 | 0.995 | 0.000 |
| boundary_ambig | 20 | 0.05 | 0.994 | 0.999 | 0.994 | 0.000 |
| boundary_ambig | 20 | 0.1 | 0.994 | 0.999 | 0.994 | 0.000 |
| boundary_ambig | 20 | 0.2 | 0.995 | 1.000 | 0.996 | 0.000 |
| boundary_ambig | 30 | 0.05 | 0.995 | 0.999 | 0.994 | 0.000 |
| boundary_ambig | 30 | 0.1 | 0.994 | 0.999 | 0.995 | 0.000 |
| boundary_ambig | 30 | 0.2 | 0.996 | 0.999 | 0.996 | 0.000 |
| boundary_ambig | 60 | 0.05 | 0.996 | 0.998 | 0.995 | 0.000 |
| boundary_ambig | 60 | 0.1 | 0.995 | 0.999 | 0.995 | 0.000 |
| boundary_ambig | 60 | 0.2 | 0.996 | 0.998 | 0.996 | 0.000 |
| mixed_hard | 10 | 0.05 | 0.736 | 0.490 | 0.570 | 1.135 |
| mixed_hard | 10 | 0.1 | 0.463 | 0.218 | 0.329 | 2.305 |
| mixed_hard | 10 | 0.2 | 0.186 | 0.067 | 0.123 | 4.117 |
| mixed_hard | 20 | 0.05 | 0.736 | 0.509 | 0.571 | 0.998 |
| mixed_hard | 20 | 0.1 | 0.461 | 0.244 | 0.325 | 1.871 |
| mixed_hard | 20 | 0.2 | 0.185 | 0.077 | 0.120 | 3.029 |
| mixed_hard | 30 | 0.05 | 0.737 | 0.540 | 0.571 | 0.840 |
| mixed_hard | 30 | 0.1 | 0.461 | 0.279 | 0.324 | 1.490 |
| mixed_hard | 30 | 0.2 | 0.185 | 0.095 | 0.119 | 2.148 |
| mixed_hard | 60 | 0.05 | 0.737 | 0.613 | 0.570 | 0.481 |
| mixed_hard | 60 | 0.1 | 0.460 | 0.362 | 0.322 | 0.725 |
| mixed_hard | 60 | 0.2 | 0.184 | 0.217 | 0.115 | 0.539 |