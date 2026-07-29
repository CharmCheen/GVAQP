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
