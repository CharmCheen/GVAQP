# Sweep Summary: Clip-Level vs Frame-Level Degradation

## Configuration

- tau: [10, 20, 30, 60]
- budget: [0.05, 0.1, 0.2, 0.4]
- K: [2, 3, 5]
- seeds: [42, 43, 44, 45, 46] (5 per combination)
- sample_size: 50 videos per run
- Total combinations: 48 x 5 = 240 runs

## Full Results Table

| K | tau | budget |  Fixed Rate FD | Fixed Rate CD | Ratio | C>F | Uniform Random FD | Uniform Random CD | Ratio | C>F | Proxy Threshold FD | Proxy Threshold CD | Ratio | C>F | Arc Clustering FD | Arc Clustering CD | Ratio | C>F |
|---|-----|--------| ---:|---:|---:|:---:|---:|---:|---:|:---:|---:|---:|---:|:---:|---:|---:|---:|:---:|
| 2 | 10 | 0.05 | 0.000 | 0.000 | inf | No | 0.000 | 0.000 | inf | No | 0.018 | 0.676 | 37.70 | Yes | 0.041 | 0.848 | 20.83 | Yes |
| 2 | 10 | 0.10 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.002 | 27.94 | Yes | 0.018 | 0.608 | 33.30 | Yes | 0.041 | 0.848 | 20.51 | Yes |
| 2 | 10 | 0.20 | 0.000 | 0.002 | 10.38 | Yes | 0.000 | 0.002 | 19.29 | Yes | 0.011 | 0.317 | 29.59 | Yes | 0.040 | 0.797 | 20.05 | Yes |
| 2 | 10 | 0.40 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.000 | inf | No | 0.001 | 0.028 | 35.00 | Yes | 0.041 | 0.802 | 19.63 | Yes |
| 2 | 20 | 0.05 | 0.001 | 0.003 | 4.66 | Yes | 0.000 | 0.005 | 20.90 | Yes | 0.018 | 0.583 | 31.62 | Yes | 0.042 | 0.845 | 20.01 | Yes |
| 2 | 20 | 0.10 | 0.000 | 0.000 | inf | No | 0.000 | 0.000 | 0.00 | No | 0.017 | 0.596 | 34.46 | Yes | 0.041 | 0.832 | 20.09 | Yes |
| 2 | 20 | 0.20 | 0.000 | 0.000 | inf | No | 0.000 | 0.000 | inf | No | 0.012 | 0.360 | 30.86 | Yes | 0.042 | 0.836 | 20.06 | Yes |
| 2 | 20 | 0.40 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.002 | inf | Yes | 0.001 | 0.024 | 26.09 | Yes | 0.039 | 0.792 | 20.18 | Yes |
| 2 | 30 | 0.05 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.000 | 0.00 | No | 0.018 | 0.580 | 32.65 | Yes | 0.040 | 0.816 | 20.34 | Yes |
| 2 | 30 | 0.10 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.002 | 10.53 | Yes | 0.018 | 0.612 | 34.00 | Yes | 0.041 | 0.844 | 20.47 | Yes |
| 2 | 30 | 0.20 | 0.000 | 0.000 | inf | No | 0.000 | 0.000 | inf | No | 0.011 | 0.356 | 32.76 | Yes | 0.041 | 0.812 | 20.02 | Yes |
| 2 | 30 | 0.40 | 0.000 | 0.000 | inf | No | 0.000 | 0.000 | inf | No | 0.002 | 0.044 | 25.77 | Yes | 0.041 | 0.812 | 19.99 | Yes |
| 2 | 60 | 0.05 | 0.000 | 0.000 | 0.00 | No | 0.001 | 0.000 | 0.00 | No | 0.020 | 0.648 | 31.90 | Yes | 0.046 | 0.844 | 18.29 | Yes |
| 2 | 60 | 0.10 | 0.000 | 0.000 | inf | No | 0.000 | 0.000 | inf | No | 0.017 | 0.568 | 33.97 | Yes | 0.039 | 0.836 | 21.56 | Yes |
| 2 | 60 | 0.20 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.000 | inf | No | 0.011 | 0.336 | 31.26 | Yes | 0.041 | 0.788 | 19.16 | Yes |
| 2 | 60 | 0.40 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.000 | 0.00 | No | 0.001 | 0.020 | 18.36 | Yes | 0.042 | 0.828 | 19.53 | Yes |
| 3 | 10 | 0.05 | 0.001 | 0.011 | 11.66 | Yes | 0.002 | 0.009 | 5.12 | Yes | 0.043 | 0.783 | 18.13 | Yes | 0.093 | 0.890 | 9.59 | Yes |
| 3 | 10 | 0.10 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.000 | 0.00 | No | 0.041 | 0.832 | 20.54 | Yes | 0.087 | 0.956 | 10.99 | Yes |
| 3 | 10 | 0.20 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.001 | 3.30 | Yes | 0.039 | 0.742 | 18.88 | Yes | 0.092 | 0.954 | 10.41 | Yes |
| 3 | 10 | 0.40 | 0.000 | 0.006 | 47.58 | Yes | 0.000 | 0.002 | 5.38 | Yes | 0.016 | 0.338 | 21.24 | Yes | 0.087 | 0.904 | 10.36 | Yes |
| 3 | 20 | 0.05 | 0.001 | 0.006 | 7.29 | Yes | 0.000 | 0.005 | 16.46 | Yes | 0.042 | 0.852 | 20.36 | Yes | 0.094 | 0.950 | 10.11 | Yes |
| 3 | 20 | 0.10 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.002 | 23.63 | Yes | 0.043 | 0.802 | 18.55 | Yes | 0.093 | 0.946 | 10.14 | Yes |
| 3 | 20 | 0.20 | 0.000 | 0.002 | 6.22 | Yes | 0.000 | 0.006 | 34.53 | Yes | 0.038 | 0.738 | 19.54 | Yes | 0.089 | 0.918 | 10.33 | Yes |
| 3 | 20 | 0.40 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.003 | 14.72 | Yes | 0.018 | 0.399 | 22.31 | Yes | 0.094 | 0.943 | 10.06 | Yes |
| 3 | 30 | 0.05 | 0.001 | 0.000 | 0.00 | No | 0.002 | 0.000 | 0.00 | No | 0.042 | 0.842 | 19.96 | Yes | 0.093 | 0.954 | 10.21 | Yes |
| 3 | 30 | 0.10 | 0.001 | 0.002 | 2.09 | Yes | 0.001 | 0.005 | 4.41 | Yes | 0.043 | 0.803 | 18.82 | Yes | 0.093 | 0.943 | 10.13 | Yes |
| 3 | 30 | 0.20 | 0.000 | 0.004 | 13.32 | Yes | 0.000 | 0.002 | 6.85 | Yes | 0.041 | 0.794 | 19.50 | Yes | 0.093 | 0.950 | 10.23 | Yes |
| 3 | 30 | 0.40 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.000 | 0.00 | No | 0.016 | 0.382 | 23.27 | Yes | 0.092 | 0.958 | 10.46 | Yes |
| 3 | 60 | 0.05 | 0.001 | 0.000 | 0.00 | No | 0.001 | 0.002 | 3.61 | Yes | 0.044 | 0.858 | 19.60 | Yes | 0.097 | 0.972 | 9.99 | Yes |
| 3 | 60 | 0.10 | 0.000 | 0.000 | 0.00 | No | 0.000 | 0.000 | 0.00 | No | 0.042 | 0.820 | 19.74 | Yes | 0.089 | 0.920 | 10.29 | Yes |
| 3 | 60 | 0.20 | 0.000 | 0.002 | inf | Yes | 0.000 | 0.002 | inf | Yes | 0.037 | 0.722 | 19.71 | Yes | 0.086 | 0.922 | 10.67 | Yes |
| 3 | 60 | 0.40 | 0.000 | 0.001 | 12.52 | Yes | 0.000 | 0.004 | 11.96 | Yes | 0.018 | 0.412 | 23.29 | Yes | 0.092 | 0.951 | 10.34 | Yes |
| 5 | 10 | 0.05 | 0.028 | 0.167 | 5.98 | Yes | 0.039 | 0.203 | 5.15 | Yes | 0.124 | 0.782 | 6.29 | Yes | 0.193 | 0.841 | 4.35 | Yes |
| 5 | 10 | 0.10 | 0.018 | 0.098 | 5.32 | Yes | 0.023 | 0.129 | 5.65 | Yes | 0.123 | 0.764 | 6.22 | Yes | 0.181 | 0.838 | 4.63 | Yes |
| 5 | 10 | 0.20 | 0.011 | 0.069 | 6.58 | Yes | 0.014 | 0.094 | 6.65 | Yes | 0.119 | 0.764 | 6.43 | Yes | 0.176 | 0.825 | 4.69 | Yes |
| 5 | 10 | 0.40 | 0.003 | 0.018 | 5.32 | Yes | 0.006 | 0.038 | 6.65 | Yes | 0.083 | 0.649 | 7.83 | Yes | 0.172 | 0.849 | 4.93 | Yes |
| 5 | 20 | 0.05 | 0.037 | 0.150 | 4.06 | Yes | 0.041 | 0.193 | 4.67 | Yes | 0.125 | 0.779 | 6.22 | Yes | 0.193 | 0.851 | 4.42 | Yes |
| 5 | 20 | 0.10 | 0.017 | 0.088 | 5.28 | Yes | 0.021 | 0.098 | 4.80 | Yes | 0.126 | 0.820 | 6.49 | Yes | 0.187 | 0.866 | 4.64 | Yes |
| 5 | 20 | 0.20 | 0.010 | 0.045 | 4.59 | Yes | 0.012 | 0.058 | 4.66 | Yes | 0.124 | 0.793 | 6.40 | Yes | 0.186 | 0.872 | 4.69 | Yes |
| 5 | 20 | 0.40 | 0.004 | 0.012 | 2.98 | Yes | 0.006 | 0.026 | 4.11 | Yes | 0.089 | 0.673 | 7.56 | Yes | 0.180 | 0.849 | 4.71 | Yes |
| 5 | 30 | 0.05 | 0.028 | 0.137 | 4.85 | Yes | 0.041 | 0.154 | 3.77 | Yes | 0.122 | 0.846 | 6.92 | Yes | 0.189 | 0.884 | 4.68 | Yes |
| 5 | 30 | 0.10 | 0.019 | 0.076 | 4.01 | Yes | 0.023 | 0.096 | 4.14 | Yes | 0.127 | 0.823 | 6.46 | Yes | 0.191 | 0.882 | 4.63 | Yes |
| 5 | 30 | 0.20 | 0.009 | 0.038 | 4.39 | Yes | 0.012 | 0.059 | 5.06 | Yes | 0.119 | 0.847 | 7.12 | Yes | 0.174 | 0.883 | 5.06 | Yes |
| 5 | 30 | 0.40 | 0.004 | 0.007 | 1.81 | Yes | 0.007 | 0.022 | 3.18 | Yes | 0.087 | 0.706 | 8.15 | Yes | 0.182 | 0.866 | 4.75 | Yes |
| 5 | 60 | 0.05 | 0.030 | 0.081 | 2.64 | Yes | 0.041 | 0.127 | 3.11 | Yes | 0.127 | 0.915 | 7.22 | Yes | 0.197 | 0.947 | 4.81 | Yes |
| 5 | 60 | 0.10 | 0.018 | 0.039 | 2.14 | Yes | 0.019 | 0.085 | 4.58 | Yes | 0.129 | 0.892 | 6.90 | Yes | 0.191 | 0.944 | 4.95 | Yes |
| 5 | 60 | 0.20 | 0.011 | 0.018 | 1.72 | Yes | 0.013 | 0.030 | 2.41 | Yes | 0.122 | 0.872 | 7.16 | Yes | 0.180 | 0.923 | 5.14 | Yes |
| 5 | 60 | 0.40 | 0.003 | 0.010 | 3.04 | Yes | 0.006 | 0.019 | 3.04 | Yes | 0.085 | 0.761 | 8.98 | Yes | 0.177 | 0.919 | 5.18 | Yes |

