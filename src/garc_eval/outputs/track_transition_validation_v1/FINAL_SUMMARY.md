# FINAL_SUMMARY.md — Track-Transition Input Audit

## Decision: `TRACK_TRANSITION_INPUT_MISSING`

## Audit Summary

| Input | dataset3 | realcartest (V13) |
|-------|----------|-------------------|
| Per-frame YOLO bbox detections | ❌ Not saved — scout pipeline discards raw bbox after aggregate computation | ✅ `tracks.csv` (74,784 rows) |
| Bbox → anchor mapping | N/A | ❌ Not precomputed, but feasible via temporal join |
| Corridor / lateral ROI | ⚠️ Only crude image-thirds in code, no ego-corridor geometry | ✅ Kinematic proxy features (ego_path_overlap, predicted_entry) |
| event_cluster_id / singleton flag | ✅ In canonical anchor table | ❌ Not in V13 oracle tables |
| No-new-model feasibility | ❌ Per-frame bbox + corridor both missing | ⚠️ Would need to port event_cluster/singleton logic |

## Why Not Even PARTIAL

The 1-frame-per-5s-window resolution (0.2 fps) from the scout pipeline is fundamentally inadequate for track construction. Even if the raw bbox data were saved:
- 5-second gaps between adjacent samples
- Objects can enter and leave the frame entirely between samples
- Cannot establish object identity across gaps >1s without motion model

The transition hypothesis requires detecting when a *specific object* crosses from outside to inside the ego corridor. This requires:
1. Per-frame or high-rate (≥2fps) bbox data
2. Object-level temporal linking (even simple IoU)
3. Ego-corridor spatial definition (not just image-thirds ROIs)

None of these exist for dataset3 under the no-new-model constraint.

## What EXISTS That Could Be Used

If per-frame dataset3 detections were produced in the future:
- ✅ `canonical_dataset3_anchor_table.csv` — anchor_id → event_cluster_id, singleton, proxy scores
- ✅ `dataset3_full_center10_parsed.csv` — oracle labels per anchor
- ✅ `window_features_dataset3.csv` — per-5s-window aggregates (for coarse temporal context)
- ✅ `center10_proxy_features.csv` — per-anchor proxy features
- ⚠️ `scout_pipeline.py:239-251` — ROI definitions in code (image-thirds, need ego-corridor upgrade)
