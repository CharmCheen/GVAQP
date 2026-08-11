# Current research status

## Established

- The shipped runtime contains the complete SCAN-to-final-result chain: frozen candidate binding, Frontier lifecycle, fixed realized-wall-clock control, deadline admission, CONFIRM adapter/parsing, replay event materialization, cross-action deduplication, and durable action/final commits.
- Differential tests reproduce the frozen SCAN, Frontier, R4 action choice, q90 deadline admission, replay materialization, and durable-result semantics over the checked case domains.
- The selected-Frontier input Gate is currently blocked because only one of four required independent new videos was preliminarily eligible in the frozen evidence.

## Selected

- SCAN policy: `SAFE_COVERAGE_POLICY`, default `ANYTIME_LARGEST_GAP`.
- Controller: `R4_FIXED_TIME_RATIO_25_75`, based on actual cumulative wall-clock.

## Audit correction

The earlier curation was not literally SCAN-only, but its success statement was too strong: candidate generation was not an independent frozen boundary, result parsing/materialization failure semantics were incomplete, durable state mutated before write and lacked a final STOP snapshot, and deadline q90/fallback parity was not tested. `POST_SCAN_CHAIN_AUDIT.md` records the direct file/import/CLI/test evidence and the repairs.

## Not established

- Multi-fidelity preview signal, region-value proxy signal, Myopic-VPS signal, common-utility alignment, formal physical deadline safety, and formal generalization.

## Blocked

- Ratio-Anchored controller.
- Selected-Frontier calibration: insufficient independent videos; three additional qualifying videos were missing.

## Deferred

- Bandit and SMDP. RL is not part of the current system.
