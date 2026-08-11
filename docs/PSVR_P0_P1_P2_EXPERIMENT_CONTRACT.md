# PSVR P0/P1/P2 Frozen Experiment Contract

Status: **FROZEN BEFORE P0/P1/P2 TRAINING**  
Contract ID: `PSVR_CUTIN_P012_STAGE_A_Q1_V1`  
Freeze date: 2026-07-23 UTC

## 1. Research decisions

The strong system baseline is ARC. The first and only query is the existing
frozen Q1, `OTHER_VEHICLE_ENTERS_EGO_PATH`. The experiment uses only the
existing MF-PSVR Stage-A frozen sample, durable Oracle outputs, frozen YOLOv8n
weights, and frozen ByteTrack configuration. New
Oracle calls, new labels, label changes, new datasets, YOLOP, lane
reconstruction, learned controllers, bandits/RL, and architecture or security
work are prohibited.

The repository does not contain a distinct durable contract literally named
`target-vehicle cut-in`. The closest formal query is Q1 with projection
`cyclist|vehicle`. This experiment therefore tests the frozen
`OTHER_VEHICLE_ENTERS_EGO_PATH` proxy task. It must not be reported as a
vehicle-only or human-adjudicated cut-in benchmark.

## 2. Data manifest

The candidate universe is the 96 physical-call identities in
`STAGE_A_FROZEN_SAMPLE.csv`, one 10-second candidate per physical call. Q1
labels come from `ORACLE_LABEL_MANIFEST.csv`; raw durable responses and their
hashes come from the Stage-A Oracle directory and call manifest. Detection,
tracking, and trajectory materialization reuse the exact frozen video
identity, unit bounds, YOLOv8n weight/configuration, sampling rate, and
ByteTrack configuration recorded by Stage A.

Every authoritative input is listed with path, artifact type, repository
commit, SHA-256, creation time, query, Oracle contract, event-matching
contract, and validity in `outputs/cutin_p012_contract/frozen_manifest.*`.
The manifest and this contract are hashed before model fitting.

## 3. Query and Oracle label contract

`query_id = Q1`; formal query name is `OTHER_VEHICLE_ENTERS_EGO_PATH`; the
frozen type projection is `cyclist|vehicle`. A candidate is positive iff its
durably committed Q1 projection is `positive`, negative iff it is `negative`.
Only rows with `label_status=VALID`, `parse_status=ok`, and projected label in
`{positive, negative}` enter confirmatory fitting or metrics. Abstentions,
parse/runtime failures, missing rows, empty responses, contract/version
conflicts, and label/event conflicts remain in the audit and are excluded.
No invalid row is converted to negative and no label is propagated.

Committed call choice and conflicts are resolved only through the frozen call
and label manifests. The contract identities are the frozen model, prompt,
parser schema/source, and sampling-code hashes. Calls with different
identities are never merged.

## 4. Reference event mapping

The only discovered Stage-A K3 artifact, `consecutive_positive_units_v1`, is
constructed directly from the same projected positive candidate labels
(`stage_a_oracle.py`, `build_event_groups`) and is therefore not an
independent `EventRelation` reference. It is disqualified from event
evaluation. No frozen independent event boundaries and no frozen candidate to
reference-event match rule exist for this candidate universe. Consequently
`EVENT_LEVEL_EVALUATION = BLOCKED_MISSING_FROZEN_MATCH_RULE`; K3 membership
must not be used for event metrics, event claims, or cost replay.

## 5. Oracle support

The full 96-candidate Q1 universe is retained. Cells at K whose selected
candidates contain an invalid/unlabeled row are
`INVALID_OUTSIDE_ORACLE_SUPPORT`; candidates are neither skipped nor
backfilled. Full policy support is true only if all 96 Q1 candidates are valid.
Otherwise system results are explicitly `LABELED_SUPPORT_REPLAY`.

## 6. Split and leakage contract

Leakage edges are same video/session, same reference event, overlapping
windows, or same source clip. Connected components define `split_group_id`.
All P0/P1/P2 representations use the identical fixed manifest. The primary
evaluation is a one-time deterministic, stratified five-fold grouped outer
evaluation over valid Q1 candidates, grouped by connected component. Model
selection uses the three grouped development folds recorded separately for
each outer training set in `split_manifest.csv`. LOSO predictions use source
session as the held-out group when estimable.

Candidate, source/session/video, filename, absolute time, query/Oracle/event
identity, latency, label, and split fields are metadata only and prohibited as
model inputs. The split is frozen before feature-label model fitting and is
not changed after test inspection.

## 7. Feature whitelist

All representations share candidates, frames (5 fps), labels, splits, model
families, budgets, and seeds. Coordinates are normalized by image dimensions;
all rates are per second; no frame after `window_end` is read.

**P0** uses only per-frame YOLOv8 detection aggregates: count, eligible-target
count, confidence distribution, normalized box area/center/bottom
distribution, left/center/right and central-region counts, aggregate centroid,
no-detection rate, detection rate, and their temporal summaries. Track
identity, ByteTrack-derived values, flow, camera motion, lanes, drivable area,
and depth are prohibited.

