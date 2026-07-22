# Toy simulator invariants and current audit state

Required invariants remain: latent/visible separation; deterministic seed
mapping; exact-support deadline admission; productive SCAN reserve; atomic
CONFIRM; finite proper termination; no repeated region or witness action;
trace-recomputable D1 utility; symmetric full-horizon continuation; and no
held-out access during development smoke.

Static compilation and a small pi0 state-machine probe passed. These are
engineering observations, not a scientific smoke result. A valid development
smoke was not run because the episode generator and non-clairvoyant M1 kernel
are not uniquely determined by the frozen protocol. No method metrics or
rankings were generated.

Rejection trigger: any implementation that chooses an RNG insertion point,
uses future witnesses for grouping, assigns ledger-order random costs across
different policy trajectories, or evaluates M1 on the realized latent episode
must remain unfrozen.

