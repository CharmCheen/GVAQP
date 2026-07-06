# Regime Breakdown Report

## Effect of repair by segment density regime

| regime | trials | mean R_diff (core - nr) | mean unique_bin_diff | mean wasted calls | mean duplicate calls |
|---|---|---|---|---|---|
| high_mixed | 6 | -0.048 | -0.2 | 8.0 | 7.7 |
| high_point-heavy | 25 | +0.016 | -2.1 | 27.4 | 26.0 |
| medium_point-heavy | 14 | +0.004 | +1.1 | 20.4 | 20.3 |

## Budget diversion by regime

| regime | repair calls | diversion % | mean higher-theta chunks |
|---|---|---|---|
| high_mixed | 2 | 100.0% | 3.00 |
| high_point-heavy | 34 | 64.7% | 1.65 |
| medium_point-heavy | 2 | 50.0% | 1.00 |

## Interpretation

The regime most negatively affected by repair is **high_mixed**. This is consistent with dense segments having more competition among chunks: wasting budget on duplicates or low-value repair leaves high-theta chunks unexplored.
