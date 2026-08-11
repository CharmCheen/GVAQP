# Algorithm specification

## SCAN

State is the ordered tuple of public units plus already scanned unit IDs, current unit, remaining wall-clock budget, past action costs, and already revealed candidates/observations. A SCAN action names one unscanned unit. The invariant is that each completed unit enters `scanned_unit_ids` once and every returned unit belongs to the public unit universe.

`AnytimeLargestGap` selects the middle remaining unit when coverage is empty. Otherwise it maximizes the minimum index distance to any scanned unit. Exact ties select the lower unit index. It is deterministic and ignores video identity.

Each completed SCAN reveals caller-supplied public rows produced by the frozen detector/tracker/scorer. On first visibility, candidate generation binds one witness per unit by `(-score, track_id, candidate_id)` and never silently changes that track. Creation time/index remain fixed, and the accumulated visible prefix is re-emitted to the Frontier.

## Controller

R4 tracks realized wall-clock only for completed actions. Let `rho = scan_time / (scan_time + confirm_time)`. At time zero or when `rho < 0.25`, it desires SCAN; otherwise it desires CONFIRM. If the desired action is illegal but the other action is legal, it uses the legal action. If neither complete action is estimated to fit, it returns STOP. An empty Frontier makes CONFIRM illegal and therefore triggers the SCAN fallback when SCAN fits.

## Deadline admission

An action is admitted exactly when its finite, non-negative estimated complete cost is no greater than remaining budget. Before an action type has observations, its estimate is the global measured manifest fallback; afterward it is the linear-interpolated q90 of causally observed costs, matching the frozen NumPy quantile. Admission is predictive: a realized cost can exceed its estimate, so formal physical hard-deadline safety is not established. Actions are indivisible. Only successful complete actions enter ratio accounting.

## Frontier and CONFIRM

Frontier deduplication key is `unit_id`. Updates replace the visible row for a non-terminal unit, retain the ten highest scores, and permanently mark capacity drops as discarded. Ordering is descending score, then ascending `unit_id`, `track_id`, and `candidate_id`. Queried and discarded units cannot re-enter. Candidate age is elapsed time minus creation time.

CONFIRM selects `Frontier.best()`, constructs a request from candidate ID, unit ID, track ID, and public payload, and calls an injected adapter. The response is parsed before the frozen replay event IDs are materialized and canonicalized. The runner then removes event IDs already committed by prior actions. Only after all stages succeed does it terminalize the unit, account the completed action for the ratio, and atomically fsync-commit the action and utility set.

Backend, parse, or materialization failure does not terminalize the candidate or append a completed action; any reported physical cost is still elapsed wall-clock. Commit failure leaves in-memory durable state unchanged and is surfaced. STOP performs no Oracle action, but it durably writes the final result, stop reason, and optional failure record. Evaluation utility at a deadline excludes results whose completion time is after that deadline while the durable snapshot retains completed late evidence.
