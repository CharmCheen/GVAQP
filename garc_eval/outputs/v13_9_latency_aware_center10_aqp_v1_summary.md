# V13.9 Latency-Aware AQP Simulation — Summary

**Date:** 2026-06-23
**Oracle:** V13.8 full center10 (399 anchors, 51 events)
**Full report:** `test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1/reports/FINAL_REPORT.md`

## Key Results

| B32 | Best Method | Event Recall | Random Mean | Delta |
|---|---|---|---|---|
| 5 | top_yolo_vehicle_max | 0.098 | 0.016 | +0.082 |
| 10 | top_yolo_vehicle_max | 0.098 | 0.027 | +0.071 |
| 20 | uniform_anchor_10s | **0.137** | 0.078 | +0.059 |
| 40 | top_fusion_geometry_motion | 0.216 | 0.165 | +0.051 |
| 80 | hybrid_50_proxy_50_uniform | 0.451 | 0.255 | +0.196 |

## Why This Fails

- At B=20 (primary budget), uniform beats all proxy methods
- Proxy advantage over random at B=20 is only +0.059 (<0.10 threshold)
- Event recovery is dominated by temporal coverage, not proxy quality
- V13.7 labeled-subset results (0.448 at B20) were biased by pilot sampling

## Decision

```
LATENCY_AWARE_AQP_FAIL
```

Current proxy features (YOLO vehicle count, motion energy) provide insufficient signal for budgeted event recovery on the unbiased full oracle.
