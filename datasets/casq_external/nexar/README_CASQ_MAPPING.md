# Nexar Collision Prediction CASQ Mapping

## Expected Raw Files

- Dashcam videos under `datasets/casq_external/nexar/raw/` or a Hugging Face/Kaggle-compatible local dataset layout.
- Optional public/private test files should not be used for final certification unless labels are available and licensing permits.

## Expected Annotation Files

- `datasets/casq_external/nexar/metadata/train_metadata.csv`
- or `datasets/casq_external/nexar/metadata/train_metadata.json`
- or `datasets/casq_external/nexar/metadata/metadata.csv`
- or `datasets/casq_external/nexar/metadata/metadata.jsonl`

Expected positive-case fields from the public dataset documentation are `time_of_event` and `time_of_alert`, with labels for collision/near-collision versus normal driving.

## Event Boundaries

Nexar provides a precise event moment and alert time for positive collision or near-collision cases. For CASQ, the converter maps `time_of_alert` to `event_start` and `time_of_event` to `event_end` only for the query `collision_or_near_collision_precursor`. It does not fabricate an accident duration interval around the collision moment.

## Label Mapping

- Positive collision/near-collision -> `collision_or_near_collision_precursor`
- Normal driving -> negative/background source
- Scene/weather/light metadata are covariates, not event types

## Negative / Background Blocks

Normal-driving videos are natural negative videos. Within positive videos, background blocks can be sampled before `time_of_alert` and after `time_of_event` with padding; blocks near either boundary should be marked ambiguous unless manually adjudicated.

## Known Limitations

- The public training set is about 1,500 videos and roughly 31 GB on Hugging Face, so no large download should happen without explicit approval.
- `time_of_event` is an instant, not an interval end for every possible CASQ semantic query.
- The `time_of_alert` to `time_of_event` interval is suitable for accident-precursor evaluation, not necessarily object-enters-ego-path without extra adjudication.

## Manual Adjudication Needed

Limited adjudication is needed for the first accident-precursor query. More adjudication is needed if the target query is specifically `object_enters_ego_path`.

