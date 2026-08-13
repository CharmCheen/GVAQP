# P1-B annotation blinding audit — v1.2

`ANNOTATION_BLINDING = PASS`

- The server uses an explicit allowlist: `/`, `/api/cases`, the three raw-video URLs, and POST `/api/save`.
- Direct GETs for the annotation log, trace population, adjudication template, and arbitrary output paths return HTTP 404.
- `/api/cases` contains only case identity, raw-video location/integrity metadata, frozen query/guide text, clock metadata, and frozen status fields. It contains no proxy identity/score, candidate position, VERIFY outcome, trace/pair/policy identity, geometry, pseudo-reference, C0/C1/K3 output, or performance metric.
- The server has no read endpoint for saved annotations. ANNOTATOR_A cannot retrieve ANNOTATOR_B records, and vice versa. Browser drafts are namespaced by annotator ID and case; formal saves are append-only.
- HTTP byte-range seeking for raw videos was verified.

The phrase “EventF1” may appear only inside the frozen guide's explicit list of prohibited artifacts; no EventF1 value is exposed.
