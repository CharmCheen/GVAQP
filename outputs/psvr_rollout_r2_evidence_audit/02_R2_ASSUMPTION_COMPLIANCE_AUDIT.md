# R2 assumption compliance

| Condition | Satisfied | Evidence | Limitation |
|---|---:|---|---|
| pi0 defined on every safe action set | True | chooses FIFO CONFIRM, else next SCAN, else STOP | Within the finite synthetic action model only. |
| pi0 proper | True | HORIZON=1600, STOP always safe; all 4608 raw traces terminate | Properness is demonstrated for this finite synthetic construction, not video. |
| base action included | True | candidate tuple is every safe action; B1 action is among safe actions | Tie-break is not explicitly B1-preferential, but inclusion is sufficient for weak non-inferiority. |
| transition model exact | True | deterministic finite world library and replay | Exact only relative to the frozen toy generator. |
| duration model exact | True | durations are world-deterministic; support admission is frozen | Not a wall-clock model. |
| visible-history posterior exact | True | uniform mass over replay-consistent finite worlds | Exactness is a code/design claim; source hashes bind the implementation. |
| Q full-horizon exact | True | each candidate is continued until STOP in each supported world | No finite-MC approximation, within the finite library. |
| same continuation policy | True | continuation defaults to B1_SHIELDED_PI0 | Applies to candidate evaluation, not a practical learned policy. |
| terminal value exact | True | sum HORIZON-completion time over NEW_COMMIT | Synthetic D1 utility only. |
| planning cost zero | True | declared 0; utility has no compute-time term | No physical latency evidence. |
| safe action set consistent | True | one safe-action function used for M1 and B1 | Does not establish real-world safety. |

`NON_INFERIORITY_THEOREM_APPLIES = true`, within the stated synthetic expectation scope.
