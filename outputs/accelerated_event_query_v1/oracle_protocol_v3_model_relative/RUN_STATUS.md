# V3 Run Status

State: `REVISE_FULL_GRID_PREREGISTRATION_ADVERSARIAL_REVIEW_NO_INFERENCE`

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

Observed negative evidence from the first real decode attempt:

- The builder stopped before writing any manifest after decoding only 11 of the
  proposed 12 DALI tail targets.
- Frozen grid/container end is `5665.535333s`, but the video stream has 169,962
  frames and ends near `5665.381s`; ideal CFR request index 169,965 therefore
  has no source frame.
- The nearest available source frame is the unique final frame 169,961. It is
  not a repeat of the prior 5.0-second target and preserves the 5.5-second
  target plus explicit requested/decoded provenance.

Decision: enter `REVISE_FULL_GRID_PREREGISTRATION` before any seal. Add an
explicit ideal-index and finite-video-stream boundary resolution field, reject
any resolution that would repeat a frame, then rerun all tests and the complete
decode. The 12/2/6 target counts, prompt, authoritative schema, and K3 contract
remain unchanged.

## First full-grid seal and adversarial rejection

Observed evidence:

- Seal V1 `ffcfb934…` bound exactly 1,475 unique units, disjoint 567/561/347
  workers, 30,932 independently redecoded frame occurrences, legal 12/2/6
  tails, and a processor-only tail PASS. The complete mock analyzer/finalizer
  and 117 tests passed without model inference.
- Independent review of bundle `f558e6fd…` returned
  `REVISE_FULL_GRID_PREREGISTRATION`, not GO.
- The reviewer reproduced an abrupt W0 death with an in-flight call: the
  coordinator remained READY and W1 could reserve another call.
- Processed tensor hashes were runtime-self-consistent only; no expected
  1,475-unit tensor identity was frozen or enforced.
- Same-UID mode `0600` did not prevent guessed absolute-path access to evaluator
  labels; import-root separation was not an access-control boundary.

Revision actions now implemented locally:

- a sealed sole launcher supervises exactly three subprocesses, enforces
  operation leases, stops on abrupt/nonzero death, and terminates live peers;
- the builder and runner share one processor implementation, and every unit
  will carry a frozen expected tensor hash checked before `generate`;
- formal evaluator directories use UID 0/mode `0700`; later runtime is frozen
  to UID/GID 65534 with zero capabilities and excluded evaluator mounts; a real
  setuid guessed-path test passes;
- 120 focused tests pass. A new complete real decode+processor manifest,
  second-process revalidation, seal, dry-run, and independent re-review remain
  required before any approval request.

Current decision: preserve rejected seal V1 and continue revision without any
Qwen3-VL-32B inference. Do not request compute approval yet.

Seal V2 `f986ddc4…` subsequently froze 1,475 distinct processed tensor hashes;
three independent processes redecoded/reprocessed all 1,475 units and matched
every frame/tensor identity. Its dry-run then found a non-safety assertion
staleness: missing supervisor audit maps to `FULL_GRID_ABORTED_RUNTIME`, not the
fixture's older exact expectation `INSUFFICIENT_EVIDENCE`. Formal publication
remained absent and all nine hard injections passed. Seal V2 is preserved and
invalidated; the assertion is revised and requires a new source commit/seal.

The user has expanded authority to 64 A100 GPU-hours and permits direct formal
execution after a GO review. Current A100 use in this expanded authorization is
0.0 hours. Expanded authority does not relax authentication, zero-retry per
formal execution, label hiding, deadline, or partial-publication gates.

## Second supervision review and lifecycle revision

Observed evidence:

- Seal V3 `f84a1861…` passed the complete 1,475-record mock, ten fault
  injections, 120 tests, and reproduced the already frozen 30,932 frame and
  1,475 processed-tensor identities. No Qwen generation occurred.
- Independent review verified that the three V1 blockers were closed, but
  returned `REVISE_FULL_GRID_PREREGISTRATION` on two new lifecycle gaps.
- A supervisor process death could orphan workers created in new sessions;
  their one-time parent check did not terminate them after reparenting.
- A loaded worker could stall indefinitely before `reserve_call`, outside both
  the model-load and call leases and outside complete GPU-residency accounting.

Implemented revision evidence:

