# Micro-CASQ-v0 Mapping

## Expected Raw Files

- A small manually selected set of short dashcam clips under `datasets/casq_external/micro_casq_v0/raw/`.
- Source videos should be documented with provenance and license notes before annotation.

## Expected Annotation Files

- `datasets/casq_external/micro_casq_v0/micro_casq_events_template.csv`
- Future filled file: `datasets/casq_external/micro_casq_v0/micro_casq_events.csv`

## Event Boundaries

The template requires annotators to provide `event_start` and `event_end`. No boundary should be inferred from pseudo-events, VLM labels, or clip names.

## Label Mapping

- `object_enters_ego_path`
- `near_collision`
- `collision_or_near_collision_precursor`
- `background_hard_negative`

Annotators should use `positive_reason` and `negative_near_miss_reason` to document why the event does or does not satisfy the CASQ query.

## Negative / Background Blocks

Negatives should include normal driving and hard negatives such as nearby traffic, dense traffic, parked vehicles, and far-away crossing events that do not enter the ego path or create a potential conflict.

## Known Limitations

- Manual annotation is slow and may not scale to 200 / 500 events without substantial effort.
- Human adjudication policy and inter-annotator checks are not implemented in this Phase 1 scaffold.
- Existing pseudo-events may be used only for debugging ingestion, not as human truth.

## Manual Adjudication Needed

Yes. Micro-CASQ-v0 is useful as a tiny clean boundary sanity set or fallback, not as the primary route to 500 events.

