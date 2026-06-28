# Temporal Oracle Allocation Study

## Executive Summary

This study explores whether temporal-aware oracle allocation can reduce event disappearance and clip collapse more efficiently than frame-wise allocation.

**Key finding:** While oracle value IS temporally non-uniform (boundaries carry more information than interiors), naive temporal-aware allocation strategies that merely reweight proxy scores fail catastrophically. Only SUPG-style importance sampling with oracle verification achieves low disappearance rates.

## 1. Is Oracle Value Temporally Non-Uniform?

### Temporal Autocorrelation

Oracle labels show strong temporal autocorrelation, indicating non-uniform value:

- Lag-1 correlation: 0.340
- Lag-5 correlation: 0.275
- Lag-10 correlation: 0.158

### Interior vs Boundary Entropy

- Mean interior entropy: 0.068
- Mean boundary entropy: 0.632
- Boundary/interior ratio: 9.345

**Conclusion:** Oracle labels are highly temporally correlated. Adjacent frames provide redundant information, while boundaries carry ~9x more information per frame.

## 2. Are Event Boundaries More Valuable Than Interiors?

| Position | N Frames | Mean Consistency | Positive Rate |
|----------|----------|------------------|---------------|
| start_boundary | 126 | 0.529 | 1.000 |
| end_boundary | 126 | 0.532 | 1.000 |
| interior | 886 | 1.000 | 1.000 |
| between_events | 4773 | 0.897 | 0.078 |

**Conclusion:** Event boundaries show lower local consistency (0.53) than interiors (1.00), confirming they carry more information per oracle query. Between-event regions show moderate consistency (0.90) with low positive rate (0.08).

## 3. Can Temporal-Aware Allocation Reduce Disappearance?

| Strategy | Disappearance Rate | Clip Recall | Frame Recall | Gap |
|----------|-------------------|-------------|--------------|-----|
| boundary_aware | 1.000 | 0.000 | 0.122 | +0.122 |
| burst_aware | 1.000 | 0.000 | 0.055 | +0.055 |
| redundancy_aware | 1.000 | 0.000 | 0.119 | +0.119 |
| supg_importance | 0.037 | 0.963 | 0.978 | +0.016 |
| temporal_smoothing | 1.000 | 0.000 | 0.131 | +0.131 |
| uniform | 1.000 | 0.000 | 0.103 | +0.103 |

**Critical finding:** Naive temporal-aware strategies (boundary_aware, burst_aware, redundancy_aware, temporal_smoothing) ALL produce disappearance rate = 1.000 — every clip vanishes. Only SUPG importance sampling achieves low disappearance (0.037). The key factor is oracle verification, not temporal reweighting.

## 4. Which Strategies Help Most?

### Budget Sweep

- budget=0.01: Best = supg_importance (disappearance=0.000)
- budget=0.05: Best = supg_importance (disappearance=0.011)
- budget=0.1: Best = supg_importance (disappearance=0.037)
### Coverage Sweep

- coverage=0.5: Best = supg_importance (disappearance=0.000)
- coverage=0.9: Best = supg_importance (disappearance=0.037)
- coverage=1.0: Best = supg_importance (disappearance=0.053)
### Clip Length Sweep

- clip_length=3.0: Best = supg_importance (disappearance=0.037)
- clip_length=20.0: Best = supg_importance (disappearance=0.238)
- clip_length=50.0: Best = supg_importance (disappearance=0.000)

**Conclusion:** SUPG importance sampling dominates in ALL regimes. Temporal reweighting strategies fail because they do not incorporate oracle verification — they merely redistribute sampling probability without learning.

## 5. Is Frame-wise IID Allocation Fundamentally Inefficient?

- Uniform (iid) disappearance rate: 1.000
- SUPG importance disappearance rate: 0.037
- Improvement: 0.963

**Conclusion:** Frame-wise iid allocation IS fundamentally inefficient — it produces disappearance rate of 1.0 (every clip vanishes). However, the solution is not temporal reweighting but importance sampling with oracle verification. The inefficiency comes from the lack of adaptive sampling, not from ignoring temporal structure per se.

## 6. Is There Evidence for a Future Temporal-Aware AQP System?

### Evidence That Temporal Structure Matters

- Oracle labels show strong temporal autocorrelation (lag-1 = 0.34)
- Event boundaries carry ~9x more information than interiors
- Adjacent frames are highly redundant (oracle value is non-uniform)

### Evidence That Temporal Awareness Alone Is Insufficient

- ALL naive temporal-aware strategies produce disappearance = 1.0
- Reweighting proxy scores without oracle verification fails completely
- SUPG's success comes from importance sampling + verification, not temporal structure

### Recommendation

The evidence does NOT support a standalone temporal-aware allocation system. However, temporal structure could enhance an already-correct importance sampling framework. Future work should investigate:

1. **Temporal importance sampling**: Using temporal autocorrelation to improve the proxy-to-oracle mapping in SUPG-style systems
2. **Boundary-aware verification**: Prioritizing oracle queries at event boundaries within an importance sampling framework
3. **Redundancy-aware budget allocation**: Skipping redundant adjacent frames when the proxy is confident, to free budget for boundary verification

The key insight is that temporal awareness must be integrated WITH oracle verification, not as a replacement for it.
