# Full-Grid Independent Adversarial Review — Rejected Seal V1

Decision: `REVISE_FULL_GRID_PREREGISTRATION`

Reviewed execution seal SHA-256:
`ffcfb9342221b66e25d347fd021648ac17f6f1b91d89dbfc55d75db73f7759b3`

Reviewed bundle SHA-256:
`f558e6fde12eefd3f104035e76eab7a023a53e55387063ff66c2854504b01d4e`

The reviewer verified the seal, review bundle, artifact/source bindings,
self-hashes, exact 1,475-unit accounting, disjoint 567/561/347 shards, all
30,932 redecoded frame occurrences, 12/2/6-frame tails, processor-only tail
audit, contact sheets, and the 16.097123/19.372468/19.4 A100 GPU-hour
arithmetic. No checkpoint inference, approval, full-grid output, or GPU model
process existed.

Decisive blockers:

1. Abrupt worker death was reproduced without a Python exception hook. The
   coordinator remained `READY`, and another worker could reserve a new call.
   No supervisor, heartbeat, lease, or `SIGCHLD` watchdog enforced global stop.
2. `processed_input_sha256` was checked only for runtime ledger/record
   self-consistency. It was not compared with a preregistered expected tensor
   identity, and the runner/analyzer did not enforce even the three tail hashes.
3. Mode `0600` plus non-overlapping import roots did not prevent a process under
   the same UID from opening a guessed evaluator-only absolute path. No separate
   UID, container, ACL, or cryptographic access boundary was enforced.

Strongest competing explanation: the final analyzer would probably prevent an
incomplete run from becoming a false formal PASS. That does not satisfy the
pre-execution guarantees: follow-on calls could still consume compute after an
abrupt death, processed input identity was unauthenticated, and label secrecy
was not enforced against path guessing.

Required revision: add a fail-closed worker supervisor with abrupt-death fault
injection; freeze and enforce processed tensor identities for every unit; add a
real evaluator/runtime access boundary; rebuild, reseal, and independently
review before requesting compute approval.
