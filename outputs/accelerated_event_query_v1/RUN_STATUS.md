# Accelerated Event Query V1 — Run Status

Overall status: `IN_PROGRESS`

Current research-loop decision: `REVISE_ORACLE_PROTOCOL`

Terminal decision: `NOT_YET_JUSTIFIED`

## Objective

Under the same hard deadline and event-precision requirement, determine whether causal dynamic SCAN/VERIFY allocation returns more K3-reconstructed driver-response events and returns them earlier than the best fixed or two-stage policy.

## Established findings

- Three real videos are present, decodable, and content-hash frozen: Dali, Hangzhou, Wuhan.
- The existing center10 unit semantics can be reused, yielding 1,475 non-overlapping units.
- Existing Dali/Wuhan operational labels are not semantically interchangeable with the new query.
- Prior 32B A100 execution is feasible only as a two-GPU BF16-dequantized path and is fallible.
- Prior binary-SMDP headroom evidence remains insufficient: one approximate SCAN-better state, no VERIFY-better states, four ties, and incomplete/unsafe cost support.
- New event/K3/matching/state-boundary/oracle-schema/protocol tests: 51 passed with `PYTHONPATH=src pytest -q tests/accelerated_event_query`.
- A twelve-clip, 2 fps contact-sheet review was frozen before any new-query 32B output. It is explicitly a fallible adversarial screen, not human ground truth; five clips are qualitatively `not_relevant`, four `relevant`, and three `unknown`.
- V1 attempted a machine-checkable unsupported-positive gate, but independent review showed it ignored medium-confidence and false-negative failures; it is retained only as rejected evidence.
- Independent critique falsified that V1 gate before execution: reviewer/model frame mismatch, incorrect nominal 4 fps, permissive parsing, unauthenticated raw records, degenerate false passes, and insufficient authorization scope.
- V2 exact input manifests contain 12 endpoint-inclusive 21-frame base sets and six exact 41-frame sensitivity sets. Two pre-outcome reviewers agreed on 10/12 clip labels; disagreements are retained as unknown.
- The first independent V2 implementation audit rejected execution: the derived schedule was not source-sealed, model identity was partly declarative, attempt accounting did not prove exact artifact/input/hash triples or forbid physical retries, crash recovery ran too late, 4 fps positives escaped grounding, duplicate JSON keys were accepted, and no frozen finalizer could legitimately reach pass.
- The repair now binds an explicit 32-entry call manifest (24 base, six sensitivity, two replica anchors), a direct full-file 35.53 GB model rehash, duplicate-key rejection, a pre-model-load crash audit under per-shard locks, exact `INFERENCE_STARTED`/`INFERENCE_COMPLETED`/`ACCEPTED` accounting, a mandatory exact-scope user-approval artifact, and a sealed grounding/finalization protocol. These repairs have passed local falsification tests but not yet the second independent audit.
- CPU-only validation passed for the sealed 10/11/11 shard schedules: all bindings, 19 current model files, three video hashes, exact frame indices/RGB hashes, and 32 call identities matched. Physical oracle calls remain 0/32.
- The second audit passed the eight original blocker areas but returned NO-GO on one new linked defect: metadata/frame identities could match while the actual processor tensor bundle differed. The replacement seal now forces the ledger's PREPARED and INFERENCE_STARTED tensor hashes to equal the accepted record, requires actual processed-input equality for repeats and replica anchors, and requires one preprocessing-runtime fingerprint. Local tests and CPU-only 10/11/11 validation pass; independent re-review of this replacement seal is pending.
- Independent re-review of commit `b09f99974` / seal `58f84d2c...` returned GO for requesting explicit user approval. The reviewer independently injected a processed-input reconciliation mismatch and observed fail-closed behavior; all sealed bindings matched and no new blocking bypass was found.

## Active hypotheses

- H1: the frozen 32B prompt yields stable enough operational labels.
- H2: frozen YOLO candidates plus K3 have adequate event-recall ceiling.
- H3: event-calibration verification exposes safe cross-video binary switching headroom.

## Failed/rejected paths retained

- Old-query labels as new-query truth: rejected for semantic mismatch.
- Immediate learned controller: rejected until oracle, scan-ceiling, and safety gates pass.
- Historical Q90 dynamic-oracle gain: retained but invalid for the new safety contract because it admitted overruns.

## Artifacts completed this cycle

- `docs/ACCELERATED_EVENT_QUERY_CONTRACT_V1.md`
- `docs/ACCELERATED_EVENT_QUERY_REPORT_V1.md`
- `docs/ACCELERATED_EVENT_QUERY_NEXT_DECISION.md`
- frozen query/oracle/K3/matching config and prompt
- three-video identity manifest
- incremental event K3, event matcher, causal state schema, and targeted tests
- hash-bound contact-sheet manifest, pre-outcome blinded review, and tested contradiction analyzer
- preserved V1 invalidation audit; V2 strict prompt/config/parser, exact RGB frame manifest, explicit call authorization, full model manifest, dual-review consensus, targeted preregistration, grounding protocol, and execution-source seal

## Missing decision-critical evidence

- explicit user approval for the exact H1 V2 32-call targeted pilot
- H1 V2 targeted pilot execution and post-output grounding (expected 32, observed 0)
- complete new-query 32B oracle with raw output retention
- operational reference events
- full YOLO scan and K3 event-recall ceiling
- independent cost-calibration safety gate
- label-hiding replay and dynamic headroom
- state models, closed-loop evaluation, and ablations (correctly not run yet)

## Next action

Request explicit user approval for the exact sealed 32-call targeted pilot. If approved, materialize the approval artifact and run only the three authorized 10/11/11 shards; if not approved, retain the current nonterminal state without spending oracle budget.
