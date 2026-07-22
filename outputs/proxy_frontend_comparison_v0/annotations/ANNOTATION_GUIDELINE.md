# Proxy Front-End Annotation Guideline v1

## Objective

Produce an independent ground-truth set for comparing YOLOv8n, YOLOP-640, and YOLOP-320 
detection/tracking quality on the target-domain video `long_video_dataset3.mp4`.

Annotators must NOT know which detection boxes come from which model.

## Task Structure

| Task | Frames | Format | Primary Goal |
|------|--------|--------|-------------|
| Detection | 400 | COCO-style bboxes | Classify + bound-box all traffic targets |
| Tracking | ~600 (6 clips × 100 frames) | MOT-style | Track-ID continuity for key targets |
| Lane/Corridor | 100 | Polyline + visibility | Ego-lane boundaries |

## Detection Annotation Rules

### Classes

| Class ID | Name | Description |
|----------|------|-------------|
| 0 | car | Sedan, SUV, hatchback, wagon, taxi |
| 1 | truck | Box truck, dump truck, semi (exclude pickup) |
| 2 | bus | Transit bus, coach, school bus |
| 3 | motorcycle | Motorcycle, scooter (include rider) |
| 4 | bicycle | Bicycle (include rider) |
| 5 | person | Pedestrian, person on foot |

### Bounding Box Rules

1. **Tight fit**: Box must tightly enclose the visible portion of the object.
2. **Truncated objects**: Objects partially visible at frame edge: annotate if >= 30% visible.
3. **Occluded objects**: Annotate if the object's category is identifiable despite occlusion.
4. **Reflections/glass**: Do NOT annotate reflections of vehicles in windows or puddles.
5. **Far objects**: Annotate the smallest objects that a human can confidently classify from a single frame.

### Attributes (Per Box)

| Attribute | Values | Description |
|-----------|--------|-------------|
| small_or_distant | yes/no | Object occupies < 2% of frame area OR < 32px in either dimension |
| partially_occluded | yes/no | Object is partially hidden by another object or static element |
| adjacent_lane | yes/no | Object is in a lane adjacent to ego vehicle's lane |
| near_ego_path | yes/no | Object is directly in ego vehicle's path or within 1 lane width of ego centerline |
| interaction_relevant | yes/no | Object COULD participate in a traffic interaction (not necessarily cut-in) |

`interaction_relevant` is the loosest criterion. Mark "yes" for any vehicle that the ego vehicle might need to respond to.

## Tracking Annotation Rules

### Pre-annotation

ByteTrack results from all 3 detectors are provided as pre-annotations. Annotators should:

1. **Correct ID switches**: Re-assign track IDs when a single vehicle gets multiple IDs.
2. **Fix trajectory breaks**: Connect segments of the same vehicle that were fragmented.
3. **Remove ghost tracks**: Delete tracks corresponding to false detections (clutter, reflections).
4. **Add missed targets**: Add boxes for vehicles the detectors missed, maintaining track continuity.

### Track States

| State | Code | Description |
|-------|------|-------------|
| Active | active | Object is present and moving within frame |
| Occluded | occluded | Object hidden by another object but trajectory continuous |
| Out of view | out_of_view | Object left the frame |
| Stationary | stationary | Parked vehicle or stopped pedestrian |

### Annotation Priority

Prioritize these targets (others optional):
1. Vehicles in ego lane or directly ahead
2. Vehicles in adjacent lanes, especially those showing lateral motion
3. Pedestrians and cyclists near the roadway
4. Vehicles making lane changes

For each priority target, ensure track continuity across the entire 20-second window.

## Lane/Corridor Annotation Rules

### What to Annotate

For each frame, draw two polylines:

1. **Left ego-lane boundary**: The line marking the left edge of ego's current lane
2. **Right ego-lane boundary**: The line marking the right edge of ego's current lane

If the lane has a physical median or curb, the boundary is the painted lane line nearest to ego, NOT the physical barrier.

### Lane Visibility

| Code | Description |
|------|-------------|
| clear | Both boundaries clearly visible for >= 80% of frame height |
| partial | Boundaries visible for 40-80% of frame height |
| unavailable | Boundaries visible for < 40% or absent entirely |

### Special Cases

- **Intersections**: Annotate the lane boundaries leading INTO the intersection. Mark visibility as "partial" or "unavailable" within the intersection itself.
- **Curves**: Follow the actual curve; do not approximate with straight lines.
- **Multiple lanes**: Pick the lane containing ego vehicle's center at frame bottom.
- **Unmarked roads**: If no painted lines exist, annotate the inferred lane boundary based on road edge, parked cars, or vehicle flow.

### Ego Corridor

The ego corridor is the polygon bounded by:
- Left ego-lane boundary
- Right ego-lane boundary  
- Bottom of frame
- Top of visible drivable area

## Quality Control

1. **Double annotation**: 10-15% of frames randomly selected for independent second annotation.
2. **Adjudication**: All samples where annotators disagree on class, box IoU < 0.5, or attribute conflict go to a third adjudicator.
3. **Blind protocol**: Annotators see pre-annotated boxes but are told they come from "an automated system" — not which model.
4. **Timing**: Track time spent per frame; flag frames taking > 60s for review.

## Output Format

All annotations in COCO JSON format for detection, MOT Challenge format for tracking, and GeoJSON for lane polylines. See `DETECTION_SCHEMA.json`, `TRACKING_SCHEMA.json`, `LANE_SCHEMA.json` for exact schemas.
