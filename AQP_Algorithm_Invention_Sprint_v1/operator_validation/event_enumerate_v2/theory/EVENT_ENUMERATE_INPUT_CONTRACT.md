# EVENT_ENUMERATE v2 input contract

Contract ID: `event_enumerate_v2_metadata_exact_v1`.

## Frozen purpose

The operator reads one padded interval and returns zero or more
`enter_ego_path` relations.  This contract does not plan intervals, execute
VERA's dynamic program, access evaluator labels, or compare algorithms.

## Canonical input path

There is exactly one path and no sampling-strategy grid:

1. Accept a source video, an input interval of at most 60 seconds, and its
   contained ownership core.
2. Read source FPS and frame count from OpenCV.
3. Select frames with the already used fixed-stride rule:
   `start=int(start_seconds*source_fps)`,
   `end=int(end_seconds*source_fps)` inclusive and capped, and
   `stride=max(1,int(source_fps/2.0))`.
4. Decode the scheduled frames sequentially as RGB and require exact scheduled
   frame identities.
5. Anchor local time at the actual first decoded frame timestamp.
6. Pass the RGB tensor directly to the local Qwen3-VL processor with explicit
   `VideoMetadata` containing relative *source-frame* indices and original
   source FPS.
7. Pass `do_sample_frames=False`; a second sampling operation is forbidden.
8. Require the processor-visible timestamp sequence and temporal grid to equal
   the independently computed two-frame-patch sequence.
9. Use the byte-identical v1 enumeration prompt.  Only the clip-duration
   placeholder changes per input; its value is the actual sampled span rounded
   to one decimal as the processor itself displays timestamps.
10. Generate greedily with at most 768 new tokens and parse without repair.
11. Map relative seconds by adding the actual first decoded timestamp, apply
    the existing midpoint single-owner rule, and exactly deduplicate identical
    rows only.

## Frozen values

| Field | Value |
|---|---:|
| target sampling rate | 2 FPS |
| maximum input span | 60.0 seconds |
| maximum decoded frames | 121 |
| temporal patch size | 2 |
| prompt timestamp precision | 0.1 seconds |
| prompt hash | `ffb65213017a79b5312bce98d5cf9a3d270cf69347ed560176119be347167bc8` |
| generation | greedy, `do_sample=false`, max 768 new tokens |
| retries | 0 |
| physical batch size | 1 |

The 121-frame limit includes the old VERA physical operator lengths: 50-second
cores with up to five seconds of guard context on each side, including the
nominal 60-second case and a shorter final partial interval.

## Metadata invariants

- `video_metadata` is mandatory and its FPS must equal probed source FPS.
- Metadata frame offsets start at zero and strictly increase.
- Metadata offset count equals decoded tensor length.
- Processor sampling is false.
- `video_grid_thw[0] == ceil(decoded_frame_count/2)`.
- The tokenized timestamp list equals the proof-generated list exactly after
  the processor's one-decimal formatting.
- No timestamp is silently rescaled, clamped, or inferred from model output.
- Frame, tensor, metadata, prompt, and serialized-chat hashes are recorded.

## Output and parser invariants

The top-level JSON status is `ok` or `abstain`.  An `ok` result may contain an
empty list.  Each event must be chronological, finite, inside the transported
clip duration (with only the explicit 0.050001-second display tolerance), and
must satisfy the frozen schema.  The parser does not add missing fields,
change event types, reorder events, repair JSON, clamp boundaries, or inspect
references.

## Failure behavior

Missing metadata, frame mismatch, timestamp mismatch, tensor/grid mismatch,
processor warning, parse error, out-of-range boundary, model/resource error,
or missing audit record is a failed operator call.  There is no retry and no
alternative sampling path.  If a semantic gate is eventually run, failed or
abstaining calls are scored as producing no true events while any returned
invalid rows are not rescued.  Exact evaluator handling must be preregistered
with the held-out call matrix before the first physical call.

## Separation from evaluator data

Inference code accepts only video bytes, interval/core timestamps, the frozen
prompt, processor configuration, and generation configuration.  It contains
no event-reference path, reference count, event stratum, or expected label.
Evaluator references must live in a separately permissioned file.  The
current gate stops before that file exists.

