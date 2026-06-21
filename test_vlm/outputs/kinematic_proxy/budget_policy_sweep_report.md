# Budget Policy Sweep Report

This sweep uses the broad VLM pseudo-label variant only.

## Best Policies At Key Budgets

| budget ratio | best clip recall policy | clip recall | best event recall policy | event recall |
|---:|---|---:|---|---:|
| 0.10 | uniform_expansion (r=1, a=0.25) | 0.161 | temporal_nms_count (gap=6.0) | 0.800 |
| 0.20 | uniform_expansion (r=1, a=0.25) | 0.323 | temporal_nms_naive (gap=2.0) | 1.000 |
| 0.30 | proxy_then_expansion_count (r=1, a=0.25) | 0.468 | temporal_nms_count (gap=2.0) | 1.000 |

## Parameter Diagnostics

### Expansion Radius

| radius | mean clip recall | mean event recall |
|---:|---:|---:|
| 1.0 | 0.321 | 0.478 |
| 2.0 | 0.314 | 0.483 |
| 3.0 | 0.297 | 0.517 |

- Best average event recall radius: 3.0. Larger radius is useful only if this increases monotonically.

### Anchor Fraction

| anchor_fraction | mean clip recall | mean event recall |
|---:|---:|---:|
| 0.25 | 0.311 | 0.494 |
| 0.5 | 0.310 | 0.492 |
| 0.75 | 0.310 | 0.492 |

### Temporal NMS Gap

| gap_sec | mean clip recall | mean event recall |
|---:|---:|---:|
| 0.0 | 0.316 | 0.556 |
| 2.0 | 0.272 | 0.789 |
| 4.0 | 0.274 | 0.744 |
| 6.0 | 0.281 | 0.767 |
| 8.0 | 0.276 | 0.778 |
- Larger temporal_nms_gap_sec hurts clip recall, consistent with suppressing adjacent positive windows.

### Proxy Anchors Vs Uniform Anchors

- uniform expansion mean event recall: 0.267
- proxy expansion mean event recall: 0.568
- Proxy anchors outperform uniform anchors on average.
