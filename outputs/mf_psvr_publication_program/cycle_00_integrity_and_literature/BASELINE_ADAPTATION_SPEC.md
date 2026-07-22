# MF-PSVR Baseline Adaptation Specification

`SPEC_STATUS = PREREGISTERED_BEFORE_NEW_PHYSICAL_RESULTS`

## Purpose

The audited systems optimize different objects under different resource
contracts. A cached proxy replay, an oracle-call budget, an amortized ingest
index, and a hard first-query wall clock are not interchangeable. This document
defines how each prior method may enter the MF-PSVR evidence ledger without
silently changing either its native claim or this benchmark's semantics.

An adaptation is not an original-paper reproduction. Every result row must name
both the method family and adaptation ID.

## Common physical contract

All primary-table methods must satisfy the following conditions.

### Frozen task and output

- Use the unchanged video units, Q1/Q2 prompts, frozen Qwen oracle, parser,
  reference materializer, and `k3_bridge_safe` semantics.
- Separate two keys. `opportunity_id = (source_video, query, unit,
  frozen_track_witness)` is immutable scheduling provenance;
  `verification_key = (source_video, query, unit)` is the frozen oracle's
  evaluated object. A witness is never described as oracle-confirmed.
- Count only oracle-positive, durably materialized EventRelation rows in strict
  F1 and AnytimeAUC_F1. Proxy-only, interpolated, propagated, and model-predicted
  candidates remain visible as diagnostics but are not confirmed results.
- Use one shared deterministic tie-breaking rule and one candidate-dedup rule.
  A method may choose order but may not change identity behind a candidate ID.
  Multiple opportunities sharing a verification key are deduplicated before a
  physical oracle call and share only the unit outcome; track attribution is
  explicitly `false` in the committed provenance.

### Clock and visibility

- Workload: `warm_oracle_cold_proxy`. Oracle weights may be resident; oracle
  session setup still counts. Proxy/model initialization and warm-up count.
- Synchronize GPU work before clock start and after each charged GPU action.
- Start `time.perf_counter_ns()` before session setup, video open, proxy load,
  refiner load, and warm-up.
- Charge decode/I/O, SCAN, REFINE, VERIFY, controller computation, K3
  materialization, serialization, fsync, atomic rename/commit, and final
  synchronization.
- Admission must reserve a complete action path and an independent durable
  commit path. Starting an action that predictably makes commit miss the
  deadline is a deadline-safety failure.
- Store the full action trace, monotonic timestamps, selected IDs, physical and
  logical oracle-call counts, model/config hashes, snapshot hashes, and failure
  states. Failed and deadline-miss runs are retained.

### Information boundary

- A clean-spawn selector receives only public metadata, observations generated
  after clock start, and results of its own oracle calls.
- V0/V1 labels, reference events, full-video proxy caches, and other methods'
  traces are unavailable to scheduling code.
- Offline learned weights may use only the independent training pool. Their
  training and one-time energy/cost are reported separately; weight loading and
  query inference are charged per query.
- A paper-native method may inspect/train on target-video samples only in a
  `FIRSTQUERY` view, after the clock starts, using evidence acquired by its own
  charged actions. Evaluation labels/reference events remain inaccessible.
- Paper-native cached/pre-indexed scenarios may be reported in a secondary
  table, but must be labeled `offline_or_amortized` and never mixed with the
  strict first-query physical table.

### Evaluation

- Primary endpoint: paired task-level wall-clock `AnytimeAUC_F1` at the frozen
  snapshot/deadline grid.
- Secondary endpoints: final F1, precision, recall, verified-event yield,
  verified-positive units, deadline misses, calls, GPU/CPU time, bytes read,
  materialization time, and commit time.
- Independent inferential unit: source-video x query. Seeds and deadline points
  are repeated measurements, not additional independent samples.
- Native paper metrics may be reproduced in separate diagnostic tables. They
  do not establish superiority on EventRelation recovery.

## Required controls

| Adaptation ID | Behavior | Scientific role |
|---|---|---|
| `ORACLE-SEQ-PHYS-v1` | Sequentially VERIFY every unit; materialize and commit positive prefixes. | Exhaustive upper-accuracy / lower-throughput control. |
| `FIFO-PHYS-v2` | Existing best simple FIFO order under the repaired full clock and immutable candidate binding. | Frozen simple baseline; no retuning. |
| `RANDOM-PHYS-v1` | Seeded permutation fixed before execution; otherwise same action path as FIFO. | Tests whether ordering carries value. |
| `Y8-SCORE-PHYS-v1` | Generate Y8 evidence online and rank immutable opportunities by the frozen query-specific score routing. | Tests whether detector score alone explains gains. |
| `SCAN-ONLY-PHYS-v1` | Online Y8 scan and candidate materialization, with no learned REFINE; VERIFY via the frozen baseline rule. | Separates candidate generation from semantic refinement. |

