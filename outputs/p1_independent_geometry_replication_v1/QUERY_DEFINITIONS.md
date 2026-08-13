# Frozen P1-B query definitions — version 1.1

These definitions are semantic and continuous-time. They never refer to units, fixed gaps, proxy scores, traces, C1/K3, or algorithm output.

## Q_DRIVER_RESPONSE_V1 — Driver response required

**Definition/inclusion.** A maximal continuous episode in which visible conditions require an attentive ego driver to noticeably brake, slow, yield, or change path. Qualifying causes include a road user entering or threatening the ego path, a suddenly slowing/stopped lead vehicle, traffic control requiring a marked response, or a visible obstacle/road condition requiring marked speed/path change.

**Exclusion.** Exclude normal steady driving, ordinary following without marked response, distant/non-actionable hazards, and responses completed before the visible episode.

**Boundaries.** Start at the first visible, actionable onset requiring the response. End when the constraint clears and normal progress can resume. A brief occlusion or momentary easing remains inside one event when the same cause and response obligation persist. Split adjacent occurrences only after the first obligation clearly ends and a new actionable cause/obligation begins. Simultaneous actors/causes form one event when they create one inseparable response episode; overlapping but independently actionable obligations may be separate events and may temporally overlap.

## Q_VULNERABLE_ROAD_USER_CONFLICT_V1 — Vulnerable-road-user conflict

**Definition/inclusion.** A maximal continuous episode in which a pedestrian, cyclist, motorcyclist, or scooter rider enters, crosses, or occupies the ego vehicle's immediate travel path such that the ego driver must yield, brake, slow markedly, or steer to avoid conflict.

**Exclusion.** Exclude road users clearly separated from the ego path, ordinary adjacent traffic, and conflicts completed before the displayed episode.

**Boundaries.** Start when path conflict first becomes visible and actionable. End when the road user clears the immediate path or the ego vehicle safely passes and the conflict no longer constrains motion. A brief occlusion remains inside one event if the same conflict plausibly continues. Split only after one conflict resolves and a new conflict begins. Multiple actors form one event when they jointly create an inseparable conflict episode; independently actionable overlapping conflicts may be separate, overlapping events.

## Rules common to both queries

- **No-event:** submit an explicit empty event list and `event_exists=false`.
- **Boundary ambiguity:** mark `boundary_ambiguous=true` when either best boundary could reasonably shift by more than two seconds; retain the best estimates.
- **Semantic ambiguity:** mark `semantic_ambiguity=true` when whether the occurrence satisfies the query remains genuinely uncertain after full-video review; retain the best decision and explain briefly.
- Uncertainty is recorded, never resolved by consulting algorithmic artifacts or by snapping boundaries to fixed time grids.
