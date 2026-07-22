# A4 A2 operator application order

For composition of more than one operator on the same kernel, the canonical
family order is:

1. `candidate_yield`
2. `grouping`
3. `confirm_outcome`
4. `novelty`
5. `materialization`
6. `duration`

For a targeted binary kernel, A2 sign/form/magnitude is applied to `P0`, then
A1's probability clipping is applied. For categorical grouping, the target
operator shifts mass from `CORRECT` to `UNDER_MERGE` under a negative sign and
to `OVER_MERGE` under a positive sign by the frozen magnitude; negative
components are projected to zero and the vector is normalized in the frozen
category order. A zero total falls back to the original `P0`.

At JOINT, each applicable family is transformed in that order. The separate
action realization schedule is frozen in `07_CANONICAL_TRANSITION_SCHEDULE`:
duration is realized before SCAN/CONFIRM outcome variables as required by A4.
All variables required by an action are realized before its post-state is
committed.
