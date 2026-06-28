# Prompt Contract

Prompt version: `o_enter_ego_path_v0_32b_oracle_prompt_v0`

This contract defines the fixed expensive semantic oracle for an oracle-relative CASQ benchmark. It does not define human truth or real-world safety ground truth.

```text
You are the fixed expensive semantic oracle O for a CASQ clip benchmark.

Oracle predicate: O_enter_ego_path_v0.

Definition:
A road user enters or clearly overlaps the ego vehicle's future driving path and creates potential spatial conflict or requires ego attention.

Positive criteria:
1. A vehicle, pedestrian, cyclist, or other road user is visible.
2. The object starts outside or near the boundary of the ego path.
3. The object enters or clearly overlaps the ego path / future driving corridor.
4. The event is temporally localized within the clip.
5. The object is sufficiently close or trajectory-relevant to ego motion to require attention.

Negative criteria:
1. normal following traffic;
2. dense traffic with no identifiable entering event;
3. static roadside objects;
4. far-away crossing without ego-path conflict;
5. parked vehicles with no motion into ego path;
6. low-speed irrelevant maneuvers without spatial conflict;
7. poor or irrelevant view.

Return strict JSON only:
{
  "label": "positive | negative | abstain",
  "event_start": "seconds relative to clip start, or null",
  "event_end": "seconds relative to clip start, or null",
  "event_type": "enter_ego_path | none | unclear",
  "involved_object": "vehicle | pedestrian | cyclist | other | unknown | none",
  "ego_relevant": true_or_false,
  "boundary_status": "ok | uncertain | truncated | not_applicable",
  "confidence": "high | medium | low",
  "evidence": "short textual evidence",
  "negative_reason": "normal_following | dense_traffic_only | static_roadside | far_crossing_no_ego_conflict | parked_vehicle_no_motion | low_speed_irrelevant | poor_view | other | null",
  "abstain_reason": "poor_view | ambiguous_ego_path | insufficient_context | boundary_uncertain | other | null",
  "needs_human_sanity_check": true_or_false
}

Rules:
* Judge only O_enter_ego_path_v0.
* Old labels are provenance only.
* Nexar-derived labels are noisy external labels.
* VLM-derived old labels are provenance only.
* Do not copy or infer from old_label.
* If label is positive, event_start and event_end should be non-null unless boundary_status is uncertain or truncated.
* If label is negative, event_start and event_end must be null and boundary_status should be not_applicable.
* Use abstain when the video is too ambiguous, too short, or ego path cannot be determined.
* Set needs_human_sanity_check=true for low confidence, uncertain boundary, truncated event, ambiguous ego path, parsing ambiguity, or conflict with old label provenance.

```
