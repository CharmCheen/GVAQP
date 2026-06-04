# Synthetic Clip Degradation Experiment Report

## Configuration

- Sample size: 20
- K (min vehicles): 3
- tau (min frames): 30
- Budget: 0.1
- Num videos: 20

## Method Comparison

| Method | Frame Recall | Frame Prec | Clip Recall | Clip Prec | Mean IoU | Frag Rate | Oracle Frac |
|--------|-------------|------------|-------------|-----------|----------|-----------|-------------|
| arc_clustering | 0.912 | 0.996 | 0.050 | 0.050 | 0.046 | 1.775 | 0.043 |
| fixed_rate | 1.000 | 1.000 | 1.000 | 1.000 | 0.999 | 0.000 | 0.100 |
| full_oracle | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |
| proxy_threshold | 0.962 | 0.994 | 0.375 | 0.208 | 0.274 | 1.525 | 0.100 |
| uniform_random | 0.999 | 0.998 | 0.975 | 1.000 | 0.976 | 0.000 | 0.100 |

## Boundary Errors (frames)

| Method | Mean Start Error | Mean End Error |
|--------|-----------------|----------------|
| arc_clustering | 23.0 | 0.0 |
| fixed_rate | 0.1 | 0.1 |
| full_oracle | 0.0 | 0.0 |
| proxy_threshold | 20.5 | 69.8 |
| uniform_random | 0.0 | 7.2 |

## Degradation Analysis

### Frame-level vs Clip-level Degradation (relative to oracle)

| Method | Frame Recall Drop | Clip Recall Drop | Clip Drop / Frame Drop |
|--------|------------------|-----------------|----------------------|
| arc_clustering | 0.088 | 0.950 | 10.81 |
| fixed_rate | 0.000 | 0.000 | 0.00 |
| proxy_threshold | 0.038 | 0.625 | 16.33 |
| uniform_random | 0.001 | 0.025 | 20.00 |

### Verdict

**Yes**: Clip-level degradation is substantially larger than frame-level degradation. This confirms that perturbation compounds at the clip level — small frame-level errors cascade into clip-level misses.

## Conclusion

This pipeline successfully measures whether label-level perturbation causes disproportionate clip-level degradation. The results above show the relative impact on frame-level vs clip-level metrics across different baseline methods.
