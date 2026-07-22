# Qwen3-VL temporal semantics — exact local audit

## Scope and evidence classes

This document describes the exact local Qwen3-VL input path used by the v2
operator gate.  It does not infer processor behavior from model answers.

Observed local evidence:

- model: `models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct`;
- Transformers: `5.10.0.dev0`, installed from commit
  `effde20942e3f82a1b97449f60b3a48c5ff96145`;
- `qwen-vl-utils`: `0.0.14`;
- video config: patch size 16, temporal patch size 2, spatial merge size 2,
  shortest edge 4096 pixels, longest edge 25,165,824 pixels;
- model text context: 262,144 positions;
- installed video-processor defaults: target 2 FPS, minimum 4 frames,
  maximum 768 frames, and `do_sample_frames=True`;
- all relevant local source and configuration hashes are recorded in
  `audit/SOURCE_MANIFEST.csv` and `config/MODEL_FILE_MANIFEST.csv`.

Primary external documentation:

- The [official Qwen3-VL repository](https://github.com/QwenLM/Qwen3-VL)
  explicitly says Qwen3-VL callers should request both returned video kwargs
  and video metadata, split `(video, metadata)` pairs, pass
  `video_metadata=...`, and pass the helper's `do_sample_frames=False` kwargs.
- The [official Transformers Qwen3-VL documentation](https://huggingface.co/docs/transformers/model_doc/qwen3_vl)
  defines `video_metadata`, `do_sample_frames`, `fps`, and `num_frames`, and
  states that FPS-based sampling requires metadata.
- The [official Qwen vision helper source](https://github.com/QwenLM/Qwen3-VL/blob/main/qwen-vl-utils/src/qwen_vl_utils/vision_process.py)
  returns `{'do_sample_frames': False}` only when callers request video kwargs
  and returns video metadata only when explicitly requested.

The external sources establish the intended public contract.  The installed
source is authoritative for this run's exact arithmetic.

## How video FPS is passed

`VideoMetadata` contains `total_num_frames`, `fps`, `duration`, and
`frames_indices`.  When an already decoded tensor is passed with
`do_sample_frames=False`, `frames_indices` still controls the timestamp tokens
that Qwen3-VL inserts around temporal patches.  The v2 adapter supplies:

```text
video_metadata.fps = original source-video FPS
video_metadata.frames_indices = selected source frame index - first selected source frame index
video_metadata.total_num_frames = last relative source index + 1
do_sample_frames = false
```

This represents fixed-stride and irregular source-frame selections exactly.
It is more precise than assigning the selected tensor an approximate 2 FPS,
especially for a source whose reported FPS is not exactly 30.

## Temporal grid and timestamp derivation

The installed `Qwen3VLVideoProcessor` pads an odd number of selected frames by
repeating the final visual frame, then groups frames in temporal patches of
two.  `Qwen3VLProcessor._calculate_timestamps` independently repeats the last
metadata index when needed and computes, for each pair `(i,j)`:

```text
timestamp = ((frames_indices[i] / source_fps)
           + (frames_indices[j] / source_fps)) / 2
```

Each value is serialized as `<t.t seconds>` with one decimal place immediately
before that patch's vision tokens.  A 121-frame, 60-second input at 2 FPS has
61 temporal patches: the first timestamp is approximately 0.25 seconds and
the repeated final frame produces an exact 60.0-second final timestamp.

The model input `video_grid_thw[0]` is `(61,H,W)` for this case.  The tests
compare the decoded input-token timestamp sequence, grid, pixel tensor, and
metadata against the independently calculated values.

## Fixed-frame sampling and the v1 failure

Fixed-frame selection does not itself compress time.  Compression occurs if
the selected tensor is passed without its source metadata while processor
sampling remains enabled.  In v1, `qwen-vl-utils` padded 121 frames to 122,
then the Qwen video processor treated those as 122 frames at a default source
rate of 24 FPS and requested 2 FPS:

```text
int(122 / 24 * 2) = 10 processor-consumed frames
```

Those ten positions become five timestamped patches ending at 4.8 displayed
seconds.  The saved warning, local source, exact arithmetic, and regression
test all agree.  The prompt nevertheless declared 60.0 seconds.

## Temporal position IDs and `second_per_grid`

Qwen3-VL does not use the Qwen2-VL `second_per_grid_ts` interface.  The local
model source explicitly notes its removal.  Timestamp text separates temporal
vision patches; the model's multimodal position construction splits
`video_grid_thw` into one-frame grids around those separators.  Consequently,
real seconds are transported primarily by explicit timestamp text and correct
frame-to-metadata alignment, not by a hidden seconds-per-grid scalar.

## Limits, spatial resizing, and truncation

- The local sampling path caps sampled videos at 768 frames, but v2 disables
  processor sampling and independently caps decoded inputs at 121 frames.
- With sampling disabled, the processor does not silently truncate frames.
  It may reduce spatial resolution via `smart_resize` to respect the configured
  25,165,824 total video-pixel bound.
- The tokenizer is called without truncation.  If a model input or generation
  exceeds a hard model/resource limit, the call must fail and be scored under
  the frozen failure policy; truncation is not an allowed recovery.
- The frozen 121-frame maximum is far below the local 768-frame sampling cap
  and the model's 262,144-position context, but actual input-token count is
  still logged per call because spatial tokenization depends on resolution.

## Batching

The processor supports multiple text/video/metadata rows.  It concatenates
vision patches and pads text rows.  The pre-execution test splits concatenated
vision tensors using `prod(video_grid_thw)` and requires byte-identical
per-video pixel tensors plus identical active input IDs between batch and
single preparation.  Physical execution, if later authorized, is frozen to
batch size one so timing and failure attribution remain per call.

## Generated time convention

Qwen3-VL has no guaranteed structured-output time unit.  The frozen prompt
defines output boundaries as numeric seconds relative to the sampled clip
start.  The deterministic parser accepts only that schema.  Absolute mapping
adds the actual first decoded source-frame timestamp, never the nominal
interval start.  This convention is an operator contract; semantic accuracy
remains unmeasured until a valid disjoint reference exists.

