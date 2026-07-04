# probe_set_v1 Annotation Guide

Use this guide with:

`/qiuyeqing/llama_prl/G-ARC/outputs/probe_set_v1/probe_set_human_labels_template.csv`

All 25 probes must be reviewed. Do not skip rows because a probe looks easy, hard, low-signal, high-signal, or outside current feature coverage.

## Fields To Fill

- `label`: use `1` for a true target interval, `0` for not a target interval, and `exclude` only when the media is unreadable or the row cannot be judged.
- `event_t_start_local`: local start time of the visible target event, if present.
- `event_t_end_local`: local end time of the visible target event, if present.
- `visible_evidence`: short concrete evidence visible in the clip/contact sheet. Record what changed, where it happened, and why it supports the label.
- `main_objects`: main object types involved, such as vehicle, pedestrian, cyclist, ego vehicle, lane object, or unclear.
- `difficulty`: use `easy`, `medium`, or `hard`.
- `notes`: optional extra context, uncertainty, or reason for `exclude`.
- `reviewer`: reviewer identifier.

## Evidence Notes

Please record `visible_evidence` whenever possible, including for negative and hard cases. These notes are needed for later case-level comparison against `6_event_reference`, especially to distinguish failure or success modes such as an object suddenly entering the ego path, a near interaction already present at clip start, weak off-center motion, or no relevant interaction.

## Machine Suggestions

If any form, sheet, or side document includes a machine suggestion, cheap-signal score, or cheap-signal ranking, treat it as reference context only. It must not replace human judgment. The final `label` should be based on visible evidence in the probe media.

## Frozen-Evaluation Boundary

Completed labels are frozen ground truth for evaluation only. They must not be used for tuning, feature selection, threshold selection, selector changes, model training, repair decisions, or candidate generation.
