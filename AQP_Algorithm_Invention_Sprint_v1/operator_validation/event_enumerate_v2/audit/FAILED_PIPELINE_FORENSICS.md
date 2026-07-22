# Failed pipeline forensics

## Strongest supported conclusion

The v1 runner transported the correct scheduled source frames into
`qwen-vl-utils`, but it did not transport their temporal metadata into the
Qwen3-VL processor.  The exact responsible invocation is
`src/garc_eval/aqp_invention_v1/run_physical.py:153-157`: it calls
`process_vision_info(messages)` without `return_video_kwargs=True` or
`return_video_metadata=True`, then calls `processor(...)` without
`video_metadata` and without `do_sample_frames=False`.  The `fps` field at
line 148 is merely message data and is absent from the processor call.

## Observed evidence

- The preserved runtime log records the installed processor warning that no
  metadata was provided and source FPS was defaulted to 24.
- All 70 started checkpoints contain exact decoded frame identities matching
  the frozen schedules; 68 calls have a nominal 60-second input and 121
  decoded frames.
- The 70 complete checkpoints and raw-response hashes verify; they contain
  51 parsed event reports in total.
- The old runner saved token counts but did **not** save per-call processor
  metadata, serialized chat text, input tensors, tensor hashes, or temporal
  position IDs.  Those absences are explicit in `INPUT_MANIFEST.csv`.

## Reconstructed mechanism

For a nominal 60-second call, `qwen-vl-utils` first pads 121 frames to 122.
Because processor metadata is missing, `Qwen3VLVideoProcessor.sample_frames`
sets source FPS to 24 and applies its default target of 2 FPS:
`int(122 / 24 * 2) = 10`.  It selects 10 tensor positions and the Qwen3-VL
processor averages each pair for five temporal patches.  The timestamp tokens
therefore end at [4.770833333] seconds rather than approximately 60 seconds;
the consumed-frame counts across nominal calls are [10].

The prompt still declares 60.0 seconds.  Thus prompt prose, visual content,
and processor timestamp tokens disagree.  The exact per-call schedules,
visible timestamps, actual source patch timestamps, generated timestamps, old
absolute mapping, and a label-independent coordinate-warp diagnostic are in
`OLD_CALL_TIMELINE_RECONSTRUCTION.csv`.  Its normalized boundary table is
`OLD_COORDINATE_WARP_DIAGNOSTICS.csv`: it contains
102 generated boundaries,
67 inside the exact
processor-visible coordinate span and
35 outside.

## Derived conclusion and uncertainty

The temporal compression itself is artifact/source-supported under the pinned
current dependencies and is reproduced by `test_old_compression_regression.py`.
That suite now includes a processor-only sentinel through the exact old helper
and processor call signature, plus a check over all 68 nominal saved calls.
It does not rerun old model generation.  The coordinate-warp columns are **not
semantic ground truth**: they linearly map generated coordinates between exact
processor patch centers to quantify the coordinate contradiction.  A model
could instead follow the contradictory 60-second prose, so the diagnostic is
excluded from event-localization accuracy.

The exact dependency versions were not written into the old run metadata.
The current local source is `transformers 5.10.0.dev0` at commit
`effde20942e3f82a1b97449f60b3a48c5ff96145` and `qwen-vl-utils 0.0.14`;
its behavior matches the preserved warning and token/frame evidence.  This is
strong reproduction evidence, but not a saved v1 environment image.

## Mapping and ownership path

The old evaluator adds `task.input_start` to model-relative event boundaries
in `evaluate_physical.py`, then applies midpoint ownership to half-open cores.
Because the coordinate system was compressed before inference, this mapping
could shift model-visible content far outside its true source time and reject
otherwise reported fragments at the ownership gate.  No v1 artifact is
modified or reinterpreted as a corrected physical cost measurement.
