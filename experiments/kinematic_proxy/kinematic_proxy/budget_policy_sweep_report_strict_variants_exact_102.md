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
| strict_v2 | 0.10 | proxy_then_expansion_count (r=1, a=0.25) | 0.162 | temporal_nms_naive (gap=8.0) | 1.000 |
| strict_v2 | 0.20 | proxy_then_expansion_count (r=1, a=0.25) | 0.309 | temporal_nms_count (gap=6.0) | 1.000 |
| strict_v2 | 0.30 | proxy_then_expansion_count (r=1, a=0.25) | 0.456 | temporal_nms_count (gap=6.0) | 1.000 |
| strict_v3 | 0.10 | proxy_then_expansion_count (r=1, a=0.25) | 0.162 | temporal_nms_naive (gap=8.0) | 1.000 |
| strict_v3 | 0.20 | proxy_then_expansion_count (r=1, a=0.25) | 0.309 | temporal_nms_count (gap=6.0) | 1.000 |
| strict_v3 | 0.30 | proxy_then_expansion_count (r=1, a=0.25) | 0.456 | temporal_nms_count (gap=6.0) | 1.000 |

## Strict Variant Sweep Answers

- strict_v2: low-budget best clip policy `proxy_then_expansion_count` (0.189); best event policy `temporal_nms_naive` (0.743); temporal-NMS mean event recall=0.669; proxy expansion mean event recall=0.319 vs uniform expansion=0.143.
- strict_v3: low-budget best clip policy `proxy_then_expansion_count` (0.189); best event policy `temporal_nms_naive` (0.743); temporal-NMS mean event recall=0.669; proxy expansion mean event recall=0.319 vs uniform expansion=0.143.
- Interpretation: temporal NMS/diversity should be read as event-coverage machinery, while expansion primarily spends calls around triggered positives for dense clip recovery.

## Parameter Diagnostics

### Expansion Radius

| radius | mean clip recall | mean event recall |
|---:|---:|---:|
| 1.0 | 0.283 | 0.449 |
| 2.0 | 0.284 | 0.437 |
| 3.0 | 0.278 | 0.422 |

- Best average event recall radius: 1.0. Larger radius is useful only if this increases monotonically.

### Anchor Fraction

| anchor_fraction | mean clip recall | mean event recall |
|---:|---:|---:|
| 0.25 | 0.281 | 0.437 |
| 0.5 | 0.282 | 0.436 |
| 0.75 | 0.282 | 0.436 |

### Temporal NMS Gap

| gap_sec | mean clip recall | mean event recall |
|---:|---:|---:|
| 0.0 | 0.282 | 0.523 |
| 2.0 | 0.248 | 0.826 |
| 4.0 | 0.261 | 0.860 |
| 6.0 | 0.265 | 0.887 |
| 8.0 | 0.269 | 0.911 |
- Larger temporal_nms_gap_sec hurts clip recall, consistent with suppressing adjacent positive windows.

### Proxy Anchors Vs Uniform Anchors

- uniform expansion mean event recall: 0.264
- proxy expansion mean event recall: 0.493
- Proxy anchors outperform uniform anchors on average.
