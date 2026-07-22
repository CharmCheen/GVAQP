# A4 keyed probability realization

All A4 planner draws use SHA-256, the frozen H1B keyed primitive. The canonical
UTF-8 preimage is the canonical JSON array of this ordered tuple:

`["H1B_A4", episode_public_id, planning_decision_index, posterior_sample_index, branch_transition_index, variable_family, entity_stable_id]`

This typed serialization prevents delimiter collisions. `branch_transition_index`
is a fixed action/family/entity schedule coordinate, never an incrementing
runtime counter. `U` is the unsigned big-endian integer represented by the first eight digest
bytes, divided by `2^64`. Binary realization is exactly `U < p`. Categorical
realization chooses the first canonical category whose cumulative probability
strictly exceeds `U`, and chooses the final category only for a floating-point
tail. No PID, worker, object address, unordered iteration, or actual execution
random tape may enter a key.

The fixed numeric transition coordinate is
`action_ordinal*10000000 + family_ordinal*1000000 + entity_ordinal`, where
`action_ordinal` starts at zero in each branch, `family_ordinal` is the index
in A4's frozen family list, and `entity_ordinal` is the A2 lexical candidate,
pair, frontier, or legal-action rank for that family. Each term must be below
its stated multiplier. This is a schedule coordinate, not a counter of prior
draws, so unrelated retained/missing variables cannot renumber later keys.
