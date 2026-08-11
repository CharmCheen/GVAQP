# Full-Grid Tail Unit Audit

Status: `FROZEN_PASS_NO_MODEL_INFERENCE`

The three legal final units use only exact source-anchored `k/2` targets not
exceeding the true endpoint. No target, padding frame, repeated final frame,
or invented off-grid endpoint was added. The base query file remains unchanged;
for each tail, its exact model-visible text deterministically replaces the false
nominal 10-second sentence with the legal truncated-final identity, true source
duration, real frame count, 2-fps grid, and no-padding/no-repeat declaration.

| Unit | Video | Absolute interval | Frames | Last target | Ideal/resolved/decoded last index | Resolution | Contact SHA |
|---|---|---:|---:|---:|---:|---|---|
| DALI_u0566 | DALI | 5660.000000–5665.535333 | 12 | 5665.500000 | 169965/169961/169961 | nearest_available_final_video_frame | `9d5aff48f4ee936cf607dcca5a349a5a11eea44868e6d02d128fb49ff0e10001` |
| HANGZHOU_u0560 | HANGZHOU | 5600.000000–5600.566000 | 2 | 5600.500000 | 168015/168015/168015 | exact_ideal_cfr_index | `7abb5b2d1166039b682b73fe001c1ca918e99a5e8bc8afd321dafe339efa94a2` |
| WUHAN_u0346 | WUHAN | 3460.000000–3462.930499 | 6 | 3462.500000 | 103875/103875/103875 | exact_ideal_cfr_index | `50b09a06909e5d38f542d694de6a6c227525143fdb2a76278f8f3d4f7698c281` |

Processor-only audit:

- Status: `PASS_PROCESSOR_ONLY_NO_CHECKPOINT_WEIGHTS_LOADED_NO_INFERENCE`.
- Processor: `transformers.models.qwen3_vl.processing_qwen3_vl.Qwen3VLProcessor`.
- Checkpoint weights loaded: `false`; `model.generate` called: `false`.
- All 12/2/6-frame inputs produced deterministic tensor bundles without protocol padding.
- Exact tensor shapes and hashes are in `FULL_GRID_TAIL_PROCESSOR_AUDIT.json`.

Independent reviewers must inspect each PNG and the corresponding exact frame rows
in `FULL_GRID_FRAME_MANIFEST.json` before returning GO.
