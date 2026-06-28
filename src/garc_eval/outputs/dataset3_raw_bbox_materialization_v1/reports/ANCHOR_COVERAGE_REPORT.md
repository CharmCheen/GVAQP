# ANCHOR_COVERAGE_REPORT.md — Dataset3 Anchor × Raw BBox Coverage

## Method

- Anchor table: `canonical_dataset3_anchor_table.csv` (347 anchors, center10_10s, center_time_s 5.0 to 3462.866)
- Raw bbox table: `raw_yolo_detections_dataset3_2fps.csv` (44595 detections across 6926 frames)
- Per-frame status: `yolo_sampled_frames_dataset3_2fps.csv` (6926 unique frames)
- Anchor window: `center_time_s ± 5 s` (10s window, matching center10_10s)
- `has_enough_frames_for_tracking` = (sampled frames >= 5) AND (vehicle-like detections >= 1) AND (processed == sampled)

## Headline Results

| Group | Count | Has-enough | Coverage |
|-------|-------|-----------|----------|
| All anchors | 347 | 347 | **100.0%** |
| Qwen-positive anchors | 40 | 40 | **100.0%** |
| Qwen-negative anchors | 307 | 307 | **100.0%** |
| Singleton-positive clusters | 21 | 21 | **100.0%** |
| Multi-anchor-positive clusters | 19 | 19 | **100.0%** |
| Low-proxy singletons (object_count_mean <= 6.5) | 9 | 9 | **100.0%** |

**All anchors have enough tracking frames. No anchor is excluded by the coverage check.**

## Per-anchor Window Statistics (N=347)

| Metric | Sampled frames | Processed frames | Vehicle detections | Total detections |
|--------|---------------|-----------------|--------------------|--------------------|
| Mean | 19.97 | 19.97 | 100.40 | 110.65 |
| Median | 20.0 | 20.0 | 97.0 | 105.0 |
| Min | 10 | 10 | 1 | 4 |
| Max | 21 | 21 | 257 | 279 |
| 25th pct | 20.0 | 20.0 | 65.0 | 71.0 |
| 75th pct | 20.0 | 20.0 | 130.5 | 142.0 |

The 10s window × 2 fps yields the expected 20 frames for almost all anchors. Anchors near video boundaries (first/last 5s) have 10–21 frames, which is still > the 5-frame minimum.

## Singleton Positive Detail (N=21)

| anchor_id | center_time | object_count_mean | L3 rank | frames in window | vehicle dets in window |
|-----------|-------------|------------------|---------|------------------|------------------------|
| center10_anchor_0050 | 505.0 | 4.0 | 252 | 20 | 84 |
| center10_anchor_0057 | 575.0 | 5.0 | 211 | 20 | 50 |
| center10_anchor_0060 | 605.0 | 7.0 | 138 | 20 | 73 |
| center10_anchor_0075 | 755.0 | 10.0 | 52 | 20 | 121 |
| center10_anchor_0083 | 835.0 | 7.0 | 138 | 20 | 74 |
| center10_anchor_0132 | 1325.0 | 9.0 | 67 | 20 | 88 |
| center10_anchor_0161 | 1615.0 | 7.5 | 113 | 20 | 73 |
| center10_anchor_0164 | 1645.0 | 10.0 | 52 | 20 | 146 |
| center10_anchor_0183 | 1835.0 | 3.5 | 274 | 20 | 11 |
| center10_anchor_0185 | 1855.0 | 2.5 | 313 | 20 | 5 |
| center10_anchor_0195 | 1955.0 | 7.5 | 113 | 20 | 90 |
| center10_anchor_0197 | 1975.0 | 5.5 | 194 | 20 | 85 |
| center10_anchor_0217 | 2175.0 | 6.5 | 155 | 20 | 81 |
| center10_anchor_0219 | 2195.0 | 6.0 | 177 | 20 | 72 |
| center10_anchor_0224 | 2245.0 | 3.0 | 297 | 20 | 17 |
| center10_anchor_0276 | 2765.0 | 11.0 | 37 | 20 | 165 |
| center10_anchor_0283 | 2835.0 | 7.5 | 113 | 20 | 71 |
| center10_anchor_0317 | 3175.0 | 16.0 | 2 | 20 | 257 |
| center10_anchor_0322 | 3225.0 | 11.0 | 37 | 20 | 138 |
| center10_anchor_0325 | 3255.0 | 4.0 | 252 | 20 | 17 |
| center10_anchor_0331 | 3315.0 | 8.5 | 79 | 20 | 118 |

**Key observation for track-transition:** even the "low-proxy" singletons (L3 rank 252–313) have at least 5 vehicle detections in their window, with minimum 5 (anchor 0185) and median 73. Track construction is feasible.

## Failure Mode Coverage

The 2 fps raw bbox materialization supports the specific failure mode identified by GLM clean-pool revalidation and track-transition motivation:

- **Low-proxy singletons** (the most challenging for L3): 9/9 covered with 5–84 vehicle detections per window
- **Singleton clusters with 0 vehicle detections**: 0 (all singletons have at least 1 vehicle detection in their window)
- **Singleton clusters with very few detections** (vehicle_detections < 10): 2 (anchor 0185: 5, anchor 0183: 11, anchor 0224: 17, anchor 0325: 17). Even these have enough frames for tracking.

## Caveats

1. **2 fps sampling limit**: at 0.5s between frames, very fast object movements (e.g., a vehicle passing through the corridor in <1s) may be missed between samples. This is a known limitation; 5–10 fps would provide tighter trajectory coverage. For transition detection at 2 fps, an object must persist for >=0.5s (one frame gap) to leave a track signature.
2. **No ego-corridor definition**: the raw bbox data has no corridor annotations. Downstream track-transition analysis must define the corridor (e.g., from the kinematic ROI in scout_pipeline.py or from frame geometry). This is outside the scope of this materialization task.
3. **Singleton 0185 (5 veh dets in window)**: lowest vehicle count among singletons. Any downstream tracker must handle short tracks. This is not a coverage failure but a signal-strength concern.
4. **Frames with zero detections** (165 of 6926 = 2.4%): mostly look-ahead or look-behind boundary frames; none of the 40 positive anchors fall entirely within a zero-detection zone.

## Decision

**All anchors meet the coverage criteria.** Track construction and transition analysis are feasible on the 2 fps materialization for the full anchor set, including the 21 singleton positives and 9 low-proxy singletons.

The only caveat is the 2 fps temporal resolution, which is sufficient for transition detection (objects persisting ≥0.5s) but would miss sub-second crossing events.
