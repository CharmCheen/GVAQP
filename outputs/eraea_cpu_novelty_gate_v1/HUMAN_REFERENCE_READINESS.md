# HUMAN_REFERENCE_READINESS (parallel task: independent human EventRelation reference)

Status: **BLOCKED_HUMAN_REFERENCE** — 0 labels locally (verified:
`outputs/gvaqp_long_horizon_p1_p3_v1/human_reference_package/HUMAN_EVENT_LABELS.jsonl`
is empty, sha256 `e3b0c442…`). This document audits readiness only; it does
not modify the frozen P1 protocol and reads no annotation content.

## Field gap audit: frozen P1 protocol vs ERAEA reference requirements

Required ERAEA fields per event:

```text
event_id, query_id, start_time, end_time, core_start, core_end,
acceptable_boundary_band, confidence, ambiguity, required_evidence,
exclusion_rationale
```

Frozen P1 package (`HUMAN_REFERENCE_PROTOCOL.json`) collects per event:
`event_exists`, `start_time`, `end_time`, `boundary_ambiguous` (per
`required_fields`), plus `annotator_id`/`case_id`/`video_id`/`query_id` at row
level.

| ERAEA field | In frozen P1? | Gap | CPU-actionable fix |
|---|---|---|---|
| event_id | row identity only | derive at freeze time | assign `{query}_{case}_{n}` at adjudication |
| query_id / video_id | YES (row level) | none | — |
| start_time / end_time | YES | none | — |
| core_start / core_end | NO | missing | add to a NEW pilot schema (do not amend frozen P1) |
| acceptable_boundary_band | NO | missing | add (seconds, per annotator) |
| confidence | NO | missing | add (ordinal) |
| ambiguity | partial (`boundary_ambiguous` bool) | upgrade to 3-level (low/med/high) |
| required_evidence | NO | missing | free-text per event |
| exclusion_rationale | NO | missing | free-text for rejected candidates |

## What already satisfies ERAEA requirements

- Two independent annotators + adjudication, preserving both originals
  (protocol requirement).
- Blinding: server exposes no selector/K3/algorithm outputs (verified in
  `serve_p1_human_reference.py`); annotator UI is outcome-blind.
- Six frozen cases (3 videos x 2 queries) with video sha256s — sufficient for
  a protocol pilot (the ERAEA blueprint asks for >=2 domains at formal scale;
  the current two queries are one domain family).
- Annotation schema validation and append-only storage.

## Recommended pilot steps (protocol design only; no execution without human-work authorization)

1. Freeze a NEW pilot schema `ERAEA_PILOT_EVENT_SCHEMA.json` containing all 11
   ERAEA fields (leave `HUMAN_REFERENCE_PROTOCOL.json` untouched).
2. Reuse the six frozen cases; each annotator labels maximal temporal events
   AND per-event core/band/confidence/evidence/exclusion.
3. Adjudication pass: reconcile intervals, keep disagreements (no forced
   single-point boundary).
4. After freeze: compute the CPU-only geometric ceilings (event duration
   distribution, 2s/5s/10s recall ceilings, boundary quantization, adaptive
   granularity oracle) — this is the G_granularity gate, currently blocked.

## Blocker record

- HUMAN_P1_ANALYSIS_AUTHORIZED = NO (labels incomplete).
- CPU geometric granularity analysis (prompt section 7) = BLOCKED until a
  continuous-time human reference exists; the model-relative 10s-quantized
  reference cannot estimate sub-10s event proportions.