Historical B1 and B2 are one effective identity and cannot occupy two rows.
H-EXPOSE2, H-BOTTLE2, and H-STAGE1 remain terminal negative controls; they may
be cited as failures but not renamed or retuned into a new baseline.

## Prior-work adaptations

### ARC

The frozen benchmark cannot instantiate ARC's native contract exactly. ARC
requires binary probability distributions and oracle labels on a common
per-frame domain plus a relevant-clip duration `tau`; this benchmark exposes a
categorical frozen oracle only on 10-second units and materializes events with
K3. Therefore no current row is called faithful ARC.

#### `ARC-UNIT-INSPIRED-PHYS-v1` — comparable mechanism adaptation

Freeze the following mapping before any V0/V1 execution:

1. The ordered domain is the public sequence of 10-second units `i`. The target
   is `Y_i(q) = 1` iff the frozen unit oracle parses positive for query `q`.
2. After a complete online Y8/track pass, an independently calibrated unit model
   emits `p_i(q)`. ARC's proxy distribution is exactly
   `[1 - p_i(q), p_i(q)]`; Bernoulli entropy is used for importance sampling.
   Calibration training and all thresholds use independent sessions only.
3. A successful physical VERIFY converts the categorical parser result to
   `[1, 0]` or `[0, 1]`. Timeout, parse failure, ambiguous, or unusable output is
   charged but leaves the distribution unobserved and cannot be propagated.
4. Temporal clustering uses Jensen-Shannon divergence on adjacent unit
   distributions. Its threshold is frozen from independent calibration. Native
   relevant-clip `tau` is fixed to one unit because K3—not ARC—defines the
   benchmark event duration/bridging semantics.
5. Candidate intervals are runs with `argmax p_i = 1`. An ARC-selected index
   maps one-to-one to `verification_key=(source, query, unit)`; repeat selections
   are deduplicated. Only verified positive units enter K3.
6. Proxy generation, clustering, confidence/entropy computation, selection,
   Qwen VERIFY, K3, and commit all use the common clock. If the exhaustive proxy
   pass does not finish, ARC refinement never starts.

The adapter must first pass a synthetic binary-array test in which its selected
indices, candidate intervals, and confidence match the hashed local ARC
algorithm under `tau=1` and fixed clusters. The test establishes implementation
mapping only; it does not restore ARC's native frame/clip guarantee.

Allowing partial proxy evidence is a separate `ARC-PREFIX-INSPIRED` method and
cannot characterize ARC.

Report two views:

- `native_candidate_diagnostic`: ARC candidate clips/confidence, not comparable
  to strict EventRelation F1;
- `confirmed_eventrelation`: only frozen-oracle-confirmed materialization,
  comparable but explicitly modified from ARC's native endpoint.

The local snapshot may support scaffolding, but its missing runtime threshold
adaptation and uncertain provenance prohibit labeling either mapping a released-
code reproduction. A native ARC result, if reproduced on ARC datasets and
frame-level semantics, belongs in a separate offline protocol table.

### SUPG

#### `SUPG-RECALL-PHYS-v1` — one effective baseline

Run the selected proxy over the complete record universe after clock start,
then run SUPG's recall selector and spend the remaining physical time verifying
selected units. Above-threshold but unqueried records are retained only in the
native diagnostic view; they are not confirmed EventRelation rows.

SUPG's statistical guarantee belongs to its native oracle-call protocol. Once
proxy cost, deadline censoring, temporal materialization, and mandatory
confirmation are imposed, the comparable row is an algorithmic adaptation and
must not advertise the native guarantee without a new proof.

The two existing SUPG-RT views are not independent baselines: the Cycle-0 audit
found that they collapse after K3. Keep one selection policy/config hash and one
physical result row.

### ABae

#### `ABAE-ALLOC-DIAGNOSTIC-v1` — not a primary event baseline

ABae estimates aggregates, whereas this task recovers events. It may be used to
allocate a fixed verification sample across frozen proxy-score strata, with
yield/variance reported as a mechanism diagnostic. It must be called
"ABae-inspired stratified allocation," not "ABae," unless an aggregate query
and its native confidence interval are evaluated.

