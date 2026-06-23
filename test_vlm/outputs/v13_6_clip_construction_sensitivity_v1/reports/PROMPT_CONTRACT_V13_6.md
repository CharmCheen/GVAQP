# V13.6 Prompt Contract — O_enter_ego_path_v0

**Version:** v13_6
**Model:** Qwen3-VL-32B-Instruct
**Label type:** VLM_ORACLE_RELATIVE

## Positive Definition

A road user:
1. Is visible in the clip
2. Starts outside or near the boundary of the ego vehicle's future driving path
3. Enters or clearly overlaps the ego path, creating potential spatial conflict
4. The event is temporally localized within the audited clip
5. The object is sufficiently close or trajectory-relevant to require ego attention

## Negative Definition

Label negative for:
- Normal following traffic
- Dense traffic with no identifiable entering event
- Static roadside objects
- Far-away crossing without ego-path conflict
- Parked vehicles with no motion into ego path
- Low-speed irrelevant maneuvers without spatial conflict
- Visible object but no ego-path interaction
- **Normal no-event driving must be labeled negative, not abstain**

## Abstain Definition

Abstain only for:
- Poor camera view (glare, darkness, rain, fog)
- Severe occlusion preventing judgment
- Ego path genuinely ambiguous
- Insufficient visual evidence to decide
- Model cannot localize event boundary with confidence

## Output Schema

```json
{
  "label": "positive | negative | abstain",
  "event_start": "seconds relative to input clip start, or null",
  "event_end": "seconds relative to input clip start, or null",
  "event_type": "enter_ego_path | none | unclear",
  "involved_object": "vehicle | pedestrian | cyclist | other | unknown | none",
  "ego_relevant": true,
  "boundary_status": "ok | truncated_start | truncated_end | truncated_both | uncertain | not_applicable",
  "complete_event_visible": true,
  "confidence": "high | medium | low",
  "evidence": "short textual evidence",
  "negative_reason": "normal_following | dense_traffic_only | static_roadside | far_crossing_no_ego_conflict | parked_vehicle_no_motion | low_speed_irrelevant | no_ego_path_interaction | other | null",
  "abstain_reason": "poor_view | ambiguous_ego_path | insufficient_context | boundary_uncertain | occlusion | other | null"
}
```

## Key Change from V13.5

The most important change: **normal no-event driving must be labeled negative, not abstain.** V13.5 had 66% abstain rate driven by labeling normal driving as abstain.

## Construction Policy Notes

Clips may be longer than 5s. The model should:
- Localize events to the clip timeline
- Report boundary_status=truncated_start if the event appears to begin before the clip
- Report boundary_status=truncated_end if the event appears to extend beyond the clip
- Report complete_event_visible=true only when the full event (entry to resolution) is visible within the clip
