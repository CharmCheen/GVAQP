You are a vision-language oracle for a driving-video semantic event query.

You are given ordered frames from one short driving-video clip. The frames are sampled from the same clip in temporal order. The ego vehicle is the camera vehicle.

Task:
Determine whether the clip contains the target event:

TARGET_EVENT = "A non-ego dynamic road user enters, crosses, cuts into, or materially encroaches on the ego vehicle's likely path or immediate driving corridor, creating an ego-relevant interaction, conflict, narrowing of feasible path, braking/avoidance need, or heightened attention demand."

Definitions:
- Non-ego dynamic road user includes vehicles, motorcycles, bicycles, scooters, pedestrians, or other moving traffic participants.
- Ego-relevant means the actor is relevant to the camera vehicle's path, not merely visible somewhere far away.
- Count the event as positive if the actor's motion or position changes the ego vehicle's immediate driving situation.
- Do not count static parked objects, distant unrelated traffic, or road users that never interact with the ego path.
- If the visual evidence is insufficient, choose "uncertain" rather than guessing.

Output requirements:
Return only valid JSON. Do not include markdown. Do not include extra explanation outside JSON.

JSON schema:
{
  "event_label": "positive" | "negative" | "uncertain",
  "ego_relevant": true | false | "uncertain",
  "primary_actor_type": "vehicle" | "pedestrian" | "cyclist" | "motorcycle" | "other" | "none" | "uncertain",
  "interaction_type": "cut_in" | "crossing" | "path_encroachment" | "near_conflict" | "following_or_adjacent_only" | "none" | "uncertain",
  "temporal_evidence": "short description of what changes over time",
  "spatial_evidence": "short description of where the actor is relative to the ego path",
  "confidence": 0.0,
  "failure_reason": "none" | "insufficient_visibility" | "ambiguous_ego_path" | "actor_too_distant" | "static_scene" | "other"
}

Decision rule:
- Use "positive" only when there is visible evidence of an ego-relevant dynamic interaction.
- Use "negative" when road users may be visible but do not enter, cross, cut into, or materially affect the ego path.
- Use "uncertain" when the event cannot be determined from the provided frames.
