# Quality Control Protocol v1

## Double-Annotation Sampling

- 10% of detection frames (40 frames): independently annotated by a second annotator
- 15% of tracking clips (1 clip, ~100 frames): independently tracked by a second annotator
- 15% of lane frames (15 frames): independently annotated by a second annotator

## Adjudication Triggers

A sample enters adjudication when:

### Detection
- Class disagreement between annotators
- Box IoU < 0.5 for the same target
- Attribute disagreement (interaction_relevant, adjacent_lane, near_ego_path)
- One annotator annotates a target the other missed

### Tracking
- Track ID mismatch: same real vehicle gets different IDs
- Track merge: different real vehicles share an ID
- Missing interval: one annotator has a target during frames where the other does not
- > 2 ID switches within a single clip for the same annotator

### Lane
- Boundary center deviation > 15% of lane width at any y-level
- Different visibility classification
- One annotator's boundary is > 40px from the other's at frame bottom

## Adjudication Procedure

1. Adjudicator sees BOTH original annotations side-by-side on the same frame
2. Adjudicator does NOT see which annotator made which mark
3. Adjudicator produces final ground truth
4. Disagreement rate is recorded per annotator pair

## Metrics Tracked

| Metric | Threshold | Action if Exceeded |
|--------|-----------|-------------------|
| Inter-annotator box IoU (median) | < 0.85 | Review annotation guidelines with annotators |
| Inter-annotator class agreement | < 0.95 | Retrain annotators on class definitions |
| Frame skip rate (unannotated frames) | > 2% | Reject batch |
| Single-annotator completion time > 90s/frame | Any | Flag for complexity review |
| Track ID inconsistency count per clip | > 5 | Full clip re-annotation |
| Lane boundary deviation > 50px | Any | Adjudication |

## Batch Acceptance Criteria

A batch of annotations is accepted when:
1. All mandatory frames are annotated
2. Double-annotated subset disagreement rate < 5%
3. All adjudicated samples have final labels
4. Schema validation passes (JSON schema check)
5. Coordinate range check passes (all boxes within frame bounds)
6. No track ID appears in non-contiguous frame ranges

## Anonymity

- Annotator IDs are random UUIDs, not names
- Pre-annotated boxes' model sources are stripped
- Adjudicator cannot see annotator identity
- Statistical reports are per-anonymized-ID only

## Versioning

- Annotation batches are versioned: v1.0, v1.1, etc.
- Each version includes a changelog
- Complete version history preserved
- Only the latest version enters evaluation
