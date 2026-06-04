# Factorial Ablation Report: Allocation × Propagation

## Research Question

In relevant clip query processing under synthetic perturbation, what drives robustness:
- **Allocation strategy**: which frames to query with the oracle
- **Propagation strategy**: how to reconstruct clip labels from sparse oracle queries

## Configuration

- Sample size: 100 videos per seed
- Seeds: 5 (seeds 42-46)
- K (min vehicles): 3
- tau (min frames): 30
- Budget: 0.1 (10% of frames queried)
- Total combinations: 6 allocation × 5 propagation = 30
- Total observations: 15,000

## Key Findings

### 1. Propagation dominates allocation

| Factor | Effect Range (max - min mean clip recall) |
|--------|------------------------------------------|
| Propagation | 0.9924 |
| Allocation | 0.1951 |

**Propagation strategy has ~5x larger impact than allocation strategy.**

### 2. Propagation strategy ranking (mean clip recall)

| Propagation | Clip Recall | Fragmentation | Notes |
|-------------|-------------|---------------|-------|
| nearest_neighbor_interpolation | 0.9961 | 0.0000 | Best overall |
| conservative_boundary_expansion | 0.9922 | 0.0000 | Close second |
| risk_aware_gap_bridge | 0.2107 | 1.3961 | Moderate |
| gap_tolerant_merge | 0.0076 | 0.9959 | Poor |
| strict_threshold_stitching | 0.0037 | 0.8327 | Poor |

### 3. Allocation strategy ranking (mean clip recall)

| Allocation | Clip Recall | Notes |
|------------|-------------|-------|
| fixed_rate | 0.5964 | Best (deterministic sampling) |
| boundary_focused | 0.4248 | Second |
| hidden_risk | 0.4219 | Third |
| proxy_uncertainty | 0.4045 | |
| proxy_threshold | 0.4034 | |
| uniform | 0.4013 | Baseline |

### 4. hidden_risk vs uniform (same propagation)

| Propagation | uniform | hidden_risk | Difference | Verdict |
|-------------|---------|-------------|------------|---------|
| strict_threshold_stitching | 0.0000 | 0.0190 | +0.0190 | Marginal |
| nearest_neighbor_interpolation | 0.9957 | 0.9973 | +0.0017 | Similar |
| gap_tolerant_merge | 0.0000 | 0.0337 | +0.0337 | Marginal |
| risk_aware_gap_bridge | 0.0200 | 0.0640 | +0.0440 | Marginal |
| conservative_boundary_expansion | 0.9907 | 0.9957 | +0.0050 | Similar |

**hidden_risk allocation provides minimal improvement over uniform, typically <0.05.**

### 5. nearest_neighbor_interpolation universality

| Allocation | NN Rank | NN Clip Recall |
|------------|---------|----------------|
| uniform | 1/5 | 0.9957 |
| fixed_rate | 1/5 | 0.9970 |
| proxy_threshold | 1/5 | 0.9947 |
| proxy_uncertainty | 1/5 | 0.9977 |
| hidden_risk | 1/5 | 0.9973 |
| boundary_focused | 2/5 | 0.9943 |

**nearest_neighbor_interpolation is consistently the best or second-best propagation strategy across all allocation methods.**

### 6. gap_tolerant_merge fragmentation analysis

| Allocation | NN Fragmentation | GT Fragmentation | Change |
|------------|------------------|------------------|--------|
| uniform | 0.0000 | 0.0340 | +0.0340 |
| fixed_rate | 0.0000 | 0.0000 | 0.0000 |
| proxy_threshold | 0.0000 | 1.2617 | +1.2617 |
| proxy_uncertainty | 0.0000 | 1.2240 | +1.2240 |
| hidden_risk | 0.0000 | 2.0010 | +2.0010 |
| boundary_focused | 0.0000 | 1.4547 | +1.4547 |

**gap_tolerant_merge INCREASES fragmentation in most cases.** This is counter-intuitive and suggests the current implementation may be merging incorrectly.

### 7. risk_aware_gap_bridge vs gap_tolerant_merge

| Allocation | GT Merge | Risk Bridge | Improvement |
|------------|----------|-------------|-------------|
| uniform | 0.0000 | 0.0200 | +0.0200 |
| fixed_rate | 0.0000 | 0.9953 | +0.9953 |
| proxy_threshold | 0.0040 | 0.0270 | +0.0230 |
| proxy_uncertainty | 0.0020 | 0.0300 | +0.0280 |
| hidden_risk | 0.0337 | 0.0640 | +0.0303 |
| boundary_focused | 0.0060 | 0.1277 | +0.0217 |

**risk_aware_gap_bridge consistently outperforms gap_tolerant_merge**, but both are far worse than nearest_neighbor_interpolation.

## Interpretation