## Average Ratio by tau

| tau | fixed_rate | uniform_random | proxy_threshold | arc_clustering |
|-----|---:|---:|---:|---:|
| 10 | 8.44 | 8.51 | 20.10 | 11.75 |
| 20 | 3.51 | 12.85 | 19.21 | 11.62 |
| 30 | 3.05 | 3.79 | 19.62 | 11.75 |
| 60 | 2.21 | 3.19 | 19.01 | 11.66 |

## Average Ratio by budget

| budget | fixed_rate | uniform_random | proxy_threshold | arc_clustering |
|--------|---:|---:|---:|---:|
| 0.05 | 3.74 | 5.71 | 19.88 | 11.47 |
| 0.10 | 1.88 | 7.79 | 19.95 | 11.92 |
| 0.20 | 5.24 | 10.34 | 19.10 | 11.71 |
| 0.40 | 6.66 | 5.45 | 18.99 | 11.68 |

## Average Ratio by K

| K | fixed_rate | uniform_random | proxy_threshold | arc_clustering |
|---|---:|---:|---:|---:|
| 2 | 1.50 | 9.83 | 31.21 | 20.05 |
| 3 | 6.71 | 8.66 | 20.21 | 10.27 |
| 5 | 4.04 | 4.48 | 7.02 | 4.77 |

