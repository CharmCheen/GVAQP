# Metadata-correct EVENT_ENUMERATE operator gate v2 — final report

## Exact decision

`HELDOUT_DATA_REQUIRED`.

The processor gate passes, but zero local candidate populations satisfy the
held-out-reference requirements.  Under the preregistered stop rule, no
physical Qwen3-VL generation call, semantic metric, or corrected cost
measurement is permitted.

## 1–4. Cause, corrected contract, and metadata tests

The exact old compression cause is the v1 invocation at
`src/garc_eval/aqp_invention_v1/run_physical.py:153-157`.  It called
`process_vision_info(messages)` without requesting returned video metadata or
video kwargs, then called the processor without `video_metadata` and without
`do_sample_frames=False`.  The message-level `fps` field at line 148 did not
reach the processor.  For each nominal 60-second call, 121 decoded frames were
padded to 122; missing source FPS defaulted to 24; default 2-FPS sampling
reduced the tensor to `int(122/24*2)=10` frames; five temporal-patch timestamp
tokens ended at 4.8 displayed seconds while the prompt still declared 60.0.

This causal reconstruction is supported by preserved schedules, frame
identities, raw-response hashes, the saved processor warning, and the pinned
current dependency source.  A processor-only sentinel reproduces the exact
old helper-to-processor call signature, and all 68 nominal saved calls match
the reconstructed shape.  The exact old dependency image, serialized chat,
processor metadata object, model-input tensors, and temporal position IDs were
not preserved, and old model generation was not rerun.

The corrected contract retains the one old fixed-stride 2-FPS selection,
passes original source FPS plus relative source-frame indices in explicit
`VideoMetadata`, disables processor resampling, requires exact timestamp-token
and grid identity, maps model-relative seconds from the actual first decoded
frame, reuses the byte-identical v1 prompt, and parses without repair or
clamping.  Maximum input length is 60 seconds/121 decoded frames.

Metadata result: `25/25 PASS`, zero failures, zero
errors, zero skips.  The pre-execution audit has
`15/15 PASS` entries.  The
nominal corrected input retains 121 frames as 61 temporal patches spanning
0.2 (display-rounded first patch center) through 60.0 seconds.  Beginning,
middle, end, nonzero-offset, odd-count, alternate-FPS, and final-partial cases
pass.  Batch and single processor preparation are byte-equivalent after
splitting their concatenated tensors.

The old-call coordinate-warp table is diagnostic only: it maps generated
coordinates between exact processor patch centers and is explicitly excluded
from semantic boundary localization.  No event-localization value is inferred
from that table.

## 5. Held-out videos and reference

Accepted held-out videos: **none**.  Accepted reference: **none**.

- Nexar: 200 positive and 403 negative local clips, but the metadata labels
  one collision/near-collision alert-to-event interval and is not exhaustive
  for every `enter_ego_path` event or multi-event intervals.
- DrivingDojo-mini: 32 disjoint frame sequences with camera/ego-motion data,
  but no target-event relation.
- DoTA and DADA-2000: mapping notes only; raw/reference files absent locally.
- Micro-CASQ-v0: empty annotation template and no video population.
- Other references: strict-video-derived, VLM pseudo-references,
  development-used, non-exhaustive, or missing their raw source.

## 6–10. Calls, semantic results, and cost

| Result | Value |
|---|---:|
| New physical Qwen3-VL calls | 0 |
| Event precision / recall / F1 | NOT MEASURED |
| Multi-event recall | NOT MEASURED |
| Boundary localization | NOT MEASURED |
| Corrected enumerator GPU / wall cost | NOT MEASURED |
| Matched dense GPU / wall cost | NOT MEASURED |
| Cost ratio | NOT MEASURED |

The previous 0.240987 compressed-input GPU ratio is not reused.
Zero-call evidence is bundle-local (empty attempt directory, header-only call
ledger, runtime ledger, and no-call status); no external scheduler audit was
available.

## 11. VERA physical viability

VERA physical execution is **unresolved and not currently authorized**.  The
old physical instantiation remains falsified.  The corrected processor path
removes a demonstrated transport defect, but it supplies no evidence that the
operator meets recall/F1 or beats matched dense cost.  Therefore VERA cannot
yet be called viable or intrinsically nonviable.

## 12. Independent review

Independent-review result: `PASS_WITH_CAVEATS`.  Full checks and reviewed
hashes are in `audit/INDEPENDENT_ADVERSARIAL_REVIEW.json` when present.

## 13. Exact next task

Acquire or create, without using EVENT_ENUMERATE/VERA outputs as truth, a
byte-disjoint video population with an independently adjudicated exhaustive
`enter_ego_path` event relation and reviewed negative coverage.  Freeze its
provenance and evaluator-only reference.  Before labels are exposed to the
inference path, verify every source FPS/frame count is compatible with the
frozen <=121-frame selection rule; if not, refreeze one event-independent
selection rule and repeat the processor audit.  Then freeze the smallest
<=100-call enumeration-plus-matched-dense matrix and rerun the unchanged
processor audit before the first physical call.

## Scientific interpretation

Strongest supported conclusion: the old temporal transport was wrong and the
new transport is processor-correct.  Main competing explanation for the old
quality failure: intrinsic semantic weakness of 2-FPS long-window
enumeration, which the current zero-call gate cannot test.  Key uncertainty:
semantic recall/F1 and matched cost on an independent population.  Reject or
revise the operator hypothesis if a valid held-out run falls below recall
0.80 or F1 0.80, or if corrected GPU cost is not strictly below matched dense
execution.
