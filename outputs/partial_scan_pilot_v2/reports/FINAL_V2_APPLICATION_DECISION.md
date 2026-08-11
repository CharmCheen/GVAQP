# PARTIAL_SCAN_BENCHMARK_PILOT_V2 Application Decision

This decision covers ordinary application engineering only. V1 immutable
evidence is unchanged. No pilot-method selection has been performed.

Protocol/schema tests, a real evaluator-to-policy JSONL child-process round
trip, constructed Replay and Physical representative paths, deadline/rejection
tests, recovery tests, action-trace schema review, and Replay/Physical
interface review completed successfully (30 tests passed). The representative
paths use manually constructed messages and synthetic in-memory units only; no
hidden benchmark asset or deployment-boundary validation was performed.

PARENT_ASSET_HASH_VALIDITY = UNCHANGED

ACTION_PROTOCOL_CONSISTENCY = PASS
PUBLIC_STATE_ALLOWLIST = PASS
PUBLIC_ERROR_REDACTION = PASS
INCOMPLETE_RUN_RECOVERY = PASS
BUDGET_GATE_CORRECTNESS = PASS
REPLAY_PHYSICAL_INTERFACE_PARITY = PASS
ACTION_TRACE_COMPLETENESS = PASS

APPLICATION_PROCESS_BOUNDARY = ESTABLISHED
PUBLIC_API_DATA_MINIMIZATION = PASS
CAPABILITY_SECURITY = NOT_YET_ESTABLISHED

APPLICATION_PROTOCOL_SEPARATION = PASS
EXTERNAL_RUNTIME_ISOLATION_ATTESTATION = MISSING
FORMAL_METHOD_RANKING_ELIGIBILITY = BLOCKED

PILOT_METHOD_SELECTION = PROHIBITED
NEXT_ALLOWED_STAGE = INDEPENDENT_DEPLOYMENT_BOUNDARY_REVIEW
