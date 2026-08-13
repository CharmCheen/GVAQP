# Cluster statistical analysis

The video-query cluster is the statistical unit. Proxy cells are median-collapsed within each cluster before the 10,000-replicate bootstrap and leave-out analyses. No budget cells, traces, or proxy rows are resampled independently. This is a read-only analysis of P2 cached replay outputs.

```json
{
  "delta_AnytimeAUC": {
    "bootstrap_probability_median_ge_practical_threshold": 0.3497,
    "ci95_median": [
      -0.012680155305849927,
      0.011702019227756127
    ],
    "observed_median": 0.007912120399960934
  },
  "delta_EventRecall": {
    "bootstrap_probability_median_ge_practical_threshold": 0.0096,
    "ci95_median": [
      -0.010638297872340425,
      0.019733924611973375
    ],
    "observed_median": 0.0
  },
  "delta_F1": {
    "bootstrap_probability_median_ge_practical_threshold": 0.0359,
    "ci95_median": [
      -0.01355942376950775,
      0.022313315806466474
    ],
    "observed_median": 0.0
  }
}
```
