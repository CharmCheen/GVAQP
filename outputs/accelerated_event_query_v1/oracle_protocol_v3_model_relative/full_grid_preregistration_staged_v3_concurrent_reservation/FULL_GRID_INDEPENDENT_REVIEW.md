# Independent Adversarial Review — Concurrent-Reservation V3 Candidate

Decision: `REVISE_FULL_GRID_PREREGISTRATION`

- Source commit: `19216a5a1d8fef6d75f43acf7c315c7fd07eebd7`
- Execution seal SHA-256: `b6e1cd2892762c4372c678abd3c832bb5bcdfc4690ace61e4fff26d2aa079a02`
- Review bundle SHA-256: `06d9b83c0cf8149aa8e4f19974993d8da82ddcb05cbdd205cb97bfa2fd4a0fac`

## Authenticated evidence

The immediate failed execution authenticates exactly 476 reserved and started
calls, 473 completed and accepted calls, three model loads, and zero formal
publication. All 473 raw records have valid self-hashes, exactly match the
global completed-call set, and independently strict-parse as `ok`.

The three terminal in-flight calls are exactly `DALI_u0468`,
`HANGZHOU_u0003`, and `WUHAN_u0002`; none has a raw output. Durable intent,
global state, and global ledger agree on
`call:DALI_u0468:elapsed=35.048812:limit=35.000000`.

All 487 immediate nested bindings and all 147 deeper first-failure bindings
currently match their frozen sizes and SHA-256 hashes. The two failed runs'
conservative usage recomputes to `6.697182287098888` A100 GPU-hours, and adding
the proposed fresh 54.0-hour envelope gives `60.69718228709889 < 64`.

The seven designated concurrent observations are present in the authenticated
ledgers and raw records. Their frozen token reconstruction and runtime fields
recompute exactly. The maximum completed concurrent scaling is
`58.42139303322995` inference seconds at the 192-token cap.

The unit, frame, processed-input, worker-schedule, tail-processor, and tail-unit
artifacts are byte-identical to the preceding reviewed package. They retain
1,475 unique units, 30,932 frame occurrences, disjoint 567/561/347 shards,
three fixed GPU pairs, and legal 12/2/6-frame tails.

All current source bindings validate. The fresh execution root, approval
artifact, model process, raw outputs, and formal reference are absent. The
CPU-only suite passes 153 tests with one non-failing fork deprecation warning.

## Blocking findings

### 1. The frozen concurrent floor omits direct incomplete-call evidence

`FULL_GRID_CALL_RESERVATION_DERIVATION.json` reports a concurrent non-inference
maximum of `2.6205432303249836` seconds because the builder considers only the
seven completed concurrent records.

The hash-chained ledgers directly show larger preprocessing lower bounds in the
unfinished concurrent calls:

- `DALI_u0468`: `CALL_RESERVED -> INFERENCE_STARTED = 3.567687389 s`
- `WUHAN_u0002`: `CALL_RESERVED -> INFERENCE_STARTED = 3.486220210 s`

Combining the frozen scaled inference value with the larger observed
preprocessing lower bound and the frozen concurrent post-persistence maximum
gives `62.08846018493341 s`, not `61.141316026258394 s`.

### 2. Cost and wall-clock estimates ignore the concurrency regime

The candidate retains the old hard-coded 19.6077118-second mean, 16.097123
A100 GPU-hour estimate, and 3.093181-hour wall-clock estimate. The newly bound
evidence instead has a 473-call accounted mean of 19.697589 seconds and a
seven-call concurrent mean of 22.860418 seconds. The estimate must model the
staged one-, two-, and three-worker phases and state its uncertainty.

### 3. Launch validation does not recurse through both failed histories

The package validator authenticates the immediate evidence file but does not
traverse the 11 control and 136 raw bindings inside the earlier failure record.
Those deeper bindings are intact now, but later mutation would not fail launch.

### 4. The stated all-operations hard bound omits repeated idle consumption

The 53.327222 A100 GPU-hour calculation includes calls, loads, and three
simultaneous emergency reservations, but not the cumulative valid idle gaps
between calls. It is a reservation subtotal rather than a strict
all-operations upper bound.

## Required revision

1. Recompute the concurrent floor from completed and incomplete ledger evidence.
2. Reassess the lease and safety margin.
3. Recompute cost and wall-clock estimates under explicit concurrency assumptions.
4. Correct or qualify the all-operations bound.
5. Recursively authenticate both failed histories and add mutation tests.
6. Regenerate dependent artifacts, rerun tests and dry-run, create a new seal,
   and obtain a new independent review.

No GPU inference was started and no package or source file was modified during
this review.
