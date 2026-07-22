# Research state

## Established findings

- `test.mov` is byte/content-disjoint from the strict video under the user's provenance premise.
- `realcartest_5k.mp4` is not content-derived from the current `test.mov` artifact despite the supplied statement.
- The recovered exhaustive Qwen3-VL VEPC oracle is for `realcartest`, not `test.mov`.
- `test.mov` has exhaustive YOLO vehicle-count outputs, which do not answer the target event predicate.
- Physical calls in this workflow: zero.

## Active hypothesis

The intended test.mov VLM responses may exist outside the searched workspace or under an unrecorded source identity.

## Rejected hypotheses

- The current `realcartest_5k.mp4` is a temporal slice of the current `test.mov`: rejected by direct frame content.
- YOLO vehicle-count labels can instantiate `enter_ego_path`: rejected by predicate/schema mismatch.

## Unresolved uncertainty and next action

Locate a complete prompt-conditioned VEPC annotation set with frame-level lineage to `test.mov`, or authorize independent oracle generation before any EVENT_ENUMERATE call.
