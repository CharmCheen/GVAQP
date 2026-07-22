# PSVR Autonomous Research Contract

## Objective

Develop and validate MF-PSVR: query-conditioned multi-fidelity progressive
scan, semantic refinement, frozen-oracle verification, event materialization,
and durable commit under one hard physical wall-clock deadline.

This contract extends `docs/PSVR_RESEARCH_CONTRACT.md`; it does not replace or
weaken the frozen oracle, reference materializer, capability boundary, or
held-out discipline in that contract.

## Frozen historical state

- `TWO_VIDEO_DEV_BENCHMARK = PASS`
- `SELECTED_PROXY_FAMILY = YOLOV8`
- `SELECTED_PROXY_CONFIG = Y8`
- `CURRENT_BEST_SIMPLE_BASELINE = FIFO`
- `CURRENT_VALIDATED_CORE_METHOD = NONE`
- `PSVR_RULE_BASED_TWO_VIDEO_SEARCH = NO_GO`
- `HELD_OUT_OPENED = false`

H-EXPOSE2, H-BOTTLE2, and H-STAGE1 are terminal negative results. Their fixed
scan, fixed frontier, NMS, and hand-written controller mechanisms may not be
renamed or retuned as MF-PSVR.

## Candidate and label semantics

An MF candidate is a **unit-level physical VERIFY opportunity with a frozen
track witness**, identified by `(source_video, query, unit, track)`. The track
witness supplies causal runtime features but is not asserted to have a
track-specific oracle label. The unchanged frozen oracle labels the unit/clip;
therefore the primary semantic target is:

`P(frozen oracle returns positive when this candidate's unit is verified)`.

Candidate identity may never change its bound track as more proxy evidence is
observed. Track-specific event claims require a separately audited
track-to-oracle attribution layer and are outside the first MF-PSVR version.

## Integrity gate

No new method result is admissible until Cycle 0:

1. validates unit/oracle/reference alignment;
2. binds each candidate to one immutable track witness;
3. rejects aliased baseline identities;
4. verifies query-specific score routing;
5. counts initialization, warm-up, SCAN, REFINE, VERIFY, materialization, and
   commit in the publication deadline;
6. treats physical repeats as latency repeats rather than semantic samples;
7. excludes missing/copied snapshots and all held-out semantic access.

Historical results remain preserved. Results that fail the publication
contract are marked invalid for MF-PSVR comparison rather than overwritten.

## Evidence and split discipline

- V0/V1 labels are evaluation-only and may not train or calibrate a refiner.
- Training and calibration are grouped by independent source/session.
- Random candidate-row splits are smoke tests only.
- Bootstrap and paired inference use independent video-query tasks.
- A third source is opened only after the full development method is frozen.
- The paper held-out split remains unopened until a later preregistered gate.

## Physical accounting

The query clock begins before oracle-session setup, proxy initialization, and
detector warm-up. All action paths reserve materialization and durable commit.
`deadline_met` is based on the complete query-to-snapshot elapsed time. Legacy
traces whose clock began after proxy warm-up are not publication-comparable and
must be rerun for any method entering an MF-PSVR table.

## Positive candidate gate

`MF_PSVR_METHOD_CANDIDATE = FROZEN_POSITIVE` requires all preregistered
development, cross-video, safety, cost, generalization, and ablation gates in
the publication program. A passing model score alone is insufficient.

