# AEQ Model-Relative Oracle V3 Preflight Report

Final decision:
`V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED`

Execution seal:
`bf35f7f3c9f897f337a838f36991ab502cf538fd602b779ab8afd245b0b9ce61`

Scope: the exact 11-call schema-and-determinism preflight only. This is not a
representative audit, does not authorize the 1,475-unit grid, and supports no
YOLO ceiling, replay, headroom, value-learning, or controller claim.

## A. Protocol adequacy

### Strongest supported conclusion

For the frozen sample, checkpoint, prompt, frames, processor, decoding profile,
and K3 contract, Qwen3-VL-32B functioned as a strict and reproducible
model-relative unit labeler. K3 deterministically constructed the same
`32B-relative EventRelation` from those labels. Every frozen hard gate passed.

### Decisive execution evidence

| Gate | Observation | Result |
|---|---|---|
| Authentication | 11 expected raw records, 0 extra/missing; exact seal/model/prompt/schema/frames/GPU/runtime/approval bindings | PASS |
| Attempts | 11 each of prepared, started, completed, accepted; 0 failure, interruption, or retry | PASS |
| Strict parsing | 11/11 `ok`; no duplicate, extra, missing, invalid, or authoritative-time field | PASS |
| Class support | 10 `not_relevant`, 1 `relevant` | PASS |
| Same-process reproducibility | Three pairs match label, model input, processed input, and exact raw response; session equality authenticated | PASS |
| Cross-replica reproducibility | `DALI_u0555` matches label, model input, processed input, and exact raw response; replica sessions differ | PASS |
| Sampling diagnostic | `DALI_u0548` is `not_relevant` at both 2 and 4 fps | Non-gating equality observed |
| K3 eventization | Forward, reverse, and diagnostic-mutated relation hashes all `9d4a40f3…`; boundaries use units only | PASS |

The preflight materialized one 32B-relative event from `WUHAN_u0171` and no
unknown or parse-failure unit. Actual cost, including three two-GPU model loads
and call overhead, was `0.1517243908` A100 GPU-hours, below the pre-registered
estimate `0.1856586523`. Total inference time was 201.694 seconds over 251 frame
occurrences.

### Integrity evidence

- Metrics file SHA-256: `2003e29a3d427a892c16c68925db3f0712d15ce73e37eca1a4c06461778d4df4`
- Evidence manifest SHA-256: `c034309844cca41e6bc85491ff5997423c2b517bb0b33568750032a7df91d836`
- Decision file SHA-256: `be04bc401d65835f32709f88a7ed492dac8ddf9136cecd14939e20a3ba59eb90`
- Decision payload SHA-256: `4dc2292a61eb8bb10a698226147bbe64ab289bb3e130c1236dad591bde949982`
- K3 config SHA-256: `7906ab2da20cab7edbe0f379224b60160c7a857cd81ab7f4fec42f54ab9629b9`

The finalizer did not trust stored metrics: it reran the sealed analyzer and
required exact recomputed metrics and parsed payload equality before accepting
the evidence manifest and emitting the one allowed decision.

## B. Construct-validity diagnostics

These findings are preserved as limitations and case evidence. They did not
relabel any unit or change a hard gate.

- `DALI_u0548`: V3 is `not_relevant`; agents marked it relevant. Exact endpoint
  frames show pedestrians entering/occupying roadway, making the categorical
  “not in roadway” explanation unsupported. The marked response may fall at or
  beyond the unit boundary. V3 contains no authoritative time coordinate.
- `DALI_u0555`: V3 is `not_relevant`; agents marked it relevant. A pedestrian
  and scooter are visible in/near the forward travel area, but exact clearance
  and ego response are unmeasured.
- `HANGZHOU_u0234`: V3 and agents are `not_relevant`. The straight approach is
  green and the crosswalk is unoccupied; V3 avoids the unsupported V2 red-phase
  explanation.
- `WUHAN_u0217`: V3 is `not_relevant`; agents marked it relevant. A red-clad
  rider approaches on a constrained street, but exact ego-path membership and
  response magnitude remain indeterminate.
