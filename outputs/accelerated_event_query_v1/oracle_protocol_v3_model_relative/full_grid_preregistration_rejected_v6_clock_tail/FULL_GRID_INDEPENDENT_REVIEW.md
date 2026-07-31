# Full-Grid Independent Adversarial Review

- Reviewed at: `2026-07-29T21:23:27Z`
- Source commit: `996430fd57760e4c249862d6c2f62943e2d9268f`
- Execution seal SHA-256: `d2f350221b832a0e0f607416f4a155237f194aec8a20ba0b9a6aa5d22eaa6ccf`
- Review bundle file SHA-256: `102d7d255a9346b6924d247ce5d89cd4826f5a8d58912b4d7b600a3b6af9afc4`
- Independent decision: `REVISE_FULL_GRID_PREREGISTRATION`

## Decisive counterexamples

1. `complete_call()` accepted a caller-measured duration taken before the
   coordinator acquired its lock and reread the full hash-chain state.  It
   then advanced the worker cost clock after that uncharged interval.  A
   0.25-second injected state-read delay produced approximately 0.508
   two-GPU seconds of physical loaded residency with zero accounted increment
   while the coordinator remained `READY`.  Repetition defeats the claimed
   19.4 A100 GPU-hour upper-bound proof.
2. The 12/2/6-frame tails were decoded without padding, but the model-visible
   message still described every input as a 10-second unit.  Tail legality,
   true duration, and truncated-unit identity appeared only in manifest and
   output provenance, not in the processor message/tensors.  This violates the
   requirement to explicitly represent legal shorter tail units to the model.
3. The preregistration inherited the V3 preflight facts and nonclaims but did
   not explicitly assert and bind that the V2 historical evidence remains
   unchanged.

The reviewer also confirmed that all currently scheduled GPUs had foreign
compute contexts and that the implemented launch authentication correctly
rejects this transient execution condition.  GPU contention was not treated
as an implementation failure and does not relax either blocker above.

No model checkpoint was loaded and no formal inference or reference artifact
was produced under this rejected seal.
