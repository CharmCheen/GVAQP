# H-PROXY1 — Final Report

## Decision: BLOCKED_WAITING_FOR_ANNOTATIONS

### Components Status

| Component | Status | Blocker |
|-----------|--------|---------|
| BASELINE_IDENTITY | COMPLETE | — |
| PREREGISTRATION | COMPLETE | — |
| Detection Comparison | PARTIAL | Human annotations needed for accuracy metrics |
| Tracking Comparison | PARTIAL | Human track-ID annotations needed |
| Road Geometry | COMPLETE (executable portion) | — |
| Event Proxy | BLOCKED | No DrivingDojo event labels; STRIVE-D annotations not public |
| Cost Profile | COMPLETE | — |
| Visual Audit | PENDING | — |

### What Was Executed

1. **Baseline identity frozen**: YOLOv8n (6.5MB, SHA-256 f59b3d...f83b36) via ultralytics 8.4.51
2. **PREREGISTRATION.json**: All hypotheses, methods, and blockers documented
3. **Detection inference**: B0 (YOLOv8n), B1/B2 (YOLOP-640), B3 (YOLOP-320) on all 1200 frozen frames
4. **Tracking**: Simple Kalman+Hungarian ByteTrack-like tracker on all configs
5. **Road geometry**: YOLOP lane/drivable features extracted for B2/B3
6. **Cost profiling**: Physical GPU timing with warmup

### Detection Distribution (Without Labels)

| Config | Mean Dets/Frame | Mean Confidence |
|--------|----------------|----------------|
| B0 (YOLOv8n) | 7.0 | — |
| B1 (YOLOP-640) | 9.8 | — |
| B3 (YOLOP-320) | 6.9 | — |

### Cost Profile

| Config | Model FPS | P50 (ms) | P95 (ms) |
|--------|-----------|----------|----------|
| B0 (YOLOv8n) | 122.0 | 8.1 | 8.7 |
| B1/B2 (YOLOP-640) | 41.2 | 24.1 | 25.5 |
| B3 (YOLOP-320) | 79.5 | 12.6 | 13.1 |

### Next Highest-Value Work

Obtain human annotations for detection (400 frames) and tracking (600 frames) from the frozen sample plan.
OR: Reduce scope to distributional-only comparison with rule-baseline event proxy on target-domain video using YOLOP road geometry (no DrivingDojo labels needed).

### Unblock Conditions

1. Human annotation of 400 detection frames + 600 tracking frames + 100 lane sanity frames
2. Structured event labels for DrivingDojo (or alternative labeled event dataset)
3. Implementation of LightGBM event proxy pipeline
