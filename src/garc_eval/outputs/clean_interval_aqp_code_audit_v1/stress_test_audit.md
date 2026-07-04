# Stress Test Audit

Verdict: **PASS**

Score distributions:

| stress_test | mean | std | min | max | top20_positive_rate |
| --- | --- | --- | --- | --- | --- |
| best_proxy | 0.161892 | 0.2687 | 0 | 1 | 1 |
| noisy_proxy | 0.517667 | 0.139418 | 0 | 1 | 0.05 |
| partial_inverted_proxy | 0.424435 | 0.230022 | 0 | 1 | 0 |
| low_density_blindspot_proxy | 0.163316 | 0.260666 | 0 | 1 | 0 |
| random_proxy | 0.496226 | 0.290298 | 0.000102587 | 0.999998 | 0 |

Result aggregates:

| stress_test | recall | precision | returned |
| --- | --- | --- | --- |
| best_proxy | 0.048 | 0.96 | 0.96 |
| low_density_blindspot_proxy | 0 | 0 | 0 |
| noisy_proxy | 0.002 | 0.04 | 0.2 |
| partial_inverted_proxy | 0 | 0 | 0 |
| random_proxy | 0 | 0 | 0.48 |
