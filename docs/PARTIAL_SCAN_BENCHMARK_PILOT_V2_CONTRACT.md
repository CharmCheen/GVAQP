# PARTIAL_SCAN_BENCHMARK_PILOT_V2 Contract

## Scope

```text
BENCHMARK = PARTIAL_SCAN_BENCHMARK_PILOT_V2
PARENT_BENCHMARK = PARTIAL_SCAN_BENCHMARK_PILOT_V1
PARENT_STATUS = BLOCKED_POLICY_INFORMATION_ISOLATION
REPAIR_SCOPE = APPLICATION_PROTOCOL_AND_RUNTIME_ACCOUNTING
V1_IMMUTABLE_EVIDENCE = UNCHANGED
PILOT_METHOD_SELECTION = PROHIBITED
RUNTIME_ISOLATION_ATTESTATION = EXTERNAL_PREREQUISITE
```

V2 inherits hash-identified V1 videos, timelines, unit-local SCAN outputs,
determinism evidence, pseudo-reference events, visible-subset replay,
candidate-event mapping, partition-phase ceilings, and initial physical-cost
calibration. V1 is never modified.

The reference remains a partially complete full-context Oracle pseudo-reference.
Method ranking remains prohibited.

## Runtime-isolation prerequisite

This contract specifies application IPC and accounting only. Strong runtime
isolation is an external execution-environment prerequisite and is not tested,
attested, or inferred by this benchmark. Application protocol separation does
not claim malicious-policy isolation.

## Public protocol

Communication is line-delimited JSON over stdin/stdout. There is no shared
directory, database, socket, or inherited evaluator handle.

The production protocol supports:

1. `initialize` / `initialized`;
2. `choose_action` / action response;
3. `terminate`.

Policy output for a decision has exactly:

```json
{"step_id":17,"unit_id":"u_<opaque>"}
```

Action responses have exactly `step_id, unit_id`; no extra fields are allowed.
`step_id` must equal the current request and `unit_id` must be currently
available (known and unscanned). Invalid schemas and unknown actions are
rejected with a frozen generic public error code. Tracebacks remain evaluator
private.

## Explicit public-state allowlist

```text
PUBLIC_STATE_SERIALIZATION = EXPLICIT_ALLOWLIST_ONLY
INTERNAL_OBJECT_SERIALIZATION = PROHIBITED
```

The public state contains only:

- step ID;
- public protocol version;
- scanned opaque unit IDs;
- current opaque unit ID;
- remaining visible budget;
- past observed action costs;
- geometric coverage;
- opaque candidate IDs and the last public result class.

Reference events, exposure state, output paths, future costs, evaluator
objects, filesystem handles, and internal identifiers are evaluator-only.
Schema validation is performed on every initialization, request, and response.

## Identifier contract

Run IDs are random. Video, unit, and candidate identifiers are independent
run-scoped HMAC values:

```text
PUBLIC_VIDEO_ID = OPAQUE_RUN_SCOPED_HMAC
PUBLIC_UNIT_ID = OPAQUE_RUN_SCOPED_HMAC
PUBLIC_CANDIDATE_ID = OPAQUE_RUN_SCOPED_HMAC
REFERENCE_ID_DERIVABILITY = PROHIBITED
ID_MAPPING_PERSISTENCE = EVALUATOR_MEMORY_ONLY
```

The HMAC secret is never serialized or written to a trace.

## Environment semantics

Replay and Physical environments use the same `IsolatedPolicyClient`.
Only the evaluator can validate actions, reveal frozen or newly executed unit
outputs, run visible-subset candidate replay, and update hidden exposure.

Physical runs retain the V1 controlled-warm lifecycle:

- fresh evaluator and isolated policy processes per run;
- one decoder and one model instance per run;
- tracker reset per completed unit action;
- complete source-byte read and hash before model/decoder setup;
- no started scan action is aborted.

## V2 timing fields

Each action records:

```text
policy_request_serialize_sec
ipc_send_sec
policy_decision_sec
ipc_receive_sec
policy_response_validate_sec
environment_action_validate_sec
seek_time_sec
decode_time_sec
model_time_sec
tracker_time_sec
candidate_time_sec
visible_subset_replay_time_sec
total_scan_action_time_sec
total_scheduler_step_time_sec
```

`total_scan_action_time_sec` is the SCAN-only cost.
`total_scheduler_step_time_sec` is end-to-end evaluator wall-clock from public
state construction through completed visible-subset replay.

## Deadline gate and interrupted-run recovery

```text
SCHEDULER_OVERHEAD_INCLUDED_IN_DEADLINE = true
remaining_budget_at_validation_sec =
  remaining_budget_before_step_sec
  - policy_request_serialize_sec - IPC - policy_decision_sec
  - policy_response_validation_sec - environment_action_validation_sec
ACTION_START = estimated_post_validation_completion_sec
  <= remaining_budget_at_validation_sec
```

Validation overhead is used for admission only and is charged once through the
actual scheduler-step ledger. A started microchunk completes; an inadmissible
action is rejected before it starts.

Replay and Physical destinations may be removed only when they are strict
children of their respective V2 run root, have no `run_summary.json`, and
contain `.partial_scan_incomplete_run`. Each removal is recorded in
`outputs/partial_scan_pilot_v2/repair_log.json`. The marker is removed before
the atomic write of `run_summary.json`.

## Application-gate verification

The application gate verifies:

- a real evaluator-to-policy JSONL child-process decision;
- representative Replay and Physical paths using the shared client interface;
- public-schema allowlist and opaque-ID invariants;
- deadline admission/accounting and interrupted-run recovery;
- IPC, policy-decision, SCAN-only, and scheduler end-to-end trace fields.

It does **not** run chroot, sentinel, UID, `/proc`, filesystem-permission, or
other capability-security checks. Those checks belong exclusively to the later
independent deployment-boundary review.

## Acceptance

Application results report the following boundary-limited states:

```text
APPLICATION_PROCESS_BOUNDARY = ESTABLISHED | NOT_ESTABLISHED
PUBLIC_API_DATA_MINIMIZATION = PASS | FAIL
CAPABILITY_SECURITY = NOT_YET_ESTABLISHED
```

`CAPABILITY_SECURITY` may be set to `PASS` only by the separate deployment
review. Until then formal method ranking is blocked.

Even after all engineering gates pass:

```text
PILOT_METHOD_SELECTION = PROHIBITED
VALID_EVENT_CLAIM =
DISTINCT_EVENT_EXPOSURE_RELATIVE_TO_FROZEN_PSEUDO_REFERENCE
VALID_WALLCLOCK_CLAIM =
CONTROLLED_WARM_TEST_ENVIRONMENT_ONLY
```