Do not use the existing confirmed-segment adapter as evidence of faithful ABae
performance, and do not count this diagnostic toward the number of direct
event-retrieval baselines.

### ExSample

#### `EXSAMPLE-PHYS-v1` — primary incomplete-scan baseline

Partition each source into the paper-style temporal chunks. Start with no proxy
index. Use a seeded Thompson-sampling policy to choose a chunk and an unqueried
unit within it. The expensive sample is the frozen physical oracle call; reward
is a newly confirmed positive opportunity/event under the fixed dedup rule.
Random access, decode, oracle work, controller overhead, K3, and commit all
count. Stop by deadline admission rather than a result-limit alone.

This preserves ExSample's discriminating mechanism—query-time adaptive sampling
of unindexed temporal chunks—but maps its distinct-object endpoint to the
benchmark's confirmed-event endpoint. Because the cited public repository
contains only the report, record this as an independent reimplementation and
validate it on synthetic arm distributions before physical use.

### Seiden

Two cost views are necessary.

#### `SEIDEN-FIRSTQUERY-PHYS-v1`

Build query-agnostic anchors/index after the physical clock starts, then perform
query-dependent MAB sampling and temporal interpolation. Interpolated labels
are candidate evidence only; frozen-oracle confirmation is required before K3.
This is the fair first-query comparison.

#### `SEIDEN-AMORTIZED-v1`

Build the index outside the query clock and report its construction time,
storage, assumed number of future queries, and amortized charge separately.
This row belongs only in an explicitly amortized secondary table.

The released code's cached target-DNN outputs may validate allocation logic but
cannot provide physical runtime. A new adapter must execute inference online.
Because the benchmark oracle is query-aligned rather than a generic object
detector, the mapping from Seiden anchors to semantic evidence is a material
adaptation and must be documented before implementation.

### MIRIS

Three identities are required because training provenance changes the problem.

#### `MIRIS-FIRSTQUERY-v1`

After the common clock starts, sample the target video as MIRIS prescribes,
execute the detector/tracker and predicate needed to label training/validation
segments, train the query-specific filter/refiner, plan, and execute. All target
sampling, model training, detection, stage files, and commit count. The worker
may use only evidence acquired by these charged actions, never benchmark labels.

#### `MIRIS-AMORTIZED-v1`

Perform native target-video preprocessing/planning outside the query clock.
Report its time, GPU energy, sampled duration, storage, and assumed number of
reuses. This is the closest native-cost view and belongs only in a secondary
amortized table.

#### `MIRIS-XFER-PHYS-v1`

Train/calibrate on the independent pool and transfer frozen weights to V0/V1.
This is the former strict adaptation. It is useful as a source-generalization
control but introduces a transfer problem absent from native MIRIS and cannot
support a statement that MF-PSVR beats MIRIS.

For all three, preserve a `native_track_output` diagnostic. A separate
`qwen_confirmed_eventrelation` view may map track/tuple output to units and call
the benchmark oracle, but Qwen is an added evaluation contract, not a MIRIS or
MF-PSVR novelty mechanism. The official code's cached detections are unit-test
inputs only for the physical view.

### DIVA

DIVA is a deployment-mismatched but mechanism-critical prior: it already uses
sparse capture-time landmarks, query-specific operators of increasing cost and
accuracy, multi-pass online processing, cloud validation, and continuous result
materialization.

#### `FIXED-MULTIPASS-PHYS-v1` — generic mechanism control

Run frozen fidelity levels in a fixed cheap-to-expensive pass order, letting
earlier scores prioritize later work and interleaving VERIFY. It deliberately
has no landmarks, target/query-specific operator bootstrap, or online upgrade.
It is a cost-matched cascade control, not DIVA and cannot support "beats DIVA."

#### `DIVA-FIRSTQUERY-v1`

After clock start, construct sparse high-accuracy target-video landmarks, use
them to bootstrap a query-specific operator family, and train/select/upgrade
operators online using observed progress. Charge landmark generation, first and
later operator training/shipping (or a measured local emulation), multi-pass
processing, high-accuracy validation, materialization, and commit. This strict
view changes DIVA's capture-time assumption but retains its defining mechanisms.

#### `DIVA-LANDMARK-AMORTIZED-v1` — secondary native-cost view

Allow sparse, high-accuracy landmarks to be created outside the query clock,
then train/select/upgrade query-specific operators during execution. Report
landmark construction time, storage, assumed query reuse, and network emulation
separately. This row cannot enter the strict `warm_oracle_cold_proxy` table.

