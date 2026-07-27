# V2 Application-Boundary Research State

## Current objective

Complete the ordinary-software v2 process/API boundary without making a
capability-security claim or selecting a scanning method.

## Established findings

- Evaluator and policy communicate through a separately spawned child process
  using JSONL stdin/stdout.
- The public state is constructed with an explicit allowlist; private
  reference state, future costs, output paths, and internal identifiers are
  excluded.
- Public video, unit, and candidate identifiers are episode-local opaque IDs.
- Replay and Physical paths share the policy-client protocol and record IPC,
  policy-decision, SCAN-only, and end-to-end scheduler timing fields.
- Deadline admission subtracts validation overhead once and completes every
  admitted microchunk.

## Evidence

`PYTHONPATH=src pytest -q tests/partial_scan_v2` completed with `30 passed`.
The suite includes a real JSONL child-process policy decision and constructed
ReplayEnvironment and PhysicalEnvironment paths; it is not a full benchmark
rerun or a deployment-capability audit.

## Active uncertainty

The policy process has not been shown to lack benchmark mounts, hidden outputs,
ambient environment variables, network access, or shared credentials. The
application process boundary alone cannot establish those properties.

## Decision

```text
APPLICATION_PROCESS_BOUNDARY = ESTABLISHED
PUBLIC_API_DATA_MINIMIZATION = PASS
CAPABILITY_SECURITY = NOT_YET_ESTABLISHED
METHOD_SELECTION = PROHIBITED
```

## Next highest-value action

The repository-only deployment review found no production manifest and showed
that the development launcher inherits the evaluator identity. Obtain the
actual production deployment definition, then review its mounts, identities,
filtered environment, network policy, and allowed IPC channels. Do not rank
policies until that review passes and a multi-video formal benchmark is frozen.
