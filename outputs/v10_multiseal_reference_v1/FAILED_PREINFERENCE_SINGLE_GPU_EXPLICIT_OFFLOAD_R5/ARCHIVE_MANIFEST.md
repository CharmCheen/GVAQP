# Failed Pre-Inference Single-GPU Explicit-Offload Attempt R5

Status: `SINGLE_GPU_PHYSICALLY_INFEASIBLE_IN_CURRENT_FROZEN_RUNTIME`.

The explicit map assigned `model.visual`, embeddings, and text layers 0–43 to
GPU, with text layers 44–63, final norm, and language-model head assigned to
CPU.  `accelerate.check_device_map` accepted that map.  However the frozen
Transformers FP8-dequantization loader groups wildcard layer weights during
conversion and materializes them on the GPU device of the group before it can
apply the CPU destination.  It again reached 78.00 GiB allocated and failed
on a further 250 MiB allocation.

No raw output, parsed semantic outcome, or authoritative checkpoint was
produced. `semantic_output_exposure = NONE`.  This is an execution-capacity
result, not a semantic compatibility result.
