# AEQ Model-Relative Operational Oracle V3 Contract

Status: `PREFLIGHT_PASS_FULL_GRID_APPROVAL_REQUIRED`

Execution seal SHA-256:
`bf35f7f3c9f897f337a838f36991ab502cf538fd602b779ab8afd245b0b9ce61`

## Objective and evidence level

For the frozen query “查找需要驾驶员明显减速、制动或避让的事件。”, V3 defines the
unit predicate as

```text
y*(u,q) = f_Qwen3-VL-32B(u,q) ∈ {relevant, not_relevant, unknown}
```

under the exact hash-bound checkpoint, prompt, preprocessing, sampling, schema,
parser, decoding configuration, and seed. This is model-relative ground truth.
It is not human driving ground truth and cannot support an absolute semantic
accuracy claim.

All formal results must use `32B-relative event recall`, `32B-relative event
precision`, and `32B-relative EventRelation`.

V2 remains a separate frozen experiment with decision `REVISE_ORACLE_PROTOCOL`.
V3 does not reinterpret, overwrite, relabel, or promote any V2 result.

## Authority boundary

32B owns one authoritative field: `label`. `confidence` and `evidence` are
diagnostics only. 32B does not own event start/end, response onset/end, event
identity, merging, or deduplication. The exact output object is:

```json
{
  "label": "relevant | not_relevant | unknown",
  "confidence": "high | medium | low",
  "evidence": "nonempty string"
}
```

The object must have exactly these three keys. Whole-string parsing rejects
markdown fences, prefixes/suffixes, duplicate keys, missing/extra keys, invalid
vocabulary, invalid confidence, and empty/whitespace evidence. Confidence and
evidence are retained because they are useful construct-validity diagnostics;
as required fields, structurally malformed diagnostics make the whole object
`parse_failure`. Once the object parses, neither field can alter the label.

Any time/onset/offset field is an extra key and therefore invalid. Natural
language time claims inside diagnostic evidence are stored but never consumed
by EventRelation construction. This removes the V2 `DALI_u0548` 17–20-second
failure from the authoritative data model instead of repairing it post hoc.

## Unit outcomes

| Outcome | K3 meaning | Negative? |
|---|---|---|
| `relevant` | positive support | no |
| `not_relevant` | explicit negative/barrier | yes |
| `unknown` | indeterminate; may bridge only under the frozen short-gap rule | no |
| `parse_failure` | invalid/indeterminate hard barrier | no |

Neither `unknown` nor `parse_failure` may be coerced to `not_relevant`.

## 32B-relative EventRelation and K3

```text
EventRelation^32B_q = K3({u : y*(u,q) = relevant})
```

The reference adapter reuses the existing `EventRecord`, matching kernel,
stable-ID convention, and deadline-safe mutation pattern. It does not modify
the existing online `IncrementalK3`.

Frozen reference parameters are:

- unit duration 10 seconds, stride 10 seconds, with only the final video unit
  truncated;
- adjacent/overlapping relevant units merge;
- one fully covering `unknown` unit may bridge positive runs when the temporal
  gap is at most 10 seconds;
- a `not_relevant`, `parse_failure`, missing unit, more than one unknown, or a
  gap over 10 seconds prevents bridging;
- event boundary is exactly minimum positive-unit start to maximum
  positive-unit end; no VLM text expands it;
- core duration cap is 40 seconds and event duration cap is 60 seconds;
- exact repeated unit IDs are deduplicated; overlapping positive windows join
  the same canonical group;
- identity is SHA-256 of query, video, earliest positive unit, and K3 config;
- matching uses strict positive temporal overlap and one-to-one maximum
  cardinality followed by temporal IoU; unmatched overlaps are duplicates;
- post-deadline updates mutate no durable unit or EventRelation state.

The K3 parameter hash is
`7906ab2da20cab7edbe0f379224b60160c7a857cd81ab7f4fec42f54ab9629b9`.

Only unit labels cannot distinguish two latent human events occupying adjacent
positive units from one longer event. V3 explicitly defines such runs as one
observable model-relative event until a barrier or duration cap. This is a
construct-validity limitation, not hidden extra authority for 32B or an agent.
Online probable identity remains owned by the existing `IncrementalK3`; the
exhaustive V3 reference contains only `VERIFIED_EVENT` records.

## Diagnostic separation

Protocol adequacy is decided only by authentication, strict parsing,
authoritative-label reproducibility, class support, and deterministic K3
eventization. Agent polarity disagreement, explanation grounding,
signal-lane interpretation, ego-path interpretation, evidence plausibility,
and human semantic concerns are retained separately. They cannot relabel a V3
unit and cannot change a V3 protocol decision.

## Preflight and decisions

The frozen preflight contains exactly 11 physical calls: DALI/HANGZHOU/WUHAN
at 5/3/3, with three same-process pairs, one cross-replica anchor, 2/4-fps
coverage, all five required V2 regressions, and `DALI_u0501` as a potential
unknown. It uses zero retries.

Each runner invocation emits an authenticated execution-session identity into
every ledger event and raw/runtime record. All calls in a shard, including the
three same-process pairs, must share exactly one session; shard sessions must be
distinct, including the cross-replica pair. A crash/resume split is therefore a
hard input-binding failure rather than an unobserved change of test semantics.

The analyzer recomputes model-input identities, revalidates approval and full
runtime provenance, joins every successful ledger chain to its raw record, and
writes one parsed artifact per call plus a write-once post-run evidence
manifest. The frozen pre-execution provenance manifest binds all expected
input/source/raw/parsed/ledger/report paths. The 2/4-fps label comparison is
reported explicitly as a non-gating diagnostic.

Allowed decisions are exactly:

```text
V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED
REVISE_V3_SCHEMA
REVISE_V3_INPUT_BINDING
REVISE_K3_EVENTIZATION
INSUFFICIENT_EVIDENCE
```

A pass does not authorize the 1,475-unit grid. It only supports a separate
proposal, independent review, and explicit compute request. No YOLO ceiling,
replay, headroom, or controller work is authorized before a complete full-grid
reference exists.

## Observed preflight outcome

The exact sealed run completed 11/11 authenticated calls with 100% strict
parse, both required decided classes, exact same-process and cross-replica
label/processed-input/raw-response equality, and deterministic K3 eventization.
The frozen final decision is
`V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED`. No `unknown` or
`parse_failure` occurred; their semantics remain contract- and test-validated.
This targeted result establishes protocol survival only, not representative
three-video adequacy or permission to execute the full grid.
