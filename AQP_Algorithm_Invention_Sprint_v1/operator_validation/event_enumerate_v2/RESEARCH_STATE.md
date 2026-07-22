# Research state

## Current objective

Determine whether a correctly represented Qwen3-VL `EVENT_ENUMERATE` operator
can meet event recall and F1 >=0.80 at lower synchronized GPU cost than matched
dense 10-second execution, without changing VERA.

## Established findings

- The old 60-second physical input was temporally compressed from 121 decoded
  frames to 10 processor-consumed frames because metadata and the no-resample
  kwargs were omitted.
- All 70 old enumeration schedules/responses were reconstructed; 68 are
  nominal 60-second calls and their processor timeline ends at 4.8 displayed
  seconds.
- The single corrected path passes 25 processor tests and
  15 pre-execution audit checks, including exact
  timestamps, the exact old helper/processor signature, and batch equivalence.
- The prompt is byte-identical to v1 and no semantic reference was used to
  choose sampling, metadata, parser, or thresholds.
- Nine local held-out candidate families were audited; zero provide a valid
  disjoint exhaustive event relation.
- Physical calls spent: 0.  Terminal decision: `HELDOUT_DATA_REQUIRED`.

## Active hypotheses

- H-OPERATOR: corrected temporal transport may recover semantic recall/F1
  while retaining a cost advantage.  Still untested.
- H-INTRINSIC: 2-FPS, up-to-60-second enumeration may remain semantically too
  weak even with correct metadata.  Still plausible.
- H-COST: retaining 121 frames rather than 10 may erase the old cost advantage.
  Still untested; the previous ratio is invalid.

## Rejected hypotheses

- H-MESSAGE-FPS-SUFFICIENT: putting `fps` in the chat message correctly informs
  the processor.  Rejected by source tracing and regression.
- H-OLD-COST-REUSABLE: the compressed-input runtime estimates corrected cost.
  Rejected because the corrected tensor has materially different frames/tokens.
- H-LOCAL-DATA-SUFFICIENT: an existing local population already satisfies the
  held-out gate.  Rejected by the candidate audit.

## Important failures and lessons

Frame hashes before the processor do not prove model-visible time.  Future
physical runs must persist metadata, decoded source timestamps, serialized
timestamp tokens, grids, tensor hashes, and absolute mapping for every call.
Dataset disjointness alone is insufficient: an event enumerator needs an
exhaustive relation plus reviewed emptiness and multi-event coverage.

## Unresolved uncertainty

Semantic accuracy, multi-event behavior, boundary localization, corrected GPU
cost, and matched dense cost are all unmeasured.  Processor correctness does
not imply operator quality.  The frozen stride rule can exceed the 121-frame
cap for some non-integer source FPS values, so future held-out media require an
FPS/frame-count compatibility check before label exposure or physical
authorization.

## Next highest-value action

Produce and independently freeze the missing held-out event relation according
to `data/HELDOUT_DATA_REQUIREMENTS.md` and
`data/REQUIRED_ANNOTATION_SCHEMA.md`.  First validate the media-only FPS/frame
metadata against the frozen selection rule; if incompatible, refreeze one
event-independent rule and repeat this processor gate.  Then freeze, but do
not tune, the bounded physical matrix.
