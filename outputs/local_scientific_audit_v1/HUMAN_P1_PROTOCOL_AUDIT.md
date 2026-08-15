# Human P1 Protocol Audit (protected confirmatory experiment)

Compliance note: this audit read ONLY protocol files, freeze hashes,
annotation status metadata, schema, and server code. It did NOT read human
annotation content, human event intervals, intermediate event counts, partial
agreement, or partial outcomes. (The label log is empty, so no such content
exists anyway.)

## Protocol status

| Field | Value | Verification |
|---|---|---|
| HUMAN_P1_PROTOCOL_STATUS | FROZEN_BEFORE_HUMAN_LABELS | `HUMAN_REFERENCE_PROTOCOL.json` status field; file sha256 `62575b06…` matches `RESEARCH_STATE.json` claim |
| Cases frozen | 6 = 3 videos (DALI/HANGZHOU/WUHAN) × 2 queries (Q_DRIVER_RESPONSE_V1, Q_VULNERABLE_ROAD_USER_CONFLICT_V1) | protocol file |
| Annotators required | 2 independent + adjudication | protocol file |
| Prohibitions | no query redefinition, no boundary edits to help an algorithm, no case deletion, no method-result leakage to annotators | protocol file |
| Source video hashes | DALI `64cb0cfa…`, HANGZHOU `69649cd2…`, WUHAN `bad22900…` | protocol file |
| Label log rows | **0** | verified: empty file, sha256 `e3b0c442…` |
| Reference independence declaration | independent of C0/C1/K3/proxy policies/geometry hypothesis/semantic oracle outcomes/event-recovery results | protocol file |

## Server code (scripts/serve_p1_human_reference.py)

- Local-only server (127.0.0.1), serves the video and case metadata; the
  `/api/cases` endpoint exposes only case identity + video URL + query text
  (no oracle/proxy/trace/result data — blinding holds).
- POST validation enforces: case identity match, boolean `event_exists`
  consistency with the event list, each interval `0 <= start < end <=
  video_duration`, and `boundary_ambiguous` boolean. Appends rows with
  `saved_at_utc`. No content is read or graded by the server.
- Blinding: no algorithm outputs are served; annotations append-only.

## Frozen analysis implementation

- `P1_ANALYSIS_IMPLEMENTATION_MANIFEST.json` is hash-bound
  (sha256 `1c1e3d4c…` per RESEARCH_STATE.json); the analyzer calls the frozen
  P0 matching implementation; 10,000-replicate video-query-cluster bootstrap
  is prespecified; trace strata are not treated as independent.

## Automated preparation (non-human) — complete

- 1475/1475 Qwen3-VL-32B grid records verified; 1008 trace-query rows; 198
  equal-positive matched contrasts; 12 cluster summaries — all re-verified
  counts locally. These are model-relative diagnostics, NOT human endpoints.

## Verdicts

- HUMAN_P1_PROTOCOL_STATUS = FROZEN / READY / BLINDED
- HUMAN_LABEL_COUNT_METADATA_ONLY = 0 ROWS (nothing to analyze)
- HUMAN_P1_ANALYSIS_AUTHORIZED = **NO** (labels remain incomplete; two
  independent annotations plus adjudication are still required)

No part of the P1 protocol or frozen package was altered by this audit.
