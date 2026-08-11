# P0 Materializer Validation — Paused Input Required

## Decision

`MATERIALIZATION_MAINLINE_DECISION = PAUSED_INPUT_REQUIRED`

## Stop condition

`STOP-C`: the current V3-controlled matrix requires a frozen common candidate
universe, authoritative oracle outcomes, and a released model-relative K3
reference. The repository has three independent V3 source videos (DALI,
HANGZHOU, WUHAN) and their raw source assets, but not a valid released V3
reference for any of them.

The latest visible V3 full-grid execution state is preserved fail-stop evidence.
The V3 preregistration explicitly marks partial formal reference publication as
forbidden. This P0 run therefore must not derive labels or events from partial
raw output files.

## Available independent videos

- Raw independent V3 sources: 3 (`DALI`, `HANGZHOU`, `WUHAN`).
- Eligible controlled-main-evaluation videos: 0.
- Required minimum: 3 eligible controlled-main-evaluation videos.

## Missing requirement

Release or provide a completed, authenticated V3 full-grid package containing,
for the same frozen unit grid, `unit_labels`, a K3 model-relative event
relation/reference, candidate/proxy tables, and finalizer/provenance artifacts.
The package must cover at least DALI, HANGZHOU, and WUHAN and preserve the
frozen K3 config and matching rule.

## Minimum user action

Authorize/complete the already preregistered V3 full-grid reference release, or
provide an equivalent completed frozen V3 reference package. No new dataset,
manual relabeling, selector tuning, or algorithm change is required to resume.
