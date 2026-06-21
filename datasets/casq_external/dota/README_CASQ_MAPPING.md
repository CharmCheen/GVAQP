# DoTA CASQ Mapping

## Expected Raw Files

- Extracted video clips or frame directories from the DoTA release under `datasets/casq_external/dota/raw/` or `datasets/casq_external/dota/frames/`.
- Optional original videos if using the upstream download workflow.

## Expected Annotation Files

- `datasets/casq_external/dota/annotations/metadata_train.json`
- `datasets/casq_external/dota/annotations/metadata_val.json`
- Optional per-video JSON annotation files under `datasets/casq_external/dota/annotations/`

The upstream DoTA documentation describes `metadata_train.json` and `metadata_val.json` entries with `video_start`, `video_end`, `anomaly_start`, `anomaly_end`, `anomaly_class`, `num_frames`, and `subset`.

## Event Boundaries

DoTA provides equivalent temporal anomaly boundaries as `anomaly_start` and `anomaly_end` in the documented metadata. The local converter does not map these to CASQ second-based `event_start` / `event_end` unless an explicit verified frame rate is provided.

## Label Mapping

- `anomaly_class` -> initial CASQ `event_type`
- Vehicle-, pedestrian-, cyclist-, and obstacle-related anomaly classes may map to `near_collision`, `collision`, `object_enters_ego_path`, or `traffic_anomaly` after inspection.
- Ego relevance is not assumed from the class name alone; set `ego_relevant=unknown` until validated.

## Negative / Background Blocks

Background units can be built from intervals outside `[anomaly_start, anomaly_end]` within the same video. Blocks overlapping uncertain or padded event boundaries should be excluded or marked ambiguous until adjudicated.

## Known Limitations

- Boundary units appear to be frame indices in the public metadata description, not guaranteed seconds.
- Class labels are anomaly categories, not direct CASQ query labels.
- A class-level mapping is not enough to prove object-enters-ego-path semantics.
- The full data is large; only a controlled subset should be downloaded first.

## Manual Adjudication Needed

Yes. DoTA is the best current candidate for clean temporal-boundary ingestion, but CASQ query labels such as `object_enters_ego_path` require manual mapping/adjudication on a subset before using it as clean event-boundary evaluation data.