DIVA's native progress metrics and the adapted confirmed EventRelation metrics
must remain separate. The paper's cloud detector validates frames, so MF-PSVR
must not claim that cheap-candidate/high-accuracy-confirmation staging or
progressive materialization is new.

### Zeus

#### `ZEUS-CONFIG-PHYS-v1` — mandatory controller comparator

Train the action classifier and accuracy-aware RL policy on independent
query-aligned sessions, preserving Zeus's action space over resolution, segment
length, and sampling rate. At query time, let the policy traverse raw video and
emit localized action segments. Charge decode, adaptive proxy-feature generator,
classifier, policy, segment construction, and output materialization.

Map emitted segments to unit verification keys only in a separate confirmed
view; Qwen confirmation is an added benchmark endpoint. Freeze the accuracy
target and reward on independent calibration. Validate policy actions on a
small deterministic environment. Because the benchmark action ontology and
confirmation differ from Zeus, call the result an adaptation, not reproduction;
nevertheless it is mandatory before a learned heterogeneous-controller claim.

### FiGO

#### `FIGO-UNIT-PLAN-PHYS-v1` — mandatory chunk/fidelity comparator

Use public unit order as the video domain and a frozen ensemble of available
fidelity models. Starting with the whole video as one chunk, profile exactly
`lambda` uniformly selected units per chunk, including the frozen reference
action required by the FiGO accuracy comparison; recursively split only when
the estimated execution saving exceeds additional profiling cost. Assign one
model or skip to each final chunk, then execute the plan.

Freeze `lambda`, accuracy target, ensemble, cost estimator, and split tie-breaks
on independent calibration. Charge optimization/model profiling, execution,
Qwen calls, EventRelation mapping, and commit. Model outputs not individually
verified remain diagnostic candidates. This is a unit/Qwen adaptation and must
first reproduce the expected plan on synthetic chunks.

### Boggart

#### `BOGGART-FIRSTQUERY-v1`

Build the model-agnostic blob/trajectory index after clock start, cluster chunks,
sample the query model on representative frames, estimate propagation distance,
and execute propagation. Charge index construction, storage writes, sampled
inference, propagation, EventRelation mapping, and commit.

#### `BOGGART-AMORTIZED-v1`

Build the index outside the query clock and report preprocessing time, CPU
energy, storage, and reuse count separately. This best reflects Boggart's native
cost split but cannot enter the cold-proxy first-query table. In both views,
propagated results are not oracle-confirmed; any Qwen confirmation is a benchmark
adaptation. Until the official code is commit-audited, these are specifications,
not released-artifact reproductions.

## Adaptation identity and admission gates

A baseline result is admissible only if all gates pass:

1. **Semantic mapping:** a machine-readable file maps native records, frames,
   clips, or tracks to immutable benchmark opportunities and states what changed.
2. **Trace distinction:** methods counted separately differ in action sequence
   or selection distribution on at least one preregistered diagnostic case.
   Different names or output filters are insufficient.
3. **No hidden work:** all query-dependent proxy/detector results are generated
   after clock start in the strict table.
4. **Deadline equivalence:** identical start/stop, reserve, synchronization,
   materialization, and commit code paths are used.
5. **Information isolation:** the clean worker cannot read evaluation labels or
   precomputed semantic evidence.
6. **Native/comparable separation:** native metrics and adapted EventRelation
   metrics have different column prefixes and never share a claim.
7. **Hash completeness:** source commit/file hash, adapter hash, resolved config,
   model weights, environment, and raw trace are recorded.
8. **Synthetic validation:** selector behavior is checked on small cases with
   known expected order before expensive physical execution.

Failure of a gate invalidates the result row without deleting its artifacts.

## Decision rule for implementation effort

Implement the smallest discriminating set first: FIFO, RANDOM, Y8-SCORE,
SCAN-ONLY, EXSAMPLE-PHYS, FIXED-MULTIPASS, ZEUS-CONFIG, and FIGO-UNIT-PLAN. Add
ARC-UNIT-INSPIRED only after its common-domain synthetic test. `MIRIS-XFER` is a
transfer control; a native MIRIS or DIVA superiority statement additionally
requires the corresponding FIRSTQUERY/AMORTIZED view. Boggart first-query is
required only if ingest-index cost is part of the claimed deployment; its
amortized boundary must still appear in related work. Seiden and ABae remain
secondary unless interpolation or stratified allocation becomes the dominant
competing explanation.

This ordering is a resource-allocation decision, not evidence that the deferred
methods are weaker.
