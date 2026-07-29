# V3 Run Status

State: `FULL_GRID_PREREGISTRATION_IMPLEMENTATION_IN_PROGRESS_NO_INFERENCE`

Current decision: `V3_SCHEMA_DETERMINISM_PASS_FULL_GRID_APPROVAL_REQUIRED`

Objective: establish whether the frozen Qwen3-VL-32B unit predicate is a
strict, stable model-relative labeler and whether K3 deterministically turns
those labels into `32B-relative EventRelation`.

Established:

- V2 remains frozen at `REVISE_ORACLE_PROTOCOL`.
- V3 code/schema/K3 and evidence-authentication tests: 94 passed.
- Seven exact V2 frame sets and 11 calls are frozen.
- Direct model-file rehash and exact frame decode pass for all three shards.
- Execution seal:
  `bf35f7f3c9f897f337a838f36991ab502cf538fd602b779ab8afd245b0b9ce61`.
- The earlier seal `84d352fb…` received an independent `NO-GO` and is invalid.
  Its raw/ledger/runtime authentication and same-process identity blockers were
  repaired before this reseal.
- Final independent review returned `GO` for the exact current seal and source
  commit. This is approval to request compute only; it is not compute approval.
- Estimated compute: 0.185659 A100 GPU-hours including loads/call overhead;
  approximately 0.19 A100 GPU-hours plus normal host overhead.
- The exact user approval artifact binds the reviewed execution seal.
- Exactly 11 physical calls completed on the frozen 5/3/3 schedule: 11/11
  strict parse, 10 `not_relevant`, 1 `relevant`, 0 `unknown`, 0 failures, and
  0 retries.
- Three same-process pairs and one cross-replica pair match authoritative
  label, processed-input identity, and exact raw response. Session relations
  also pass.
- K3 forward/reverse/diagnostic-variant relations are identical at
  `9d4a40f3…`; one 32B-relative event was materialized.
- Actual cost including three loads and call overhead was 0.151724 A100
  GPU-hours, below the 0.185659 estimate.

Remaining scope limitation:

- Eleven decision-focused calls do not establish representative adequacy over
  all 1,475 units. No full-grid or downstream work is authorized.
- No unknown or parse failure occurred physically; their preservation semantics
  remain established by the frozen contract/tests rather than an observed case.
- Post-output diagnostics retain three agent/model polarity disagreements and
  explanation-grounding limitations without affecting the model-relative gate.

Full-grid proposal state:

- Revision 1 was independently rejected for an invalid label-hiding claim,
  unbounded reload/resume accounting, unspecified concurrent-shard failure
  semantics, and possible publication of a partial relation.
- Revision 2 freezes an evaluator-only/causal-VERIFY label boundary, exactly
  three loads and zero reloads, global fail-stop, a cost shield, and atomic
  complete-only publication.
- Independent re-review of exact JSON SHA `ffc47c8b…` and document SHA
  `69be8d05…` returned `GO_TO_PREPARE_FULL_GRID_PREREGISTRATION`.
- The tail-unit sampler, exact 1,475 call/frame manifests, cost/failure
  mechanisms, output schemas, analyzer/finalizer, and execution seal do not yet
  exist and must be implemented and independently reviewed in a separately
  authorized preparation stage.

Next highest-value action: stop and ask whether the user authorizes preparation
and sealing of the exact full-grid package. The review `GO` does not authorize
frame expansion, model loading, any of the 1,475 calls, or downstream work.

## Authorized preregistration preparation cycle

The user subsequently authorized preparation, input decoding/freezing,
no-inference dry-runs, sealing, and independent review. This authority does not
include any Qwen3-VL-32B generation call.

Observed implementation evidence so far:

- The repository is on clean `dspro`; all eight A100s had no compute process at
  cycle start.
- New full-grid-only modules leave every frozen preflight source/output
  untouched.
- The tail rule is source-anchored `k/2 <= true duration` and leaves all normal
  endpoint-inclusive units unchanged.
- Global fail-stop, three-load/zero-reload accounting, complete-only atomic
  publication, evaluator-only labels, and Ed25519-authenticated causal VERIFY
  history are implemented.
- 115 focused accelerated-event-query tests currently pass; exact source-video
  decode and real processor-only tail validation remain pending.

Decision-critical uncertainty: whether the real decoder and frozen Qwen
processor accept all three 12/2/6-frame tails with exact provenance and whether
the resulting 30,932-frame manifest survives a second full decode and
independent adversarial review.

Next action: commit the tested implementation, decode and freeze all 1,475
inputs without loading model weights, then run package dry-runs and review.
