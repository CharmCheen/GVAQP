# Held-out enter-ego-path event reference construction and freeze v1

## Exact decision

`HELDOUT_VIDEO_INPUT_REQUIRED`

The designated input directory `data/realcam/heldout_v1/raw` did not exist at
the Phase 0 inventory time (`2026-07-12T13:20:49Z`). Consequently, zero files,
zero candidate videos, and zero accepted videos were available. The governing
stop rule requires stopping at Phase 0; downstream media, annotation,
agreement, adjudication, reference, split, and physical-sample work was not
performed.

## Evidence and status

- Videos found / accepted: `0 / 0`.
- Prior-video comparison: no held-out hash exists to compare. The forbidden
  strict video hash is recorded in `inventory/PRIOR_VIDEO_HASH_COMPARISON.csv`.
- Media/FPS compatibility: not assessed; no input video exists.
- Annotation packets: `0`; packets cannot be constructed without timelines.
- Independent annotations: none discoverable because the designated
  `annotations/incoming` directory is also absent.
- Agreement metrics: not available.
- Adjudication: not started.
- Final event/reference counts: not frozen / not applicable.
- Canonical-anchor validation: not run because no reference exists.
- Split/leakage: no split was constructed; input leakage remains untestable.
- <=100-call physical sample: not constructed, as required before reference
  freeze.
- Physical VLM calls: `0` in the bundle-local execution record. No external
  scheduler/call-ledger verification was available.
- EVENT_ENUMERATE and VERA were not invoked and Qwen3-VL was not loaded by
  this workflow, according to its execution record; external runtime proof was
  unavailable.
- Independent review: `PASS_WITH_CAVEATS`. It independently confirmed the
  filesystem stop condition and decision logic. It also found that no-input
  video independence is untestable, not passed, and that the no-execution
  claims above are bundle-local.

## Required next action

Place one or more genuinely new source videos under
`data/realcam/heldout_v1/raw/`. Preserve original bytes and provide provenance
and license/source information. Each video must be byte-disjoint from
`data/realcam/long_video_data/long_video_dataset3.mp4`, its exported clips, and
all other development/strict-benchmark videos. Do not add model-produced event
labels as human truth. After videos arrive, rerun this workflow from Phase 0.

No human packet/template can yet be named for completion because packet IDs
depend on the missing video timelines.
