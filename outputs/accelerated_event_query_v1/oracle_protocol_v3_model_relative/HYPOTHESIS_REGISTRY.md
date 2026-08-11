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

## H7 — The three shorter final units are legal processor inputs

- Importance: dropping, padding, repeating, or textually redefining the tails
  would change the 1,475-unit reference identity.
- Minimal experiment: decode exact 12/2/6 source-anchored frames and run the
  real frozen AutoProcessor without loading checkpoint weights or generating.
- Expected result: all three tensorize with `do_sample_frames=false`; exact
  decoded targets/hashes remain the transport authority.
- Failure condition: processor rejection or a required sampling/prompt change.
- Competing explanation: processor-internal temporal patch mechanics may differ
  from source padding but still accept the legal supplied frames.
- Impact: failure yields `REVISE_TRUNCATED_UNIT_PROTOCOL` and stops sealing.
- Status: `FIRST_DECODE_FALSIFIED_NAIVE_CFR_INDEX_BINDING`; DALI container
  duration exceeds video-stream support. Revised prediction: its 5.5-second
  target resolves to unique final frame 169,961 with the ideal 169,965 request
  retained; any repeated-frame resolution remains forbidden.

## H8 — Exact manifests form a complete disjoint 1,475-call identity

- Importance: one duplicate, omission, or traversal-order dependency invalidates
  the expensive reference.
- Minimal experiment: canonical grid traversal, self-hashed unit/frame rows,
  independent worker union validation, and complete re-decode.
- Failure condition: any count/hash/index/timestamp/video/worker mismatch.
- Competing explanation: shared endpoint frames are legitimate occurrences,
  not duplicate unit attempts.
- Impact: failure revises input binding before any approval request.
- Status: `VALIDATORS_TESTED_AWAITING_REAL_MANIFEST`.

## H9 — Global fail-stop preserves interpretability under worker failure

- Importance: best-effort continuation could mix sessions, loads, retries, or
  partial reference state.
- Minimal experiment: no-inference injections for duplicate, wrong GPU, reload,
  cost, authentication, incomplete transition, and resume.
- Expected result: a terminal global stop prevents all later call reservations.
- Failure condition: any worker can start after a hard trigger.
- Impact: failure revises the execution coordinator.
- Status: `SUPPORTED_BY_UNIT_TESTS`; full 1,475-record mock remains pending.

## H10 — Preregistered coverage gates prevent post-hoc oracle adequacy claims

- Importance: unknown/invalid prevalence is unobserved in the targeted preflight.
- Frozen prediction: formal release requires global and each-video determined
  coverage >=99% and exactly zero parse failures.
- Competing explanation: the threshold may prove conservative, but changing it
  after labels would be scientifically invalid.
- Impact: a lower observed coverage yields the frozen insufficient/protocol
  decision and no formal reference.
- Status: `FROZEN_IN_IMPLEMENTATION_BEFORE_OUTPUTS`.

## H11 — Evaluator labels cannot leak into public controller state

- Importance: exhaustive labels would trivialize later SCAN/VERIFY decisions.
- Minimal experiment: evaluator capability rejection, signed causal results,
  forged/future rejection, hidden-label permutation, and path isolation.
- Failure condition: controller lookup or next-state change from unrevealed
  label permutation.
- Impact: revise the interface; do not run replay.
- Status: `SUPPORTED_BY_INTERFACE_TESTS`; no replay/controller claim is made.

## H12 — Partial files cannot become a formal operational reference

- Importance: a crash between three output writes could expose an incomplete
  table or relation.
- Minimal experiment: versioned evaluator-only staging and one final atomic
  release pointer; mocks and incomplete runs must produce no pointer.
- Failure condition: downstream-addressable formal release without all gates.
- Impact: revise finalizer/publication protocol.
- Status: `SUPPORTED_BY_ATOMIC_PUBLICATION_TEST`; end-to-end mock pending.

## H13 — A sealed supervisor closes abrupt-death global fail-stop

- Prediction: if any worker exits nonzero or by signal, the supervisor writes a
  terminal global stop and terminates every live peer before another call can
  be reserved; load/call lease expiry has the same effect.
- Falsification: reproduce W0 death with an in-flight call and successfully
  reserve W1 afterward, or directly launch an inference worker without the
  supervisor parent authority.
- Competing explanation: final incomplete-run analysis could prevent a false
  PASS, but would not prevent unauthorized follow-on compute.
- Status: `SUPPORTED_BY_NEW_FAULT_TEST_AWAITING_PACKAGE_DRY_RUN`.

