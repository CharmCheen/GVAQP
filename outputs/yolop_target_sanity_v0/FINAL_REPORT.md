# YOLOP Target-Domain Sanity Audit — Final Report

## Decision: PASS_AUTOMATED__VISUAL_REVIEW_REQUIRED

### Component Results

| Component | Result |
|-----------|--------|
| RUNTIME_COMPATIBILITY | PASS |
| DETECTION_AUTOMATED_SANITY | PASS |
| LANE_AUTOMATED_SANITY | PASS |
| DRIVABLE_AUTOMATED_SANITY | PASS |
| COST_GATE | PASS |
| VISUAL_VALIDATION | REQUIRED |

### Selected Extractor Config

**`ONNX_320`**

### Evidence Summary

- Zero-detection frame fraction: 0.000
- Lane degenerate mask rate: 0.000
- Drivable degenerate mask rate: 0.006
- ONNX 640 end-to-end FPS: 21.8

### Next Highest-Value Work

A. YOLOP frozen + ByteTrack + road-relative features
