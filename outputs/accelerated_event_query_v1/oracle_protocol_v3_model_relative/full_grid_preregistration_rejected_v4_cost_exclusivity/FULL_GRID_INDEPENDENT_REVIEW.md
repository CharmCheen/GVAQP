# Full-Grid Independent Adversarial Review — Rejected Seal V4

Decision: `REVISE_FULL_GRID_PREREGISTRATION`

Execution seal SHA-256:
`48c71239bee56b89aa34dfdd0d22e8759e332ba892527135d1b691449698bb24`

Review bundle SHA-256:
`50bfcb9c928d5a4a62b914d38343f299eb09713cbbc89f70f37f738104799f50`

Commit: `d0e1894f5ade3aa2975721bd9290b203db4169b0`

All self-hashes, 25 bundle artifacts, 26 seal artifacts, and 11 source
bindings matched. Real PDEATHSIG, abrupt-death, loaded-idle and session-tail
tests passed. Model/tensor cleanup precedes session close. Exact 1,475-unit,
30,932-frame, 567/561/347-shard, 12/2/6-tail, tensor-identity, zero-retry,
partial-publication, coverage/K3, label-isolation, analyzer and finalizer
checks passed. No approval or full-grid execution exists.

Two decisive blockers remain:

1. `19.375801544431596` A100 GPU-hours reserves all 1,475 call maxima, three
   load maxima, and three two-second exit tails, but nothing for the 1,475
   loaded-worker gaps after `CALL_COMPLETED` while raw output and ledgers are
   persisted. The envelope leaves only 87.114 GPU-seconds total, or 29.53 ms
   average wall time per call gap, although each gap may legally last two
   seconds. Charging these gaps only at the next call can discover the
   violation after the physical envelope was crossed.
2. During review, every sealed worker GPU was 94–99% utilized by foreign
   compute contexts. Initialization authenticates GPU identity but not
   exclusivity or idleness, so it would accept a changed execution profile
   that invalidates the runtime and cost assumptions.

Required revision: keep each call reservation open through durable raw output
and accepted-ledger persistence; maintain a prospective loaded-idle reservation
so remaining-envelope insufficiency stops before more work; and authenticate
GPU idleness/no foreign compute contexts before initialization and again before
each worker model load.
