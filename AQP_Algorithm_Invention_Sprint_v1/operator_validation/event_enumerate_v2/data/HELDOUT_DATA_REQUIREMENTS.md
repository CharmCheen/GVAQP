# Held-out data requirements

Decision: `HELDOUT_DATA_REQUIRED`.

## Decisive evidence

The local search found thousands of video files but no population satisfying
all gate conditions.  `HELDOUT_CANDIDATE_AUDIT.csv` separates availability
from validity.  The strongest candidate, Nexar, has disjoint positive and
negative clips with collision times, but it does not exhaustively annotate the
frozen `object enters ego path` predicate and cannot establish multi-event
recall.  DrivingDojo has disjoint imagery but no target-event relation.  The
remaining references are absent, pseudo-oracle-derived, development-used, or
derived from the forbidden strict video.

No physical call is permitted or spent under this decision.

## Minimum acceptable population

A future population must provide:

1. one or more videos byte-disjoint from
   `data/realcam/long_video_data/long_video_dataset3.mp4` and from its exported
   clips;
2. provenance showing the videos and reference were not used to select VERA,
   its prompt, sampling rule, parser, or thresholds;
3. an independently frozen, exhaustive event-level reference for the exact
   v1 prompt definition of `enter_ego_path`, or a documented one-to-one
   predicate mapping reviewed before sampling;
4. explicit reviewed negative coverage, not merely absence of a positive
   dataset label;
5. enough continuous duration to form empty, one-event, and multi-event
   operator intervals, plus events crossing proposed ownership boundaries;
6. both short and long events and multiple actor types where the source
   population contains them;
7. source FPS/frame count and a license/provenance record;
8. evaluator-only storage isolated from inference inputs; and
9. a frozen adjudication protocol with at least two independent reviewers for
   positives, hard negatives, and disputed boundaries.

## Reference creation prohibition

VERA outputs, EVENT_ENUMERATE v2 outputs, and prompt-specific Qwen responses
must not create or repair the reference.  Existing VLM pseudo-labels may help
locate candidate media for human annotation only if selection provenance is
recorded and annotators review the full sampled population; they cannot be
accepted as truth.

## Next gate

After a compliant reference is delivered, validate its schema and provenance,
freeze `HELDOUT_SAMPLE.csv`, keep
`HELDOUT_REFERENCE_EVALUATOR_ONLY.csv` inaccessible to inference, then replace
the proposed matrix with a hash-sealed call matrix.  Processor tests must be
rerun against the unchanged frozen source before any GPU call.
