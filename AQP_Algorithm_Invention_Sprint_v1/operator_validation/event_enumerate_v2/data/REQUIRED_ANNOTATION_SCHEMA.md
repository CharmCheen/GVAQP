# Required annotation schema

## Video table

Required fields:

| Field | Meaning |
|---|---|
| `population_id` | immutable annotation-population ID |
| `video_id` | stable video ID |
| `video_path` | evaluator-resolvable path; not exposed as a label carrier |
| `video_sha256` | full file hash |
| `source_dataset` | provenance and license family |
| `source_split` | split fixed before this gate |
| `fps` | verified source FPS |
| `total_frames` | verified frame count |
| `duration_seconds` | container duration |
| `used_for_vera_or_operator_development` | must be false |
| `provenance_review_status` | must be `PASS` |

## Event relation

One row per true event:

| Field | Constraint |
|---|---|
| `population_id`, `video_id`, `event_id` | unique composite key |
| `event_start`, `event_end` | finite absolute video seconds, `0 <= start < end <= duration` |
| `event_type` | exactly `enter_ego_path` after any frozen mapping |
| `involved_object` | `vehicle`, `pedestrian`, `cyclist`, `other`, or `unknown` |
| `object_identity` | reviewer-visible distinguishing description |
| `ego_relevant` | true |
| `boundary_confidence` | high/medium/low |
| `predicate_mapping_id` | exact predicate or prereviewed formal mapping |
| `annotator_ids` | at least two independent annotators for accepted events |
| `adjudicator_id` | required for disagreement |
| `reference_frozen_at` | timestamp before operator inference |
| `source_evidence` | frames/timestamps used by reviewers |

## Reviewed coverage intervals

To prove emptiness and exhaustiveness, a separate table must partition every
eligible video into reviewed intervals with fields
`coverage_id, video_id, start, end, review_complete, visibility_status,
annotator_ids, adjudication_status`.  An empty operator interval is valid only
when fully contained in coverage marked complete and containing no reference
event.  Unreviewable time must be excluded, never treated as negative.

## Evaluator-only derived fields

After reference freeze, the evaluator may derive event duration, actor/type,
empty/single/multi count, boundary-straddling status, and proposed sample
strata.  These fields must not be passed to inference.  All derivations and
the final reference hash must be reproducible.