- Every formal worker now installs Linux `PR_SET_PDEATHSIG=SIGKILL` against the
  exact sealed supervisor before importing the model stack. A real subprocess
  test confirms that its `/proc` entry disappears when the parent exits.
- The global call reservation now opens before frame decode and processor work.
  After a call closes, the loaded-worker idle gap remains subject to a two-second
  supervisor lease until the next reservation or an explicit terminal worker
  session close.
- Actual GPU cost now includes load time, whole-call time, inter-call gaps, raw
  persistence/ledger gaps, and the final session-close gap. A complete run
  requires exactly three closed worker sessions.
- 123 accelerated-event-query tests pass. Expanded-authorization A100 use is
  still 0.0 hours; no formal raw output or reference exists.

Current decision: rebuild and reseal the exact package, rerun its full mock and
fault suite, and request a third independent adversarial judgment. Execute the
1,475 calls directly only if that exact package receives
`GO_TO_REQUEST_FULL_GRID_APPROVAL` and its approval artifact binds the new seal.

Before completing that rebuild, an internal falsification found one residual
tail window: a worker was excluded from the idle monitor immediately after
session close although its process had not yet exited. The incomplete CPU-only
build was terminated before it wrote a manifest. The runner now deletes the
model and final GPU tensors, collects garbage, clears the CUDA cache, and
synchronizes before session close. A closed-but-live worker remains under the
two-second idle lease until process exit; that worst-case tail is included in
the aggregate envelope reservation. 124 tests pass, including a direct
closed-session/live-process fault. A100 use remains 0.0 hours.

## Third review: prospective cost and GPU-profile rejection

Seal V4 `48c71239…` reproduced byte-identical 1,475-unit, 30,932-frame, and
1,475-tensor identities. Three independent processes redecoded/reprocessed
567/561/347 units successfully; 124 tests and the complete mock with eleven
fault injections passed. Independent review nevertheless returned
`REVISE_FULL_GRID_PREREGISTRATION`.

Decisive negative evidence:

- The advertised 19.3758015-hour reservation included call/load maxima and
  process-exit tails but not 1,475 cumulative durable-output/ledger gaps. Only
  29.53 ms average wall gap per call remained in the envelope, while detection
  was retrospective and could occur after physical overrun.
- All sealed GPUs became occupied by a foreign eight-GPU workload during
  review. The runner authenticated identity, but not zero utilization or
  absence of compute contexts, so it would have accepted a changed cost/runtime
  profile.

Implemented local revision:

- A call reservation now remains open from before decode through durable raw
  output and ACCEPTED-ledger persistence.
- Every worker prospectively holds a reusable eight-second emergency
  reservation from load start until supervisor-observed process exit. Idle
  cost consumes the old reservation; a fresh reservation and next call are
  admitted only if the remaining envelope supports both.
- The supervisor, rather than the last worker, records all three process exits
  and only then marks physical completion.
- Initialization and each worker preload now require zero compute contexts,
  zero utilization, and <=16 MiB used memory on the exact sealed GPUs. The
  current foreign workload is correctly rejected.
- 129 tests pass. Formal calls and expanded-budget GPU use remain zero.

Current decision: rebuild/reseal and independently review the prospective cost
shield. Do not start formal execution while any sealed GPU fails exclusivity.

An internal evidence-chain audit then stopped the first empty rebuild attempt:
the runner recorded launcher/preload exclusivity snapshots, but the analyzer did
not yet authenticate them. The analyzer now rejects missing/mutated snapshots,
non-idle values, context presence, non-A100 identity strings, UUID changes from
initialization to preload, and reserved-cost residue at completion. The frozen
finalizer maps these failures to `FULL_GRID_ABORTED_AUTHENTICATION`. 130 tests
pass; no package files or GPU calls were produced by the interrupted build.

The next sealed candidate passed 130 tests but its complete mock exposed a
fixture mismatch: all three mock sessions were opened, then the canonical
video-major manifest was serialized, so HANGZHOU/WUHAN accumulated minutes of
artificial idle while DALI mock ledgers were written. Formal workers are three
parallel processes. The candidate was rejected without review or GPU use. The
mock now opens, executes, closes, and accounts each already-fixed static shard
when that shard begins; formal concurrency and the eight-second gate are not
changed.

## Second exact-package review: continuous clock and tail visibility

