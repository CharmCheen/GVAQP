# V3 Hypothesis Registry

## H1 — Label-authoritative minimal schema reaches 100% strict parse

- Importance: malformed output prevents an authoritative unit label.
- Minimal experiment: 11 sealed calls with exact three-field parsing.
- Expected result: 11/11 `ok`, exact keys, valid vocabulary.
- Failure condition: any malformed, duplicate, missing/extra-key, or invalid
  required field output.
- Competing explanation: truncation or instruction-following can fail even when
  the schema is locally correct.
- Impact: pass supports H3/full-grid request; failure gives `REVISE_V3_SCHEMA`.
- Status: `SUPPORTED_BY_PREFLIGHT`; all 11 physical responses parsed strictly.

## H2 — Removing authoritative time fields eliminates V2 timestamp anchoring failure

- Importance: V2 failed on an impossible 17–20-second boundary.
- Minimal experiment: parser/schema regression on `DALI_u0548`, plus 2/4-fps
  physical outputs.
- Expected result: no accepted object contains a time field; K3 uses unit
  coordinates.
- Failure condition: parser accepts a time key or K3 consumes evidence timing.
- Competing explanation: timing hallucinations may persist inside diagnostic
  evidence but are harmless to the authoritative relation.
- Impact: authority leakage gives `REVISE_V3_SCHEMA` or
  `REVISE_K3_EVENTIZATION`.
- Status: `SUPPORTED`; all V3 outputs have only the three frozen fields and K3
  ignored the diagnostic 0:07 time claim in `WUHAN_u0171`.

## H3 — Identical-input authoritative labels are reproducible

- Importance: exhaustive model-relative reference construction requires stable
  unit labels.
- Minimal experiment: three same-process pairs and one cross-replica
  `DALI_u0555` pair.
- Expected result: label and processed-input equality; exact raw equality is
  reported under deterministic decoding. Same-process pairs share an
  authenticated execution session; the cross-replica pair does not.
- Failure condition: any label/processed-input mismatch or session-relation
  violation.
- Competing explanation: diagnostic wording may differ without label change.
- Impact: label failure revises schema; processed/session failure revises input
  binding.
- Status: `SUPPORTED_BY_PREFLIGHT`; all three same-process pairs and the
  cross-replica pair match label, processed input, and exact raw response.

## H4 — K3 deterministically builds EventRelation from unit labels alone

- Importance: event identity/boundaries must not leak from VLM prose.
- Minimal experiment: reorder labels and mutate diagnostics while testing gaps,
  overlaps, caps, dedup, and deadline guard.
- Expected result: exact relation equality and unit-grid-only boundaries.
- Failure condition: order/diagnostic sensitivity, unstable identity, or
  post-deadline mutation.
- Competing explanation: adjacent distinct latent events are not identifiable
  and merge by explicit observable semantics.
- Impact: implementation failure gives `REVISE_K3_EVENTIZATION`.
- Status: `SUPPORTED_BY_PREFLIGHT`; forward, reverse, and changed-diagnostic
  relation hashes are identical on actual V3 labels.

## H5 — Unknown and parse failure remain explicit without contaminating negatives

- Importance: coercion would bias 32B-relative precision/recall.
- Minimal experiment: parser/store/K3 fixtures with both outcomes.
- Expected result: dedicated lists; neither negative; one unknown may bridge,
  parse failure cannot.
- Failure condition: either enters the negative list or disappears.
- Competing explanation: a hard parse-failure barrier may reduce merging but
  still does not make the unit negative.
- Impact: schema or K3 revision if violated.
- Status: `SUPPORTED_BY_CONTRACT_AND_TESTS`; neither outcome occurred in the
  physical 11-call sample, so occurrence-level behavior remains unobserved.

## H6 — Semantic disagreement remains diagnostic without changing the reference

- Importance: V2 review evidence is useful but has a different authority level.
- Minimal experiment: retain five V2 cases and mutate diagnostics while checking
  labels/relation and decision mapping.
- Expected result: concerns persist; gate result is unchanged.
- Failure condition: agent review/grounding relabels a unit or changes a gate.
- Competing explanation: severe limitations may make the model-relative task
  scientifically uninteresting, but that is not label correctness.
- Impact: authority leakage revises the protocol; otherwise report limitations.
- Status: `SUPPORTED`; post-output review retained three polarity disagreements
  and explanation limitations with zero authoritative relabels or gate changes.
