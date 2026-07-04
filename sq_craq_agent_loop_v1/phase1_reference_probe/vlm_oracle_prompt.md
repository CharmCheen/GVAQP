# probe_set_v1 VLM Oracle Prompt

Status: used for the 2026-07-03 local Qwen3-VL-32B probe_set_v1 oracle run. The executable implementation is `scripts/vlm/run_probe_vlm_oracle_qwen3vl.py`.

## Inputs Per Probe

- `probe_id`
- `center_frame_path`
- `sheet_path`
- `local_t_start`
- `local_t_end`

The VLM should receive both the center frame and the contact sheet. The contact sheet is the primary temporal context; the center frame is supporting evidence.

## System Instruction

You are a visual event reviewer for a driving-video probe set. Your task is to judge whether a short time window contains the target event type using visible semantic evidence from the provided images. Do not try to reproduce object tracking, distance, speed, TTC, or geometric calculations. Use holistic visual judgment from the center frame and contact sheet.

Target event type: a traffic participant or object enters, crosses, approaches, or creates a near-interaction with the ego vehicle path during the provided local time window. Include clear point-anchor cases where the event is visible but the exact interval boundary is not recoverable from the images. Mark negative when there is no visible target event. Mark uncertain when the images are too ambiguous or insufficient.

## User Prompt Template

Review probe `{probe_id}`.

Local time window: `{local_t_start}` to `{local_t_end}` seconds.

Images:

1. Center frame for the probe.
2. Contact sheet showing multiple frames from the probe window.

Question: In this time window, does the visual evidence show the target event type?

Do not base your answer on inferred detector scores, tracking distances, speeds, TTC, or other cheap-signal computations. Use semantic visual evidence only.

Return exactly one JSON object with these fields:

```json
{
  "label": "true_interval | point_anchor | negative | uncertain",
  "event_t_start_local": "number or null",
  "event_t_end_local": "number or null",
  "confidence": "low | medium | high",
  "rationale": "short visible-evidence explanation"
}
```

Field rules:

- Use `true_interval` when the target event is visible and the contact sheet supports an approximate start and end inside the local window.
- Use `point_anchor` when the target event is visible but only a point-like moment or rough anchor can be inferred.
- Use `negative` when no target event is visible in the provided window.
- Use `uncertain` when image quality, occlusion, contact-sheet ambiguity, or missing temporal context prevents a reliable judgment.
- `event_t_start_local` and `event_t_end_local` must be local seconds. If the label is `negative` or `uncertain`, use `null` unless a visible but ambiguous time anchor is defensible.
- `rationale` must describe visible evidence, for example object type, image location, motion/change across the sheet, and why it does or does not meet the target event type.

## Required Output Provenance

Any CSV produced from this prompt must identify the reference source as `probe_set_v1_vlm_oracle_reference`. It must not call these labels human ground truth. Downstream reports must use wording such as "relative to VLM oracle judgment" and must not use "true recall" or "ground truth recall" for these labels.