### Why is nearest_neighbor_interpolation so dominant?

The synthetic perturbation creates **short, isolated label errors**. Nearest-neighbor interpolation:
1. Smoothly fills gaps between correctly-labeled frames
2. Doesn't attempt risky "bridging" that can merge unrelated segments
3. Works well when oracle budget is distributed randomly (as in uniform/proxy methods)

### Why do gap-tolerant methods fail?

1. **gap_tolerant_merge** creates false merges between unrelated positive segments
2. **risk_aware_gap_bridge** is better but still too aggressive
3. The synthetic perturbation doesn't create the "visibility drop" scenarios these methods target

### Why does allocation have limited effect?

With budget=0.1 (30 frames out of 300), even random sampling captures enough structure. The **propagation strategy determines how this sparse information is expanded**, not which frames were sampled.

## Research Direction Assessment

Based on the decision rules:

### A. Propagation dominates allocation: **CONFIRMED**

The propagation effect range (0.99) is ~5x larger than allocation effect range (0.20).

### B. gap_tolerant_merge reduces fragmentation: **REJECTED**

gap_tolerant_merge actually INCREASES fragmentation in most cases.

### C. hidden_risk outperforms uniform: **NOT SUPPORTED**

hidden_risk shows only marginal improvement (<0.05) over uniform under the same propagation.

### D. All methods show unstable differences: **PARTIALLY SUPPORTED**

The top methods (nearest_neighbor, conservative_boundary) are consistently good, but the bottom methods are consistently bad. The ranking is stable.

### E. nearest-neighbor is near-perfect: **CONFIRMED**

This raises concerns about problem difficulty. Two interpretations:
1. The synthetic perturbation is too easy
2. The budget (0.1) is sufficient for this task difficulty

## Recommendations

### Immediate conclusions

1. **Allocation strategy is secondary.** The choice of which frames to oracle-query matters much less than how labels are propagated.

2. **nearest_neighbor_interpolation is a strong baseline.** Any new method must beat it convincingly.

3. **Gap-tolerant methods need redesign.** Current implementations increase fragmentation rather than reducing it.

### Next steps for research direction

Given these results, the research contribution should **NOT** focus on:
- Motion-conditioned oracle allocation (minimal impact)
- Gap-tolerant merge (doesn't work as intended)

Potential directions:
1. **Make perturbation harder**: Increase noise, add longer visibility drops, or use non-stationary noise to challenge nearest_neighbor
2. **Focus on boundary precision**: conservative_boundary_expansion is close to nearest_neighbor; boundary refinement could be the differentiator
3. **Reconsider the problem setting**: If synthetic perturbation is too easy, consider real moving-camera data or more realistic synthetic models

## Caveats

1. **Synthetic data only**: Results may not transfer to real moving-camera videos
2. **Single query type**: Only tested count(vehicle) >= K
3. **Budget fixed at 0.1**: Different budgets may show different patterns
4. **Metric limitations**: IoU threshold 0.5 may miss boundary-sensitive failures

**These results indicate where to look, not what to claim.**

---

## Appendix: Top 15 Combinations

| Rank | Combination | Clip Recall | Fragmentation | IoU |
|------|-------------|-------------|---------------|-----|
| 1 | proxy_uncertainty + nearest_neighbor | 0.9977 | 0.0000 | 0.9967 |
| 2 | hidden_risk + nearest_neighbor | 0.9973 | 0.0000 | 0.9961 |
| 3 | fixed_rate + nearest_neighbor | 0.9970 | 0.0000 | 0.9965 |
| 4 | uniform + nearest_neighbor | 0.9957 | 0.0000 | 0.9954 |
| 5 | hidden_risk + conservative_boundary | 0.9957 | 0.0000 | 0.9957 |
| 6 | fixed_rate + risk_aware_bridge | 0.9953 | 0.0000 | 0.9673 |
| 7 | boundary_focused + conservative_boundary | 0.9950 | 0.0000 | 0.9944 |
| 8 | proxy_threshold + nearest_neighbor | 0.9947 | 0.0000 | 0.9937 |
| 9 | boundary_focused + nearest_neighbor | 0.9943 | 0.0000 | 0.9948 |
| 10 | proxy_uncertainty + conservative_boundary | 0.9917 | 0.0000 | 0.9902 |
| 11 | uniform + conservative_boundary | 0.9907 | 0.0000 | 0.9902 |
| 12 | proxy_threshold + conservative_boundary | 0.9903 | 0.0000 | 0.9900 |
| 13 | fixed_rate + conservative_boundary | 0.9897 | 0.0000 | 0.9879 |
| 14 | boundary_focused + risk_aware_bridge | 0.1277 | 1.8089 | 0.1020 |
| 15 | proxy_threshold + risk_aware_bridge | 0.0270 | 1.8522 | 0.0364 |
