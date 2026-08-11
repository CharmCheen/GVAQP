# Full-Grid Failure Policy

Status: `FROZEN_BEFORE_FULL_GRID_EXECUTION`

The only production entry point is the sealed staged three-process supervisor.
It launches the initial frozen worker only after its pair authenticates idle,
marks the other workers pending without a process or model load, and activates
each pending worker only after its own frozen pair independently authenticates.
It monitors child exit status and operation leases, and terminates all live
peers after any nonzero/abrupt death or global stop.
Workers reject direct launch without the supervisor authority and parent PID.
Before importing the model stack, each worker installs Linux `PDEATHSIG=SIGKILL`
and rechecks the exact parent, so supervisor death cannot orphan GPU workers.
Every call is reserved before frame decode/processor work and remains open
through durable raw-output and ACCEPTED-ledger persistence. Each loaded worker
also holds a prospective eight-second emergency reservation throughout model
residency. An authoritative coordinator-side clock partitions residency
continuously from load reservation through every call/idle boundary and the
supervisor-observed process exit; caller-side timers are diagnostic only. The
two-second idle lease plus polling/termination tail therefore cannot cross the
envelope before detection. The reservation is consumed only after the
supervisor observes process exit. Model tensors and cached allocations
are explicitly released before session close.

The launcher authenticates zero compute contexts, zero utilization, and at
most 16 MiB used memory on the initial pair before initialization. Every
activation repeats the rule before process spawn, and each worker repeats its
exact-pair check immediately before its single model load. A busy pending pair
does not fail or consume compute; it remains explicitly pending. Malformed
telemetry or an identity mismatch is a global authentication failure.

The execution uses one global fail-stop coordinator. Authentication, frame or
processed-input mismatch, an unknown runner/parser, wrong GPU, duplicate or
extra call, retry, fourth load/reload, ledger transition failure, path
collision, cost-shield breach, generation failure, uncertain interruption, or
post-load process fault prevents every worker from issuing another
`INFERENCE_STARTED` event. Already-started calls may terminate and all raw and
ledger evidence is preserved.

The original approval permits exactly three uninterrupted model loads and no
post-load restart. A continuation is a new experiment: authenticated completed
records may be proposed for reuse, but any call with a durable start and no
terminal record remains uncertain and cannot be retried without explicit new
retry authority.

Any missing, failed, uncertain, extra, retried, unauthenticated, or cost-invalid
run is incomplete. It produces `INSUFFICIENT_EVIDENCE` or the higher-priority
frozen abort decision, no formal unit-label table, no formal K3 relation, and no
downstream access. Formal artifacts live in a versioned evaluator-only release;
only the final atomic `FORMAL_REFERENCE_RELEASE.json` pointer makes the release
authoritative.
