# INPUT_INVENTORY.md — Track-Transition Input Audit

## Questions

### Q1: 是否存在已有 bbox detections？

**For dataset3: NO.**

The scout pipeline (`scout_pipeline.py:104-205`) runs YOLOv8n on **1 midpoint frame per 5s window** only. For each such frame, per-instance bbox data (xyxy, class, confidence, track_id) is computed in-memory at `yolo_features_for_batch()` (`scout_pipeline.py:208-254`), immediately summarized into window-level scalar aggregates (vehicle_count, object_count, bbox_area_sum, bbox_cx_std, lateral_presence_count, etc.), and **discarded**. Only the aggregates are saved to `window_features_dataset3.csv`.

No raw per-frame detection CSV/parquet exists for dataset3 anywhere in the repo.

**For realcartest: YES.**
- `experiments/kinematic_proxy/kinematic_proxy/tracks.csv` (74,784 rows): per-frame YOLO detections with track_id, class, bbox (x1/y1/x2/y2/cx/cy/area), conf, timestamp
- `experiments/roadclip_budget_v2/roadclip_budget_v2/tracks.csv` (329,271 rows): per-frame detections on the same video (different pipeline)

But realcartest and dataset3 are different videos (different scenes, different durations, different capture conditions).

### Q2: 是否能从 bbox detections 映射到 anchor？

**For dataset3: N/A — no bbox detections exist to map.**

**For realcartest: Would need per-anchor time windows.** The V13 anchors are also center_10s with the same schema. A mapping script could assign each detection to its enclosing anchor by `time_sec ∈ [anchor.start_time, anchor.end_time]`. This is technically feasible but requires a temporal join — no such mapping file currently exists.

### Q3: 是否存在 corridor / lateral region 定义？

**PARTIAL — ROI definitions exist in code but are crude image-thirds, not an ego-centric corridor.**

The scout pipeline (`scout_pipeline.py:239-251`) defines three spatial ROIs relative to image dimensions:

| ROI | Definition | Purpose |
|-----|-----------|---------|
| `center_mask` | `cx ∈ (w/3, 2w/3) & cy ∈ (h/3, 2h/3)` | V13.5 center third (generic) |
| `ego_mask` | `cx ∈ (0.35w, 0.65w) & cy > 0.45h` | Near-ego lower-center band |
| `lateral` | `cx < w/3 \| cx > 2w/3` | Left/right image thirds |

Limitations:
- These are **image-frame-relative** thirds, not a geometrically computed ego future-path corridor
- No per-frame lane/path estimation exists for dataset3
- "Outside" vs "inside" the ego path cannot be determined from these ROIs — a vehicle in `center_mask` may be in the ego lane or an adjacent lane
- The kinematic proxy (`experiments/kinematic_proxy/`) computes ego-path features (`max_ego_path_overlap`, `max_predicted_entry`, `max_lateral_toward_ego_path`) but only for realcartest, not dataset3

### Q4: 是否有 event_cluster_id / singleton flag？

**YES — for dataset3.**

- `event_cluster_id`: in `canonical_dataset3_anchor_table.csv` (column `event_cluster_id`, integer, -1 for non-positive anchors)
- `is_singleton_cluster`: in same file (bool, True for single-anchor positive clusters)
- `is_multi_anchor_cluster`: in same file (bool, True for ≥2-anchor positive clusters)
- Cluster counts: 21 singleton clusters + 6 multi-anchor clusters = 27 total positive clusters (from `canonical_table_summary.json`)

### Q5: 是否能在 no-new-model 条件下验证 transition idea？

**For dataset3: NO.**

The transition hypothesis requires:
1. Per-frame bbox data at ≤1s resolution → **not available** for dataset3 (only 1 frame per 5s)
2. Object-level tracking across time → impossible without per-frame data
3. Corridor membership classification per detection → no ego-centric corridor definition exists for dataset3 (only crude image-thirds ROIs)

## Decision

The 1-frame-per-5s-window resolution from the scout pipeline is fundamentally insufficient for track construction. Even if raw bbox data were saved, 5-second gaps between observations mean objects can appear, move, and disappear between samples. The ego-corridor definition is also missing (only crude image-thirds ROIs are available).

Without per-frame bbox data at ≤1fps sampling and an ego-corridor definition, the track-level outside→inside transition hypothesis cannot be tested under the no-new-model constraint.

**Decision: `TRACK_TRANSITION_INPUT_MISSING`**
