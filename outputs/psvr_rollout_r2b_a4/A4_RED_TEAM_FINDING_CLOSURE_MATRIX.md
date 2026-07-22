# A4 red-team finding closure matrix

All original findings remain non-closed because the new independent reassessment found `BLOCKED_INDEPENDENT_VERIFIER`. Repairs are implemented and focused regressions pass, but no item depending on replay/evidence can honestly be `VERIFIED_CLOSED` while a forged canonical post-state is accepted.

| Findings | Status | Decisive limitation |
| --- | --- | --- |
| RT-A4-01–09, RT-A4-11–12 | REPAIR_IMPLEMENTED_NOT_VERIFIED | Independent transition/post-state/continuation replay is absent. |
| RT-A4-10 | SUPERSEDED_BY_NEW_BLOCKER | Imports are non-circular, but verifier accepts forged post-state after local hashes are recomputed. |
