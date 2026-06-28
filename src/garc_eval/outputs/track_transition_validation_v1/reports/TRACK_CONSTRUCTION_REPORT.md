# TRACK_CONSTRUCTION_REPORT.md

## Input
- Source: `raw_yolo_detections_dataset3_2fps.parquet` (44595 raw detections)
- Classes used: vehicle-like only (car, bus, truck, motorcycle)
- Image dimensions: 1920x1080
- Sample rate: 2.0 fps (frame gap = 0.5 s)

## Linkage Strategy
- Per-frame matching against previous frame
- Primary: IoU >= 0.05
- Fallback: center distance < 100 pixels (only when IoU is near zero)
- Greedy 1-to-1: each current detection matched to at most one previous track
- New track_id for unmatched current detections
- Active track set is cleaned only every 100 frames (small leak OK at this scale)

## Vehicle-like Class Distribution (N=34814)

| class_name | count |
|-----------|-------|
| car | 31072 |
| bus | 1612 |
| truck | 1465 |
| motorcycle | 665 |

## Track Statistics (N=8787 tracks)

| Metric | Value |
|--------|-------|
| Total vehicle-like detections | 34814 |
| Total tracks | 8787 |
| Mean track length (frames) | 3.96 |
| Median track length (frames) | 1 |
| Max track length (frames) | 310 |
| Track length std | 12.69 |
| Tracks length >= 2 | 3676 (41.8%) |
| Tracks length >= 3 | 2303 (26.2%) |
| Tracks length >= 5 | 1296 (14.7%) |
| Tracks length >= 10 | 616 (7.0%) |
| Total linked detections | 26027 |
| Total new tracks started | 8787 |
| Detections with track_id >= 0 | 34814 (100.0%) |
| Unmatched detections (track_id == -1) | 0 |

## Quality Notes

1. **Track length distribution is heavy-tailed**: median 1 frame (single-frame "tracks"), mean 3.96 frames. This is expected at 2 fps (0.5s between samples) where many objects appear briefly.

2. **Link rate**: 26027/34814 = 74.8% of vehicle-like detections are linked to a previous-frame detection (track continuation). The rest start new tracks.

3. **Long tracks (>=10 frames)**: 616 tracks have >= 5 seconds duration. These are persistent vehicles.

4. **Short tracks (length 1)**: 5111 tracks have only one frame. These represent objects that appear once and are missed on the next sample (e.g., fast-moving objects, occluded objects). For transition analysis, only length >= 2 tracks can produce transitions.

5. **No learning-based tracking used**: pure IoU + center-distance linking. No SORT, DeepSORT, or other learned tracker.

6. **0.5s frame gap is a fundamental limit**: at 2 fps, an object must persist for >=1s to leave a length-2 track. Very fast crossings (sub-second) will only produce length-1 tracks and be missed.

## Decision

`TRACKS_CONSTRUCTED_OK` — proceed to Phase 2 (transition feature extraction).
