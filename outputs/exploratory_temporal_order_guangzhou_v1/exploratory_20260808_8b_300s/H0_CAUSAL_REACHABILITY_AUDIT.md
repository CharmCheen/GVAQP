# H0 causal reachability audit

`H0_COUNTERFACTUAL_BRANCHES_NOT_IDENTIFIABLE_FROM_EXISTING_TRACE`

The persisted Guangzhou traces validate selected-action exposure dependencies, but do not provide state-specific physical transitions for unselected legal actions. Reference labels may value an already legal action; they cannot create its physical transition or admission cost.

## Result

No reachable dynamic oracle or Gate-H metric was computed. The old cached greedy/headroom artifact is a clairvoyant diagnostic ceiling only, not a valid Guangzhou H0 oracle.

## Minimum evidence needed

- canonical pre-decision state snapshot and state hash for every branch point
- causally observed admission estimate/history used at each state
- for every evaluator-chosen legal alternative: its deterministic SCAN/VERIFY output, durable completion cost, and next-state transition under the same runtime contract
- an explicit branch-cache coverage manifest keyed by (state_hash, action), not labels alone

Raw traces and deadline-safe results were read only; their SHA-256 values are recorded in the JSON artifact.