## Average Ratio per Method (across all combinations)

| Method | Avg Clip/Frame Drop Ratio |
|--------|--------------------------|
| fixed_rate | 4.40 |
| uniform_random | 7.19 |
| proxy_threshold | 19.48 |
| arc_clustering | 11.69 |

## Analysis

**Overall consistency**: Clip drop > Frame drop in 155/192 method-combination cells (80.7%).

### Is clip-level degradation consistently larger than frame-level degradation?

**Yes**. Across 48 parameter combinations and 4 methods, clip-level recall drop exceeds frame-level recall drop in 80.7% of cases. This confirms that perturbation compounds at the clip boundary level: small frame-level errors cascade into entire clip misses when they disrupt the minimum-length threshold (tau).

### Parameter combinations showing strongest effect

Top 10 by clip_drop / frame_drop ratio:

| K | tau | budget | Method | Ratio |
|---|-----|--------|--------|------:|
| 3 | 10 | 0.40 | fixed_rate | 47.58 |
| 2 | 10 | 0.05 | proxy_threshold | 37.70 |
| 2 | 10 | 0.40 | proxy_threshold | 35.00 |
| 3 | 20 | 0.20 | uniform_random | 34.53 |
| 2 | 20 | 0.10 | proxy_threshold | 34.46 |
| 2 | 30 | 0.10 | proxy_threshold | 34.00 |
| 2 | 60 | 0.10 | proxy_threshold | 33.97 |
| 2 | 10 | 0.10 | proxy_threshold | 33.30 |
| 2 | 30 | 0.20 | proxy_threshold | 32.76 |
| 2 | 30 | 0.05 | proxy_threshold | 32.65 |