## H14 — Every runtime processor tensor matches a preregistered identity

- Prediction: all 1,475 exact frame/prompt inputs tensorize twice to the same
  frozen SHA-256; any runtime difference triggers
  `processed_input_identity_mismatch` before reservation/generation.
- Falsification: arbitrary record/ledger tensor hashes pass the analyzer, or a
  second processor-only traversal differs.
- Competing explanation: source/code/frame hashes constrain preprocessing but
  do not prove installed dependency or tensor-byte identity.
- Status: `IMPLEMENTED_AWAITING_1475_UNIT_PHYSICAL_PROCESSOR_FREEZE`.

## H15 — Runtime cannot path-guess evaluator-only full-grid labels

- Prediction: formal labels are root-owned under `0700/0600`; later runtime is
  UID/GID 65534 with zero effective capabilities and no evaluator mount, so an
  absolute guessed path is absent or raises `PermissionError`.
- Falsification: the frozen runtime identity opens the sentinel or shares the
  evaluator UID/capabilities/mount.
- Competing explanation: Python capabilities and import roots are useful API
  hygiene but are not security boundaries under the same UID.
- Status: `SUPPORTED_BY_REAL_SETUID_TEST_AWAITING_INDEPENDENT_REVIEW`.

## H16 — Supervisor authority survives supervisor death as a kernel-enforced boundary

- Prediction: every formal worker receives `SIGKILL` from Linux if its exact
  sealed supervisor dies, including workers launched in independent sessions;
  reparenting cannot leave a GPU inference process alive.
- Minimal falsification: launch a worker child with the production death-signal
  installer, let its parent exit normally, and observe whether the child PID
  remains in `/proc` beyond five seconds.
- Competing explanation: supervisor polling closes ordinary worker failure but
  cannot close failure of the supervisor itself.
- Impact: any surviving child rejects the package before model loading.
- Status: `SUPPORTED_BY_REAL_SUBPROCESS_TEST_AWAITING_PACKAGE_REVIEW`.

## H17 — No loaded-model GPU-residency interval is unleased or unaccounted

- Prediction: model-load, decode, preprocessing, inference, parsing, output
  persistence, ledger writes, inter-call gaps, and final shutdown are covered
  by either an open operation lease or a maximum two-second loaded-idle lease;
  all elapsed residency contributes two GPU-seconds per wall second.
- Minimal falsification: freeze a loaded worker before decode or after call
  completion and test whether peers continue past the idle limit or whether the
  cost clock omits the interval.
- Competing explanation: per-operation reservations alone bound inference but
  not arbitrary Python/I/O stalls around it.
- Impact: any unbounded or unaccounted interval rejects the package and the
  19.4 A100 GPU-hour claim.
- Status: `SUPPORTED_BY_UNIT_AND_FAULT_TESTS_AWAITING_COMPLETE_DRY_RUN`.
  An internal adversarial pass falsified the first revision's immediate
  post-session exclusion. The repaired prediction additionally requires model
  and tensor release before close and keeps a closed-but-live PID under the
  same lease until exit; the new fault test passes.

## H18 — A reusable emergency reservation prevents retrospective envelope crossing

- Prediction: each loaded worker holds eight seconds of two-GPU emergency
  reservation continuously from load start to observed exit; every idle gap
  consumes the prior reservation, and the next call cannot start unless both a
  refreshed emergency reserve and its complete call reserve fit under 19.4.
- Falsification: construct an elapsed gap whose cost leaves insufficient room
  for the next call and observe any new attempt, or observe actual physical cost
  above the envelope before STOPPED.
- Competing explanation: merely recording idle time at the next call detects
  but does not prevent an overrun when no prospective reserve exists.
- Status: `SUPPORTED_BY_PROSPECTIVE_RESERVATION_TEST_AWAITING_PACKAGE_REVIEW`.

## H19 — Formal execution rejects a changed or contended GPU profile

- Prediction: before coordinator initialization and again before each model
  load, all sealed GPUs have zero compute contexts, zero utilization, <=16 MiB
  used memory, and exact index/name/UUID identity.
- Falsification: a busy, memory-occupied, or foreign-context GPU reaches
  `start_model_load` or produces an initialization audit marked exclusive.
- Competing explanation: UUID identity alone proves hardware identity but not
  runtime comparability or lack of contention.
- Status: `SUPPORTED_BY_MOCKS_AND_REAL_BUSY_GPU_REJECTION_AWAITING_IDLE_RUN`.
  The first implementation was runner-enforced but not analyzer-grounded; that
  evidence-chain variant was rejected internally. The current prediction also
  requires initialization/preload UUID continuity and independent analyzer
  validation of every raw snapshot.

