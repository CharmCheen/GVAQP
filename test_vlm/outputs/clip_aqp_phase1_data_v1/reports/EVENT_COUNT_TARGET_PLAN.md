# CASQ Event Count Target Plan

## Targets

- Minimum target: 200 clean events
- Ideal target: 500 clean events
- Current reusable clean-event count: 0
- Existing pseudo-event count from Phase 0: 29, debugging only

## Recommended First Query

`collision_or_near_collision_precursor`

This is the most practical first CASQ query because Nexar provides documented `time_of_alert` and `time_of_event` fields for positive cases. The interval `[time_of_alert, time_of_event]` can be treated as the precursor event interval without inventing a collision duration.

## Recommended First Dataset

Nexar Collision Prediction is the recommended first dataset for controlled subset ingestion.

Rationale:

- It is directly aligned with collision / near-collision prediction.
- It has documented positive temporal labels and normal-driving negatives.
- It can plausibly reach 200 and 500 positive events if access and licensing are approved.
- It is smaller than DoTA and DADA-2000 full releases.

## Manual Adjudication Estimate

| stage | positive events | negative videos/blocks | expected adjudication |
| --- | --- | --- | --- |
| smoke | 25 | 25 videos | light review of metadata fields and boundary sanity |
| minimum benchmark | 200 | matched normal/background blocks | moderate review of query mapping and ambiguous cases |
| ideal benchmark | 500 | matched normal/background blocks | substantial review, preferably with an adjudication protocol |

For `object_enters_ego_path`, manual adjudication is higher because collision/near-collision labels do not necessarily specify ego-path entry.

## Reuse Of Existing Data

Existing Phase 0 data and VLM-defined pseudo-events may be reused for:

- script smoke testing;
- schema validation;
- unit/block generation debugging;
- report formatting checks.

They must not be used as human-truth event boundaries, final CASQ clean events, ranking labels, or certification labels.

## First Approved Download Request

When the user authorizes download/access, request only:

- Nexar metadata;
- 25 positive videos with non-null `time_of_alert` and `time_of_event`;
- 25 normal-driving videos;
- any license/terms text required to document use.

Do not download the full dataset unless the small subset validates cleanly and the user explicitly authorizes scale-up.

