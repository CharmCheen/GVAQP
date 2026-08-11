# Reference Recovery Options Audit

## Scope

This audit determines whether the current repository can complete the V3
reference after the V9 formal abort without changing a frozen semantic or
reference-execution protocol.  It does not inspect semantic labels or compute
downstream retrieval metrics.

## Option 1 — Restart V9

**Rejected by source contract.**  The V9 state is terminal (`STOPPED`) and
`GlobalFailStopCoordinator` documents: “No method permits resume.”  The V9
failure policy additionally classifies a cost-invalid/incomplete run as
ineligible for publication.  Reinvoking V9 would be a forbidden retry, not a
resume.

## Option 2 — Run only the 21 missing DALI units and merge them with V9

**Not legal under the frozen protocol.**  It is attractive computationally,
but not a repair that the present system supports:

- V9's failure policy prohibits access to its incomplete raw labels as a
  reference input.
- Unit records bind `execution_seal_sha256`; a new tail run necessarily has a
  different seal.
- The frozen analyzer validates every record against one seal and requires a
  single complete global ledger, exactly three loads, the sealed staged
  activation record, no stop intent, and exactly 1,475 accepted calls.
- The frozen coordinator rejects both an existing state and any duplicate or
  retried unit.

Making a merged V9/V10 evaluator would require a new multi-seal provenance
rule, a new finalizer, and a new reference-release policy.  That is not a
pure worker restart or checkpoint repair; it changes the frozen execution and
evaluation contract.  The user has not authorized such a change.

## Option 3 — New fresh-from-zero V10 with unchanged semantic bindings

**Semantically possible but not covered by the current compute authority.**
It would preserve model, processor, prompt, query, unitization, parser,
generation, K3 reference semantics, and the DALI/HANGZHOU/WUHAN GPU-pair
topology.  A runtime-only revision could address the demonstrated 2-second
idle-lease failure.

However, before V10 the conservative accounting used by the V9 approval plus
actual V9 residency is 48.651173136404445 A100 GPU-hours, leaving only
15.348826863595553 inside the present 64-hour cap.  The frozen full-grid point
estimate is 16.59314522789404 hours.  The available authority therefore does
not cover a defensible new full-grid hard envelope.

## Option 4 — Use V9 partial results as evaluation labels

**Rejected.**  This would violate both the frozen failure policy and the
long-horizon reference-completeness gate.  In particular, it would leave
DALI's final 21 units without authoritative terminal outcomes.  No missing
unit may be treated as negative, unknown, or excluded post hoc.

## Result

There is no legal local path to a complete model-relative V3 reference under
the existing protocol and 64 A100 GPU-hour authorization.  The outstanding
requirement is external authority, not an unperformed engineering action.

### Required user decision

Authorize one of the following explicitly:

1. a new V10 fresh-from-zero, semantic-binding-preserving full-grid run with a
   stated total compute cap above the current 64 A100 GPU-hours and a newly
   frozen runtime-only idle-lease contract; or
2. a new multi-seal checkpoint-recovery/reference protocol permitting V9
   accepted records plus the 21 missing units, acknowledging that this is a
   protocol change rather than a resume under the existing V9 seal.

Until then, P0 remains prohibited because no formal reference relation exists.