## H20 — Coordinator-side partitioning closes every loaded-residency clock gap

- Prediction: authoritative cost for model load and each call is elapsed time
  between consecutive coordinator timestamps, taken after lock/state
  validation; coordinator tail work after one timestamp is charged in the next
  call/idle/session segment. Caller timers cannot reduce charged residency.
- Falsification: inject delay anywhere after reservation and before the next
  timestamp and observe a smaller increase in `actual_gpu_seconds` than two
  GPU-seconds per wall second, or status `READY` after physical cost exceeds the
  envelope.
- Competing explanation: operation timers plus idle timers appear exhaustive
  but can leave seams at lock/hash-chain/persistence boundaries.
- Status: `REVISED_AFTER_REJECTED_V6_COUNTEREXAMPLE; TARGETED_TEST_SUPPORTED`.

## H21 — Tail legality is part of the actual model input, not provenance only

- Prediction: all normal units retain the exact frozen base-prompt bytes; each
  12/2/6-frame tail instead has deterministic model-visible text that explicitly
  states legal truncated-final identity, true source duration, distinct real
  frame count, frozen 2-fps grid, and no padding/repetition.
- Falsification: the processor tensor for a tail equals the old nominal
  10-second tensor, the nominal instruction remains, or the declared text/hash
  is absent from the processed-input and tail audits.
- Competing explanation: frame count/fps make shortness inferable, but do not
  establish legality and conflict with an explicit 10-second assertion.
- Status: `IMPLEMENTED_IN_SOURCE; FULL_REPROCESS_AND_REVIEW_REQUIRED`.

## H22 — V3 preserves rather than rewrites V2 historical evidence

- Prediction: package construction fails unless both the write-once V2 targeted
  decision and evidence manifest still report 32 records and
  `REVISE_ORACLE_PROTOCOL`; both exact files are seal bindings.
- Falsification: V3 can build while either V2 artifact changes or preregistration
  implies that model-relative V3 repairs/supersedes V2 findings.
- Status: `IMPLEMENTED_IN_SOURCE; PACKAGE_BINDING_REQUIRED`.

## H23 — Staged activation preserves oracle identity and fail-stop semantics

- Prediction: starting the exact DALI shard on idle GPU `(2,6)` while the
  other fixed shards remain process-free and explicitly pending yields the
  same authenticated unit identities as simultaneous activation; no pending
  worker can load a model or issue a call before pair authentication.
- Falsification: any pending worker produces a process/load/call transition,
  any busy pair is activated, an activated-worker failure permits a later
  activation, or partial outputs become a formal reference.
- Competing explanation: simultaneous startup is operationally simpler, but
  is not required for model-relative label validity when every shard has fixed
  inputs/pair identity and the complete-run gate remains global.
- Counterexample and revision: staged seal V1 left global state `READY` when
  the initial pair changed between initialization authentication and the
  pre-spawn authentication. The exact seal is rejected. The repaired path
  atomically fails closed as `authentication_mismatch`; a separate initial
  spawn-failure test fails closed as `post_load_process_fault`.
- Second counterexample: staged seal V2 authenticated pending W1 from a stale
  loop-top `READY` snapshot; if authentication concurrently persisted
  `STOPPED`, W1 and W2 could still be spawned before the next loop.
- Second revision: every authenticated activation now reacquires the exact
  global coordinator lock, rechecks durable `READY`, and linearizes the
  activation-ledger transition and process creation before releasing the lock.
- Third counterexample: staged seal V3 allowed W2 to spawn if W0 died during
  W2 authentication after the loop-top process-health poll but before the
  locked global-state recheck; the state remained `READY` until the next poll.
- Third revision: locked activation checks active-peer return codes before and
  after Popen. A post-Popen peer failure kills the uncommitted child before
  lock release/model-load reservation and omits the SPAWNED ledger event.
- Pre-build falsification: zero exit without an authoritative session-close
  transition is not success; malformed pre-existing activation ledgers must
  fail closed; and lock serialization alone does not prioritize a fail-stop
  already contending behind a candidate model-load reservation.
- Fourth revision: only supervisor-adjudicated completed peers are excluded;
  every other terminal code blocks activation. A durable write-once stop
  intent precedes lock contention and is checked by every coordinator
  admission. Activation-ledger creation is inside the protected fail-stop
  block and any pre-existing path is an output collision.
- Exact-seal falsification: the first intent blocked work but did not govern
  state/ledger decision identity when a later generic caller committed STOP.
