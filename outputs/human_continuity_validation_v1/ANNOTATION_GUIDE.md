# Annotation Guide: Human Event Continuity

You will see a driving-video context with two neutral temporal markers, **A** and **B**, and the frozen query below. You will not see any model result or method output.

## Frozen query

Inspect this 10-second ego-driving unit and decide whether an attentive ego driver needs a noticeable slowdown, braking action, or avoidance maneuver because of visible conditions within this unit.

Relevant causes may include a road user entering or threatening the ego path, a suddenly slowing or stopped lead vehicle, a traffic control that visibly requires a marked response within this unit, or a visible obstacle or road condition requiring a marked speed or path change. Normal steady driving, ordinary following with no marked response, distant hazards, merely seeing pedestrians or vehicles, and a response completed before the unit are not relevant. Do not infer hidden motion or a future event outside the supplied frames.

## Choose exactly one answer

- **SAME_EVENT** — both marked moments satisfy the query and are part of one continuing semantic episode. A short occlusion, observation gap, or change in intensity can still be one event.
- **DIFFERENT_EVENTS** — both marked moments satisfy the query, but the first episode has clearly ended and B belongs to a new independent episode.
- **ANCHOR_INVALID** — at least one marked anchor does not itself satisfy the query.
- **UNCERTAIN** — the video/context is insufficient for a reliable continuity judgment.

Temporal closeness does not automatically mean SAME_EVENT, and temporal separation does not automatically mean DIFFERENT_EVENTS. Use the visible driving semantics, including the intervening interval. Do not infer hidden motion or events outside the shown video.

An optional comment is available but not required. Your answers are saved immediately. You may go back and revise prior answers until all 40 cases are complete; after the primary set is frozen, corrections require a separately documented revision.
