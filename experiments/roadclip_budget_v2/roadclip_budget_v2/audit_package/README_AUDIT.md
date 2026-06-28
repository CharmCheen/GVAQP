# Roadclip V2 Human Audit Package

- clips in package: 111
- all conservative positives included: 39

Fill these columns in `audit_manifest.csv`:

- `human_label`: 1 = true ego-relevant risk/path conflict, 0 = not ego-relevant risk, -1 = uncertain.
- `human_event_type`: cut_in/crossing/sudden_braking/lane_conflict/normal_following/dense_traffic_only/roadside_static/other.
- `human_reason`: brief reason.
- `human_confidence`: low/medium/high.
- `error_type`: optional, e.g. false_positive, false_negative, ambiguous_prompt, bad_scene.

VLM labels are pseudo-GT and not human ground truth.
