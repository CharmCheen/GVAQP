# 05 Certificate Simulation

## Mechanics

The simulation estimates total positives with block-level stratified estimators using only known-probability random/calibration/audit samples. Proxy-ranked exploitation samples are excluded from the population-rate estimator.

Compared methods: uniform_random, uniform_temporal_grid, top_proxy_object_count_mean, and the best BASA_two_channel configuration at B=80.

## Limitation

This is not a formal G-ARC certificate. It is a mechanics check for missed-positive risk accounting under block sampling. Proxy-biased selections cannot directly estimate population positives without inclusion-probability correction.

See `analysis/certificate_simulation.csv` and `analysis/block_level_estimates.csv`.