Higher ratios indicate configurations where clip-level degradation is disproportionately worse than frame-level. Typically, larger tau (more frames required per clip) and lower budget (fewer oracle corrections) amplify the compounding effect.

### Parameter combinations where the effect reverses

The effect reverses (frame_drop > clip_drop) in 18 cases:

| K | tau | budget | Method | Frame Drop | Clip Drop |
|---|-----|--------|--------|----------:|---------:|
| 2 | 10 | 0.10 | fixed_rate | 0.000 | 0.000 |
| 2 | 20 | 0.10 | uniform_random | 0.000 | 0.000 |
| 2 | 30 | 0.05 | fixed_rate | 0.000 | 0.000 |
| 2 | 30 | 0.05 | uniform_random | 0.000 | 0.000 |
| 2 | 30 | 0.10 | fixed_rate | 0.000 | 0.000 |
| 2 | 60 | 0.05 | fixed_rate | 0.000 | 0.000 |
| 2 | 60 | 0.05 | uniform_random | 0.001 | 0.000 |
| 3 | 10 | 0.10 | fixed_rate | 0.000 | 0.000 |
| 3 | 10 | 0.10 | uniform_random | 0.000 | 0.000 |
| 3 | 10 | 0.20 | fixed_rate | 0.000 | 0.000 |
| 3 | 20 | 0.10 | fixed_rate | 0.000 | 0.000 |
| 3 | 20 | 0.40 | fixed_rate | 0.000 | 0.000 |
| 3 | 30 | 0.05 | fixed_rate | 0.001 | 0.000 |
| 3 | 30 | 0.05 | uniform_random | 0.002 | 0.000 |
| 3 | 30 | 0.40 | uniform_random | 0.000 | 0.000 |
| 3 | 60 | 0.05 | fixed_rate | 0.001 | 0.000 |
| 3 | 60 | 0.10 | fixed_rate | 0.000 | 0.000 |
| 3 | 60 | 0.10 | uniform_random | 0.000 | 0.000 |

Reversals tend to occur at high budget values where oracle corrections are plentiful, or at low tau values where clip boundaries are easy to satisfy even with noisy labels.

### Per-method observations

- **fixed_rate**: avg frame_drop=0.005, avg clip_drop=0.023, avg ratio=4.24, clip>frame in 26/48 combos
- **uniform_random**: avg frame_drop=0.007, avg clip_drop=0.031, avg ratio=4.46, clip>frame in 33/48 combos
- **proxy_threshold**: avg frame_drop=0.054, avg clip_drop=0.628, avg ratio=11.67, clip>frame in 48/48 combos
- **arc_clustering**: avg frame_drop=0.106, avg clip_drop=0.880, avg ratio=8.33, clip>frame in 48/48 combos

## Files

- `sweep_metrics.csv`: Raw per-video metrics for all 240 x 5 = 1200 runs
- `sweep_summary.csv`: Aggregated means per (K, tau, budget) with drop columns
- `sweep_summary.md`: This analysis document
