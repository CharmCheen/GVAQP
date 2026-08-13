# Frozen human-event attribution protocol — P1-B v1.2

## Primary: ANCHOR_ASSIGNED_EVENT

Each verified-positive unit credits at most one adjudicated human event. The anchor is a pre-existing unit anchor when supplied; otherwise it is the frozen interval center `(start+end)/2`. Event containment is half-open. If overlapping events contain the anchor, choose maximum unit/event temporal overlap; an exact tie goes to lexically earliest frozen `event_id`. If no event contains the anchor, give no credit.

Primary endpoints are `distinct_human_events_anchor_assigned`, `human_event_coverage_anchor_assigned`, `events_with_zero_anchor_assigned_evidence`, and `events_with_1plus_anchor_assigned_evidence`.

## Secondary: OVERLAP_ANY_EVENT

Every human event with positive temporal overlap receives credit. This mapping may credit multiple events and is sensitivity-only. Report `distinct_human_events_overlap_any` and `human_event_coverage_overlap_any`; it cannot establish the primary claim. Final reporting must state whether primary and sensitivity directions agree.
