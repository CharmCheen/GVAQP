Analyze these driving video frames. Is there any road user (pedestrian, cyclist, motorcycle, vehicle) that enters, crosses, or encroaches on the ego vehicle's path?

If YES, output: {"event_label": "positive", ...}
If NO, output: {"event_label": "negative", ...}

When in doubt, say positive. Missing a real event is worse than a false alarm.

Output ONLY valid JSON:
{
  "event_label": "positive" | "negative" | "uncertain",
  "ego_relevant": true | false,
  "primary_actor_type": "vehicle" | "pedestrian" | "cyclist" | "motorcycle" | "none",
  "interaction_type": "cut_in" | "crossing" | "path_encroachment" | "near_conflict" | "none",
  "temporal_evidence": "what changes across frames",
  "spatial_evidence": "actor position relative to ego path",
  "confidence": 0.0
}
