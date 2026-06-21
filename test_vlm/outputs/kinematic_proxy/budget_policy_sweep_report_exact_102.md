# Budget Policy Sweep Report

This sweep reports every available VLM pseudo-label variant in the sweep CSV.

## Best Policies At Key Budgets

| label variant | budget ratio | best clip recall policy | clip recall | best event recall policy | event recall |
|---|---:|---|---:|---|---:|
| broad | 0.10 | proxy_then_expansion_count (r=1, a=0.25) | 0.115 | proxy_then_expansion_naive (r=1, a=0.25) | 1.000 |
| broad | 0.20 | proxy_then_expansion_count (r=1, a=0.25) | 0.219 | proxy_then_expansion_naive (r=1, a=0.25) | 1.000 |
| broad | 0.30 | proxy_then_expansion_count (r=1, a=0.25) | 0.323 | proxy_then_expansion_naive (r=1, a=0.25) | 1.000 |
| ego_relevant | 0.10 | proxy_then_expansion_count (r=1, a=0.25) | 0.134 | temporal_nms_count (gap=6.0) | 1.000 |
| ego_relevant | 0.20 | proxy_then_expansion_count (r=1, a=0.25) | 0.256 | temporal_nms_count (gap=6.0) | 1.000 |
| ego_relevant | 0.30 | proxy_then_expansion_count (r=1, a=0.25) | 0.378 | temporal_nms_count (gap=6.0) | 1.000 |
| strict | 0.10 | proxy_then_expansion_count (r=1, a=0.25) | 0.162 | temporal_nms_naive (gap=8.0) | 1.000 |
| strict | 0.20 | proxy_then_expansion_count (r=1, a=0.25) | 0.309 | temporal_nms_count (gap=6.0) | 1.000 |
| strict | 0.30 | proxy_then_expansion_count (r=1, a=0.25) | 0.456 | temporal_nms_count (gap=6.0) | 1.000 |

## Parameter Diagnostics

### Expansion Radius

| radius | mean clip recall | mean event recall |
|---:|---:|---:|
| 1.0 | 0.268 | 0.523 |
| 2.0 | 0.268 | 0.515 |
| 3.0 | 0.264 | 0.489 |

- Best average event recall radius: 1.0. Larger radius is useful only if this increases monotonically.

### Anchor Fraction

| anchor_fraction | mean clip recall | mean event recall |
|---:|---:|---:|
| 0.25 | 0.266 | 0.510 |
| 0.5 | 0.266 | 0.509 |
| 0.75 | 0.266 | 0.509 |

### Temporal NMS Gap

| gap_sec | mean clip recall | mean event recall |
|---:|---:|---:|
| 0.0 | 0.268 | 0.603 |
| 2.0 | 0.242 | 0.863 |
| 4.0 | 0.250 | 0.888 |
| 6.0 | 0.254 | 0.913 |
| 8.0 | 0.258 | 0.926 |
- Larger temporal_nms_gap_sec hurts clip recall, consistent with suppressing adjacent positive windows.

### Proxy Anchors Vs Uniform Anchors

- uniform expansion mean event recall: 0.313
- proxy expansion mean event recall: 0.574
- Proxy anchors outperform uniform anchors on average.
