# Partial-SCAN Benchmark Construction Contract

Status: **PRE-EXECUTION FROZEN CONTRACT**  
Benchmark: `PARTIAL_SCAN_BENCHMARK_PILOT_V1`  
Purpose: validate whether a Partial-SCAN benchmark can be constructed. This
pilot does not select or compare scheduling methods.

## Frozen scope

`PILOT_METHOD_SELECTION = PROHIBITED`. The strict query is
`TARGET_VEHICLE_CUT_IN`: another motor vehicle enters the ego vehicle's
expected driving path from an adjacent or lateral direction. Cyclists,
pedestrians, ego lane changes, ordinary parallel travel, overtakes without
path entry, and ambiguous path entry are excluded.

The atomic action is one independently executable contiguous 10-second
microchunk. The formal action universe is the offset-0 non-overlapping
partition; offset 5 seconds is evaluator-only partition sensitivity. Tail
units execute the complete remainder and remain explicitly typed as tails.
Tracker state resets per action. Cross-unit tracking and cross-unit candidate
completion are prohibited.

P0/P1/P2, SCAN-CONFIRM control, bandits, RL, ARC outcome claims, and scheduler
method selection are out of scope.

## Video selection

The pilot uses the shorter and longer of the two complete long videos already
content-audited in the repository's two-video physical program:
`long_video_dataset3.mp4` and `驾驶-大理.mp4`. Candidate clips and the
documented 208-second `realcartest_5k` prefix are ineligible. Exact paths,
hashes, metadata, and selection reasons are frozen in `immutable/videos.csv`.

## SCAN operator

The decoder is OpenCV over the exact source bytes. Each action seeks to its
frozen first frame, decodes the complete half-open temporal unit, and samples
at 5 FPS. YOLOv8n uses the frozen local weight, 640 input size, confidence
0.25, and NMS IoU 0.45. Only COCO motor-vehicle classes 2, 3, 5, and 7 enter
the public operator. ByteTrack uses the repository's frozen configuration and
is constructed afresh for every action.

A unit-local raw candidate requires at least three observations, front-region
occupancy at least 0.05, and positive lateral-to-centre motion or box growth.
Visible-subset admission recomputes zero-anchored feature percentiles from
only revealed raw candidates and applies deterministic temporal NMS at IoU
0.50. It never reads a full-scan candidate list.

## Independent reference

Reference construction is a separate pre-benchmark physical process. It may
use the frozen full-context Oracle before final benchmark freeze, but it may
not read SCAN outputs, raw candidates, proxy scores, policy traces, or
candidate-event mappings. It systematically covers the complete timeline
with 30-second windows at 15-second stride. Raw responses and input lineage
are durable. Overlapping detections are merged only by the frozen reference
rules; ambiguous rows remain explicit.

Without human adjudication the reference type is
`FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE`, never ground truth. Reference
completeness may be `COMPLETE`, `PARTIAL_OR_UNVERIFIED`, or `BLOCKED`.

## Event exposure

An event is exposed by a visible unit set only when the candidate generator is
rerun from outputs of that set, emits a legal candidate whose entire lineage
is visible, and the candidate passes the frozen match rule. The match rule
requires matching video and motor-vehicle event type plus either at least 0.5
seconds temporal intersection or containment of the reference-event midpoint.
Temporal overlap alone cannot create a candidate.

## Replay and information isolation

Policies receive only public unit IDs/bounds, scanned units, current position,
remaining estimated budget, revealed outputs/candidate IDs, past costs, and
geometric coverage. Reference events, unscanned outputs, candidate-event maps,
future actual costs, proxy scores for unscanned units, and total event count
are evaluator-only. Replay results are
`LOGICAL_REPLAY_OR_ESTIMATED_COST`.

## Physical runtime

The controlled protocol is `CONTROLLED_WARM`. Each policy run starts in a
fresh process with a newly opened decoder; the YOLO model loads once per run;
ByteTrack resets per action. Each action records seek, decode, model, tracker,
candidate, overhead, actual and cumulative wall-clock time. Actions are
atomic: an action may not start when the conservative estimate exceeds the
remaining budget, and a started action must finish.

The four representative paths—Sequential, Random without replacement,
Uniform-prefix, and Anytime Largest-Gap—run only to populate path classes and
validate the environment. A 4×4 Latin square controls order. No performance
ranking or event-recall conclusion is permitted.

The conservative policy-visible cost is the transition-class Q90 from
development physical traces. Evaluation uses actual action time. Warm and
cold observations may never be mixed.

## Immutability, audits, and claims

Six machine-readable contracts, videos, the offset-0 timeline, reference
events, and offset-0 atomic SCAN outputs form `immutable/`. After
materialization, every file is SHA-256 manifested and the directory is made
read-only. Any change requires a new benchmark version. Derived candidates,
maps, cost models, policy traces, audits, and reports are outside immutable.

Acceptance covers timeline completeness, all-unit executability, unit
determinism, reference independence/provenance, phase sensitivity, full-scan
exposure ceiling, visible-subset replay, policy isolation, cache protocol,
action-trace completeness, deadline enforcement, path-cost support, and
replay/physical directional agreement.

Legal terminal states are `SUPPORTED`, `PARTIALLY_SUPPORTED`, and `BLOCKED`.
Regardless of terminal state:

`PILOT_METHOD_SELECTION = PROHIBITED`  
`EVENT_AWARE_SCAN_POLICY_CLAIM = PROHIBITED`

One controlled repair cycle may address only paths, schemas, frame/time
conversion, deterministic serialization, implementation bugs, runtime
compatibility, or contract mismatch. It may not change query semantics,
videos, action granularity, labels, method scope, or interpret pilot paths as
a scheduler comparison.