- Fifth revision: `trigger_stop`, emergency stop, coordinator admission, and
  every internal locked stop resolve the authoritative trigger/detail from
  the validated first write-once intent before persisting state or ledger.
- Status: `REVISED_AFTER_FIRST_CAUSE_COUNTEREXAMPLE; 150_LOCAL_TESTS_PASS; NEW_EXACT_PACKAGE_REVIEW_REQUIRED`.

## H24 — The original per-call hard reservation represented the full generation tail

- Prediction: every legal frozen call, including a 192-token response, finishes
  within `23.579961` wall seconds from reservation through durable acceptance.
- Observation: falsified on the 137th formal attempt. `DALI_u0136` remained in
  generation at `23.754265` seconds and triggered the preregistered fail-stop.
  The preceding 136 calls had already reached `23.304528` seconds.
- Competing explanation: the unit hung. This is not supported by the available
  evidence: generation had run for 22.129 seconds versus a completed maximum of
  21.621 seconds, and response-token count explains most inference-time variance
  (R² 0.942). The failed call was killed before a terminal model result could
  distinguish a long response from a hang, so that residual uncertainty remains.
- Status: `REJECTED_BY_FORMAL_EXECUTION`.

## H25 — A token-cap-aware hard reservation can retain fail-closed cost safety

- Prediction: a preregistered call bound derived from the frozen 192-token cap,
  observed token/runtime slope, decode/persistence overhead, and explicit safety
  margin admits ordinary long-tail calls while the sum of all 1,475 hard call
  reservations, three loads, and emergency tails remains below a newly sealed
  full-grid envelope and the overall 64 A100-hour authorization.
- Falsification: the derived hard envelope does not fit the authorization, a
  no-inference fault test permits physical cost to cross it, independent review
  finds post-hoc outcome adaptation, or a fresh call exceeds the new limit.
- Competing explanation: a separate high watchdog with only actual aggregate
  accounting would consume less prospective budget, but loses the existing
  deterministic all-calls worst-case proof. Prefer the smallest revision that
  preserves that proof unless review shows it is unnecessarily coupled.
- Status: `SUPPORTED_BY_CALIBRATION_AND_153_LOCAL_TESTS; EXACT_PACKAGE_REVIEW_REQUIRED`.
  The 35.0-second bound exceeds a 99% Bonferroni family-wise total-call upper
  prediction of 32.263114 seconds by 2.736886 seconds. Its all-operations hard
  cost is 28.743889 A100 GPU-hours; adding the prior failure's conservative
  1.444388-hour upper bound remains below the user's 64-hour authorization.

## H26 — Terminal model unload requires a distinct bounded lease

- Prediction: keeping the ordinary loaded-idle lease at 2 seconds while using
  an 8-second lease only after durable `WORKER_SESSION_COMPLETED` admits the
  observed 2.073427-second V5 unload, preserves fail-stop for next-call and
  session-close stalls, and rejects a process-exit tail above 8 seconds both
  transactionally and in the supervisor.
- Observation: V5 completed the entire WUHAN shard before stopping solely in
  the session-close/process-exit window. Its 1,084 complete calls had maximum
  accounted time 27.805666 seconds; no call approached the prior 66-second
  lease. All preserved outputs strict-parse and none were formally published.
- Competing explanation: the terminal delay could be an abnormal hang rather
  than unload. The observed 2.073427 seconds is only 73 ms over the ordinary
  lease and occurred after full shard/session completion; the 8-second
  emergency reservation already prospectively covered this residency. A
  future tail above 8 seconds still falsifies V6 and globally stops.
- Status: `IMPLEMENTED_IN_SOURCE; 37 TARGETED TESTS PASS; EXACT V6 PACKAGE_AND_INDEPENDENT_REVIEW_REQUIRED`.

## H27 — Correct mechanics are insufficient when frozen evidence semantics are inconsistent

- Prediction: an independently reviewable execution package must describe the
  immediate failure hierarchy accurately, report a statistical upper no lower
  than its corresponding point estimate, and keep exact full-grid approval
  distinct from separately authorized downstream work.
- Observation: V6 mechanics passed all direct checks, but independent review
  found all three frozen inconsistencies and returned
  `REVISE_FULL_GRID_PREREGISTRATION` before inference.
- Competing explanation: these are cosmetic defects because they do not change
  tensors or labels. Rejected: each changes how cost risk or authorization
  scope would be interpreted after sealing.
- Status: `SUPPORTED; V7_CORRECTION_AND_NEW_REVIEW_REQUIRED`.
