# Annotation Protocol

This protocol is for human or semi-human review only. It does not create labels automatically.

- True interval event: a temporally extended object interaction where an object starts outside the ego future path and enters/overlaps it, creating a meaningful spatial conflict or attention demand.
- Point-anchor event: a timestamp-like or very short event (duration <= 2s) whose boundaries are not meaningful enough for interval IoU main evaluation.
- Start boundary: first frame/time where the object begins the entering or conflict trajectory.
- End boundary: time when the conflict is resolved, leaves the path, or no longer requires ego attention.
- Atomic conditions: cut-in, near-conflict, abnormal interaction, pedestrian/cyclist/vehicle entering ego path.
- Boundary confidence: high if start/end are visually clear, medium if approximate, low if only an anchor is visible.
- Ambiguous cases: keep notes and do not include in interval-IoU main set unless corrected boundaries are credible.
- Multi-event overlap: create separate rows only when two objects/events have separable start/end semantics.
- IoU evaluation applies only to `keep_for_interval_eval=true` true interval events.
