# Full-Grid Independent Adversarial Review — Rejected Seal V3

Decision: `REVISE_FULL_GRID_PREREGISTRATION`

Execution seal SHA-256:
`f84a18616a0f1d5e8e87aa394cb3e32e56de80b6ac04af6136bdc44d3ff50dae`

Review bundle SHA-256:
`8bcc7f3214c6650fd3d704c39b38b3e33ef8236ec654c5fa486ee9ccd1189c9c`

All self-hashes, 24 bundle artifacts, 26 frozen artifacts, and 11 source
bindings matched. Exact accounting, 12/2/6 tails, 30,932 frames, static
567/561/347 shards, cost arithmetic, coverage/K3 thresholds, and the
no-output/no-inference boundary passed.

The three prior blockers were materially closed: worker `-9` stopped the
coordinator and peers; CALL lease expiry stopped on cost; mutated processed
tensor identity was rejected against all-unit frozen expectations; UID/GID
65534 could not open a guessed root-owned evaluator path; partial missing
supervisor evidence caused runtime abort and no publication.

Two new decisive blockers:

1. Supervisor death is unhandled. `start_new_session=True` workers authenticate
   `getppid()` only once and have no Linux parent-death signal or recurring
   parent-liveness gate. A child survived reparented to PID 1 after its parent
   exited.
2. Decode/processor work occurs after `MODEL_LOAD_COMPLETED` but before
   `reserve_call`. During a reproduced 24-hour synthetic stall,
   `_open_operations()` was empty, `_lease_violation()` was `None`, and the
   coordinator remained `READY` with zero reservation. Two loaded A100s could
   therefore remain outside the cost shield indefinitely.

Required revision: install and test fail-closed Linux `PDEATHSIG` before any
worker model import; reserve the call before decode/processing; and add a short
loaded-worker idle lease that covers every gap between model-load completion,
call reservations, call completions, and process exit. Rebuild, reseal, dry-run,
and independently review before execution.
