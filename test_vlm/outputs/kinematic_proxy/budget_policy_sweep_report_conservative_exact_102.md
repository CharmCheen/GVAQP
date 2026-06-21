# Budget Policy Sweep Report

This sweep reports every available VLM pseudo-label variant in the sweep CSV.

## Best Policies At Key Budgets

| label variant | budget ratio | best clip recall policy | clip recall | best event recall policy | event recall |
|---|---:|---|---:|---|---:|
| conservative | 0.10 | proxy_then_expansion_count (r=1, a=0.25) | 0.409 | temporal_nms_count (gap=6.0) | 0.857 |
| conservative | 0.20 | temporal_nms_count (gap=8.0) | 0.545 | temporal_nms_count (gap=8.0) | 0.857 |
| conservative | 0.30 | proxy_then_expansion_ensemble (r=3, a=0.25) | 0.727 | temporal_nms_ensemble (gap=2.0) | 1.000 |
| old_strict | 0.10 | proxy_then_expansion_count (r=1, a=0.25) | 0.162 | temporal_nms_naive (gap=8.0) | 1.000 |
| old_strict | 0.20 | proxy_then_expansion_count (r=1, a=0.25) | 0.309 | temporal_nms_count (gap=6.0) | 1.000 |
| old_strict | 0.30 | proxy_then_expansion_count (r=1, a=0.25) | 0.456 | temporal_nms_count (gap=6.0) | 1.000 |

## Conservative Predicate Sweep Answers

- old_strict: low-budget best clip policy `proxy_then_expansion_count` (0.189); best event policy `temporal_nms_naive` (0.743); temporal-NMS mean event recall=0.669; proxy expansion mean event recall=0.319 vs uniform expansion=0.143.
- conservative: low-budget best clip policy `proxy_then_expansion_count` (0.385); best event policy `temporal_nms_ensemble` (0.729); temporal-NMS mean event recall=0.676; proxy expansion mean event recall=0.331 vs uniform expansion=0.143.
- Interpretation: conservative pseudo-GT is the preferred predicate for the next budget-allocation analysis if its positive rate and examples remain acceptable.

## Parameter Diagnostics

### Expansion Radius

| radius | mean clip recall | mean event recall |
|---:|---:|---:|
| 1.0 | 0.375 | 0.382 |
| 2.0 | 0.371 | 0.356 |
| 3.0 | 0.361 | 0.340 |

- Best average event recall radius: 1.0. Larger radius is useful only if this increases monotonically.

### Anchor Fraction

| anchor_fraction | mean clip recall | mean event recall |
|---:|---:|---:|
| 0.25 | 0.365 | 0.364 |
| 0.5 | 0.371 | 0.357 |
| 0.75 | 0.371 | 0.357 |

### Temporal NMS Gap

| gap_sec | mean clip recall | mean event recall |
|---:|---:|---:|
| 0.0 | 0.369 | 0.456 |
| 2.0 | 0.290 | 0.782 |
| 4.0 | 0.305 | 0.798 |
| 6.0 | 0.325 | 0.825 |
| 8.0 | 0.340 | 0.837 |
- Larger temporal_nms_gap_sec hurts clip recall, consistent with suppressing adjacent positive windows.

### Proxy Anchors Vs Uniform Anchors

- uniform expansion mean event recall: 0.202
- proxy expansion mean event recall: 0.412
- Proxy anchors outperform uniform anchors on average.
