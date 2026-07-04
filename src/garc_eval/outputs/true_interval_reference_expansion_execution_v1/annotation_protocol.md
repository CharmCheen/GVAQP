# Annotation Protocol

## Core Labels

### true interval event

A true interval event is a sustained process with a meaningful start and end time. It is suitable for interval IoU evaluation because a reviewer can mark when the event semantics begin and end.

### point-anchor event

A point-anchor event is a local, instantaneous, or single-frame-neighborhood cue. It may be useful context, but it should not enter the main interval IoU evaluation.

### negative

The candidate window does not contain the target event.

### ambiguous

The candidate needs second review, or event boundaries cannot be reliably determined.

## Required Human Fields

- `human_event_type`: one of cut-in, near-conflict, abnormal vehicle interaction, pedestrian crossing, cyclist crossing, blocked, overtaking, being overtaken, other, negative, ambiguous.
- `corrected_start`: event semantic start time in local video seconds.
- `corrected_end`: event semantic end time in local video seconds.
- `boundary_confidence`: high / medium / low.
- `keep_for_interval_eval`: yes / no / review.
- `exclusion_reason`: required when excluding a visible candidate from interval IoU evaluation.

## Atomic Conditions

- cut-in: an object moves into the ego path from an adjacent/outside region.
- near-conflict: spatial interaction requires ego attention or creates potential conflict.
- abnormal vehicle interaction: unusual merge, stop, encroachment, or trajectory conflict.
- pedestrian / cyclist crossing: vulnerable road user enters or crosses the ego path.
- blocked / overtaking / being overtaken: include only when the target event has sustained ego-path interaction semantics.

## Boundary Rules

- `start_time`: earliest time where the event semantics begin.
- `end_time`: time where the event semantics end or the scene stabilizes.
- Do not use a single center anchor as an interval boundary.
- If the event is too short and has no sustained process, mark point-anchor.
- If boundary is uncertain, use `boundary_confidence=low` and `keep_for_interval_eval=review`.

Existing labels are context only. Candidate suggestions are not human labels. Final reviewed labels must come from filled human fields.