- `WUHAN_u0171`: V3 is `relevant`, consistent with agents. Crossing users make
  braking plausible, but the diagnostic claim that the light turns red around
  0:07 is unsupported; the signal is already red earlier. This text cannot
  influence K3 boundaries.

Thus there are three retained agent/model polarity disagreements, two primary
whole-explanation `UNSUPPORTED` verdicts, one `INDETERMINATE` verdict, and one
additional unsupported timing subclaim. None is a model-relative label error.

### Main competing explanation and uncertainty

The PASS may be sample-specific. Ten of eleven calls were `not_relevant`, only
one event was materialized, and no physical unknown or parse failure occurred.
Therefore the pilot directly establishes protocol execution and repeatability,
but not representative label distribution, construct validity, rare-output
handling frequency, or three-video full-grid oracle adequacy.

## Required final answers

1. **Why does V2 remain `REVISE_ORACLE_PROTOCOL`?** V2 had only 31/32 strict
   parse, an impossible 17–20-second authoritative boundary, three polarity
   contradictions, and independently unsupported explanations. V3 is a new
   contract and does not reinterpret or overwrite V2.
2. **What is V3 ground truth?** The unit label emitted by the exact frozen
   Qwen3-VL-32B checkpoint/prompt/frame-processing/sampling/decoding pipeline.
3. **Which fields are authoritative?** Only `label`. `confidence` and
   `evidence` are required diagnostic fields and never control the relation.
4. **How are free time-coordinate errors eliminated?** Time keys are absent
   from and rejected by the exact schema. K3 derives boundaries solely from
   frozen unit intervals; time prose inside evidence is ignored.
5. **How are unknown and parse failure handled?** Both are preserved as
   indeterminate and never negative. One short unknown may bridge under the
   frozen K3 rule; parse failure is a hard indeterminate barrier. Neither
   occurred physically in this sample.
6. **How does K3 construct EventRelation?** It groups relevant units under the
   frozen adjacency/one-unknown-gap/cap/boundary/dedup/identity rules, then uses
   one-to-one overlap matching.
7. **What role does agent disagreement play?** Non-gating construct-validity
   and limitation evidence only; three disagreements were preserved.
8. **Is same-process label reproducibility established?** Yes for all three
   frozen pairs, including exact processed-input and raw-response equality.
9. **Is cross-GPU label reproducibility established?** Yes for the frozen
   `DALI_u0555` replica pair, including processed input and raw response.
10. **Is K3 eventization deterministic?** Yes on actual V3 labels: forward,
    reverse, and changed-diagnostic relations are identical.
11. **Exact calls and cost?** 11 calls on 5/3/3; actual cost 0.151724 A100
    GPU-hours; zero retries.
12. **Is a full 1,475-unit request justified?** A separately sealed,
    independently reviewed request is now justified as the next experiment.
    It is not authorized by this PASS.
13. **Current final decision?**
    `V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED`.

## Rejection/revision trigger

This preflight conclusion would require revision if any sealed raw/ledger/hash
binding fails later integrity checks. A full-grid proposal must be rejected or
revised if it changes the model-relative contract, cannot authenticate all
1,475 inputs, permits silent retries/relabels, or treats this targeted PASS as
representative adequacy.

## Post-PASS full-grid proposal status

The proposal-only next step has been completed without input expansion or model
execution. Independent review rejected revision 1, which incorrectly treated
the current caller-ID label view as a hiding boundary and left reload,
cross-shard failure, and partial-publication semantics open. Exact revision 2
(JSON SHA `ffc47c8b…`, document SHA `69be8d05…`) closed those points and received
`GO_TO_PREPARE_FULL_GRID_PREREGISTRATION`.

The reviewed plan contains exactly 1,475 calls (567/561/347), estimates
16.097123 A100 GPU-hours and about 3.093 parallel wall hours, permits exactly
three checkpoint loads and zero retries/reloads, and uses global fail-stop plus
complete-only atomic reference publication. It also identifies three truncated
final units whose proposed 12/2/6 source-anchored frames must still be
implemented, decoded, hashed, tested for no overrun, frozen, and independently
reviewed. The review GO authorizes none of that preparation or compute by
itself.
