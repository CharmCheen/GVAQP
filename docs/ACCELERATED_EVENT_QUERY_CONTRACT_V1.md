# Accelerated Event Query Contract V1

Status: `FROZEN_BEFORE_NEW_QUERY_ORACLE_EXECUTION`

Baseline: `dspro@5047241b0561b911b9a519b18e8e7591c0074e70`

Research branch: `research/accelerated-event-query-v1`

Inherited evidence commits: `31592ba0a..dd84374c9`

## Research question

For the frozen query “查找需要驾驶员明显减速、制动或避让的事件。”, can a causal, deadline-safe policy allocate the next unit of wall-clock resource between `SCAN`, `VERIFY`, and `STOP` so that K3 events are returned earlier and with higher deadline recall than the best fixed or two-stage allocation, subject to event precision at least 0.80?

The final answer object is an event. Candidate count, detector count, verifier positive rate, action-class accuracy, GPU utilization, and code volume are diagnostics only.

## Frozen evidence levels

Qwen3-VL-32B is a fallible operational oracle. All formal recall and precision claims are explicitly relative to this oracle, never absolute semantic truth. `unknown` and parse failure remain unknown and cannot be silently converted to negative. Existing Dali/Wuhan Q1/Q2 labels concern ego-path entry and are not labels for this query; only their clip-grid, raw-runtime, and engineering evidence may be reused.

## Videos and unit grid

The three test videos are the hash-bound Dali, Hangzhou, and Wuhan files in `outputs/accelerated_event_query_v1/video_manifests/frozen_videos_v1.json`. The grid reuses the existing PSVR center10 semantics: non-overlapping 10-second units from time zero, with only the final unit truncated. There are 1,475 units in total. This selection is frozen before new-query oracle results.

## EventRelation and K3

After every completed SCAN or VERIFY, K3 must update candidate assignments, boundaries, merge groups, novelty/duplicate state, evidence state, and returnability. A returned record contains `event_id`, `query_id`, `video_id`, `start_time`, `end_time`, `event_score`, `evidence_status`, `source_candidate_ids`, `verification_history`, `k3_group`, and `commit_time`.

Formal return statuses are `VERIFIED_EVENT` and `PROBABLE_EVENT`. An unverified clip is never returned directly; it first becomes an event hypothesis. A probable event is explicitly marked and uses a threshold frozen independently of test outcomes. Main threshold and precision floor are 0.80; 0.70 and 0.90 are fixed sensitivity points.

The V1 kernel conservatively aggregates candidate probabilities by maximum, merges temporal neighbors up to 10 seconds without crossing a verified-negative barrier, and enforces 40-second core and 60-second event caps. The implementation is `src/garc_eval/accelerated_event_query/incremental_k3.py`. These defaults retain the prior K3 cap lineage but remain hypotheses until real new-query labels support boundary/merge quality.

## Event matching

The existing frozen benchmark rule is retained: strict positive temporal overlap makes a pair eligible; one-to-one assignment maximizes matched cardinality first and temporal IoU second. Thus one reference event matches at most one prediction. Extra overlapping predictions are false-positive duplicates. The tIoU threshold is 0.0 with strict `tIoU > 0`; boundary tolerance is 0 seconds. tIoU and boundary errors remain reported diagnostics.

## Objective and safety order

Evaluation is lexicographic:

1. zero deadline overrun;
2. zero post-deadline commit;
3. event precision at or above the frozen floor;
4. maximum deadline event recall;
5. maximum AnytimeEventRecallAUC under near-tied recall;
6. time-to-first-event, time-to-K-events, VLM calls, and GPU time.

An action is admitted only from an independently frozen complete-path upper bound. Realized post-deadline work commits no candidate, estimator, K3, EventRelation, or frontier mutation. Observed, missing, imputed, predicted, and upper-bound costs remain separate; only observed costs calibrate formal bounds.

## Information boundary

Controller state contains only causally public budget/cost, coverage, frontier, event-hypothesis, precision-risk, and recent-yield summaries. It cannot contain unverified 32B labels, unscanned candidates, future action costs, reference events, future K3 results, final metrics, or video identity. The schema and guard are in `src/garc_eval/accelerated_event_query/state.py`.

## VERIFY macro and headroom gate

The main macro is `VERIFY_EVENT_CALIBRATION_TARGET`: probable event with greatest precision risk; then a near-return-threshold core candidate capable of changing event state; then highest expected new-event value; deterministic identifiers break ties. `VERIFY_TOP1` remains an ablation.

No learned controller is trained unless stable SCAN-better and VERIFY-better states appear on multiple videos, a safe dynamic oracle exceeds the best fixed/two-stage policy without precision or deadline violations, leave-best-video-out is positive, and low budgets do not systematically regress. With three videos, learned results are mechanism validation only.

## Required rejection triggers

- Low K3-materialized YOLO event-recall ceiling: `REVISE_SCAN`.
- Correct candidates but fragmentation/overmerge/boundary failure: `REVISE_K3`.
- Headroom limited by deterministic verification target: `REVISE_VERIFY_TARGET`.
- Safe oracle headroom not predictable from public state: `REVISE_STATE`.
- Any admitted incomplete action, deadline overrun, or post-deadline commit: `REVISE_COST_SAFETY`.
- Mostly tied actions and no safe-oracle improvement: `NO_GO_BINARY_ALLOCATION`.
- Unstable oracle, too few events/states, or incomplete costs: `INSUFFICIENT_EVIDENCE`.

`GO_ACCELERATED_EVENT_QUERY` requires every gate in the user-specified objective; no partial result is promoted to GO.
