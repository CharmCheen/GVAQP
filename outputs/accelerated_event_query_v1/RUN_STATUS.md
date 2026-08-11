# Accelerated Event Query V1 — Run Status

Overall status: `IN_PROGRESS`

Current research-loop decision: `REVISE_ORACLE_PROTOCOL`

Terminal decision: `NOT_YET_JUSTIFIED`

Targeted V2 pilot decision: `REVISE_ORACLE_PROTOCOL`

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
- The repair binds an explicit 32-entry call manifest (24 base, six sensitivity, two replica anchors), a direct full-file 35.53 GB model rehash, duplicate-key rejection, a pre-model-load crash audit under per-shard locks, exact `INFERENCE_STARTED`/`INFERENCE_COMPLETED`/`ACCEPTED` accounting, a mandatory exact-scope user-approval artifact, and a sealed grounding/finalization protocol.
- CPU-only validation passed for the sealed 10/11/11 shard schedules: all bindings, 19 current model files, three video hashes, exact frame indices/RGB hashes, and 32 call identities matched.
- The second audit passed the eight original blocker areas but returned NO-GO on one linked defect: metadata/frame identities could match while the actual processor tensor bundle differed. The replacement seal forces PREPARED and INFERENCE_STARTED tensor hashes to equal the accepted record, requires actual processed-input equality for repeats and replica anchors, and requires one preprocessing-runtime fingerprint.
- Independent re-review of commit `b09f99974` / seal `58f84d2c...` returned GO for requesting explicit user approval. The reviewer independently injected a processed-input reconciliation mismatch and observed fail-closed behavior; all sealed bindings matched and no new blocking bypass was found.
- The explicitly approved pilot completed exactly 32/32 calls on disjoint GPU pairs `(1,2)`, `(3,5)`, and `(6,7)`: every shard has one PREPARED, INFERENCE_STARTED, INFERENCE_COMPLETED, and ACCEPTED event per call; there were zero retries, failed generations, or uncertain interruptions.
- Engineering reproducibility passed: all 12 identical-input repeat pairs and all three cross-replica anchor observations had identical metadata, processed tensors, and raw output; class support also passed across all three videos.
- Oracle adequacy failed. Strict parse success was 31/32 rather than 32/32 because a 10-second 4-fps clip claimed relative event bounds `17.0–20.0`. Three decided-polarity contradictions occurred across DALI, HANGZHOU, and WUHAN, satisfying the frozen systematic semantic-failure condition.
- Independent post-output grounding found 2/4 unique positive claims unsupported: WUHAN falsely claimed the light turned red at 6.0 seconds although it was already red, and HANGZHOU attributed a left-turn red signal to the straight lane while the straight arrow remained green and the crosswalk was empty.
- The frozen finalizer returned `FAIL_NUMERIC_OR_SUPPORT_GATE`; the pre-output user mapping produced the sole targeted-pilot decision `REVISE_ORACLE_PROTOCOL`. Measured inference usage was 790.67 seconds across two GPUs per call, or 0.4393 A100 GPU-hours.

## Active hypotheses

- H1: rejected—the frozen 32B protocol is reproducible but not semantically/contractually adequate.
- H2: suspended because H1 failed and no complete new-query operational reference is authorized.
- H3: suspended because H1/H2 and cost-safety prerequisites are unmet.

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
- complete 32-record raw corpus, three append-only attempt ledgers, frozen metrics/grounding/final decisions, and `PILOT_EVIDENCE_MANIFEST_V2.json`

## Missing decision-critical evidence

- a revised oracle protocol capable of passing a new independently reviewed preflight; no such revision or compute is authorized
- complete new-query 32B oracle with raw output retention (scientifically and computationally unauthorized after H1 failure)
- operational reference events
- full YOLO scan and K3 event-recall ceiling
- independent cost-calibration safety gate
- label-hiding replay and dynamic headroom
- state models, closed-loop evaluation, and ablations (correctly not run yet)

## Next action

Stop and report `REVISE_ORACLE_PROTOCOL`. Do not request representative/full-oracle, YOLO, replay, headroom, or controller compute. Any future work must begin with an offline causal diagnosis and a newly frozen, independently reviewed protocol; the present approval is exhausted.