**P1** is P0 plus frozen ByteTrack trajectory aggregates: track count and
duration; start/end position; displacement, velocity and acceleration; area
growth; motion toward center and side-to-center entry; direction change,
stability, gaps, confidence, relative-distance change, approach proxy,
frozen TTC-like proxy, and top-N aggregates.

**P2** is P1 plus lightweight background camera-motion normalization:
320-pixel long-side grayscale frames; detection boxes expanded by 10% and
masked; Shi-Tomasi background corners; sparse pyramidal Lucas-Kanade flow;
RANSAC partial affine transform; background reliability; compensated track
motion; and explicit missingness. Failed motion estimates retain the
candidate, set `motion_valid=0`, and leave compensated values missing.
Training-fold imputers alone handle missing values.

The three JSON feature schemas are frozen before test scoring.

## 8. Models and tuning

Logistic regression uses L2, `C in {0.01,0.1,1,10}` and
`class_weight in {None,balanced}`. Imputation and scaling fit only on training
folds.

LightGBM is primary and evaluates exactly 16 configurations:
`num_leaves in {7,15}`, `max_depth in {3,6}`,
`learning_rate in {0.03,0.10}`, and `min_child_samples in {10,30}`, with a
maximum 500 estimators and early stopping. Development AUPRC selects a
configuration; ties select the lexicographically simplest configuration.
Test outcomes never select hyperparameters.

Baselines are deterministic random (100 seeds), the existing frozen Stage-A
Q1 candidate score (`STAGE_A_FROZEN_SAMPLE.csv:q1_score`, identical to
`UNIT_SCORES.csv:unit_score`), and training-fold shuffled labels (20 seeds),
plus P0/P1/P2 Logistic and LightGBM.

## 9. Metrics

Candidate metrics are grouped OOF AUPRC (primary), AUROC, Precision/Recall at
8/16/32, Brier, 10-bin ECE, and high-global-motion negative FPR. The motion
threshold is the training-fold 80th percentile among valid negatives.

When mapping and support permit, event metrics are distinct Event Recall at
8/16/32, Event Recall versus Confirm Calls AUC, duplicate-candidate rate,
candidates per recovered event, and unrecovered reference events.

System metrics are unique confirmed events, event recall/F1, event-F1 versus
deadline AUC, SCAN/feature/CONFIRM/materialization/commit/wall time, calls,
duplicates, and misses. They are formal only if a matching complete ARC
candidate universe, Oracle support, and deadline trace exist. Otherwise they
are a labeled-support replay and the full system claim is `NOT_ESTABLISHED`.

## 10. Runtime accounting

The same hardware, candidate videos, resolution, and 5 fps sampling are used.
Detection, incremental ByteTrack, incremental camera motion, aggregation, and
classifier inference are timed separately. At least three repeated physical
measurements on the same frozen candidate and setting are reported with mean,
median, p90, FPS, seconds/video-hour,
peak GPU memory, and peak process RSS. Cached replay is charged the measured
first-computation cost. ARC SCAN, CONFIRM, K3/materialization, and commit
costs are included whenever a compatible trace exists.

## 11. Statistical analysis

P1-P0 and P2-P1 are paired by `split_group_id` (session/source clip). The
analysis uses 10,000 group-bootstrap resamples and reports aggregate delta,
95% percentile CI, group win rate, median group delta, and leave-best-group-out
delta. A gain is not single-group-driven only if aggregate delta is positive,
at least half of valid group deltas are nonnegative, and leave-best-group-out
delta remains positive.

## 12. Baseline, Go/No-Go, and claims

ARC_FULL and `ARC_SCHEDULER + {RAW_PROXY,P0,P1,P2}` must reuse a matching
frozen candidate universe and physical latency/deadline contract. Existing
ARC traces on a different two-video universe may document ARC, but may not be
passed off as a component-replacement comparison on Stage A.

P1 is selected only if it improves grouped AUPRC and distinct-event-recall
AUC, is not single-group-driven, survives ByteTrack cost, and has no evident
cross-group collapse. P2 is selected only if AUPRC is no worse than P1,
high-motion negative FPR is lower, event-recall AUC is higher, the gain is not
single-group-driven, and the same-deadline result survives motion cost. If P2
only improves candidate AUPRC, P1 is selected.

Claims are restricted to the frozen single-provider, enriched Stage-A Q1
support. Cross-source generalization is always `NOT_ESTABLISHED`. A
vehicle-only cut-in, human ground truth, full candidate-space prevalence, or
online end-to-end result is not established by these data.

## 13. Blocking conditions and repair

Missing/contradictory hashes, Oracle identity conflicts, label-event
conflicts, split leakage, fewer than two classes in a required training/test
fold, missing frozen event mapping, incomplete Oracle policy support, or lack
of a matching ARC trace blocks the affected claim, not the remaining
candidate experiment.

One controlled repair cycle may correct only paths, schemas, cache damage,
frame/time conversion, feature implementation, split leakage, numerical
stability, runtime compatibility, or implementation/contract mismatch. It
must be logged with issue, cause, affected files, fix, before/after hashes, and
reruns. It may not change data, labels, feature scope, search budget, Oracle,
or introduce YOLOP/RL.

Contract and manifest hashes are written to
`outputs/cutin_p012_contract/contract_freeze.json`. Any later contract change
invalidates prior results unless recorded as an allowed repair.