Seal V6 `d2f35022…` reproduced all 1,475 units and 30,932 frame occurrences,
passed 130 tests and a complete mock with 2,964 global-ledger events, and bound
25 review artifacts with zero hash mismatch. Independent review returned
`REVISE_FULL_GRID_PREREGISTRATION` before any formal inference.

Decisive negative evidence:

- `complete_call()` advanced the loaded-worker clock only after a caller-side
  duration had been measured. Lock acquisition and full hash-chain state reads
  between those points were neither in the supplied call duration nor the next
  idle segment. A 0.25-second injected state read yielded about 0.508 uncharged
  two-GPU seconds while status remained `READY`.
- The 12/2/6-frame tails were physically legal but model-visible text still
  called them 10-second units. Tail identity and true duration appeared only in
  provenance, not processor tensors.
- The preregistration did not explicitly bind the unchanged V2
  `REVISE_ORACLE_PROTOCOL` decision/evidence.

Revision in progress: authoritative cost uses a gap-free coordinator-side
residency clock from load reservation through observed process exit; caller
timers are diagnostic. Normal units retain exact base-prompt bytes, while the
three tails deterministically replace the nominal-duration sentence with an
explicit legal truncated-final declaration including true duration, distinct
real frame count, 2-fps grid, and no-padding/no-repeat statement. The V2
decision and evidence manifest are now prospective bindings. Targeted
counterexample tests pass 19/19. Expanded-authorization A100 use remains 0.0
hours, and no formal raw/reference exists.

## Staged execution revision — user-directed resource scheduling

The simultaneous-start package passed its second independent review, but
foreign work repeatedly left only GPU 2 and 6 fully idle. The user explicitly
directed the run to start one complete video shard on that pair and leave the
other two shards marked pending until their frozen pairs authenticate idle.
This is an execution-scheduling revision, not a change to the 1,475-unit grid,
model-relative query, schema, decoder, processor tensors, zero-retry rule, or
complete-only publication boundary. Source now implements fixed staged pairs
DALI `(2,6)`, HANGZHOU `(3,5)`, WUHAN `(1,7)` with DALI first, append-only
pending/authenticated/spawned/exited transitions, and global fail-stop across
all activated and pending workers. Local evidence: 136 tests pass; no model
load, formal call, or formal output has occurred under the staged protocol.

The first staged seal was rejected before approval after a local adversarial
counterexample showed that an initialization-to-spawn GPU-authentication race
could raise without changing `READY` to `STOPPED`. The supervisor now maps
that race to `authentication_mismatch`, maps an initial spawn failure to
`post_load_process_fault`, and fails closed before any model process exists.
Local evidence after the repair: 138 tests pass; the rejected seal produced no
model load, formal call, or formal output. A new exact package, seal, and
independent review are required before launch.

A subsequent pre-build source audit caught stale simultaneous-pair prose in
the completion-audit generator. No package artifact had yet been written. The
generator now loads and validates the sealed worker schedule and derives its
worker IDs, call counts, GPU pairs, activation mode, and initial worker from
that artifact instead of duplicating them as prose constants.

Independent review of staged seal V2 (`2bcac478…`) returned
`REVISE_FULL_GRID_PREREGISTRATION`. A reproduced stale-state interleaving let
W1 and W2 spawn after W1 authentication had durably changed global state to
`STOPPED`. The seal and review bundle are rejected with zero formal calls.
The revised activation path now acquires the coordinator's OS file lock,
re-reads durable state, and linearizes the authenticated ledger transition and
process spawn while holding that lock. A regression injection requires that
only W0 spawns in the reviewer interleaving. Local evidence is 139 tests
passed, with zero formal model loads or calls.

Independent review of staged seal V3 (`c0094a…`) found a distinct active-peer
liveness race: W0 could die during W2 GPU authentication after the loop-top
health poll, leaving durable state temporarily `READY` and allowing W2 to
spawn. Seal V3 is rejected with zero formal calls. The next revision checks
every active peer for nonzero exit both immediately before Popen and again
after Popen while still holding the coordinator lock. A child created in the
remaining Popen interval cannot reserve model-load residency under that lock;
if a peer died, the uncommitted child is killed and receives no SPAWNED ledger
transition. Local evidence is 141 tests passed and zero formal calls.
