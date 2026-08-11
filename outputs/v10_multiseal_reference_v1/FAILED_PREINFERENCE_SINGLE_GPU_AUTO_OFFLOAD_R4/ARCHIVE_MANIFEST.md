# Failed Pre-Inference Single-GPU Auto-Offload Attempt R4

Status: `FAILED_PREINFERENCE_EXECUTION_PLACEMENT`.

The automatic device-map planner retained the entire BF16 realization on the
single A100 because it estimated the FP8 checkpoint size before the runtime
dequantization.  Loading therefore again reached 78.11 GiB allocated and
failed before any oracle call.  No raw output, parsed semantic result, or
authoritative checkpoint exists in this seal.

`semantic_output_exposure = NONE`.  The successor uses an explicit frozen
layer map solely to force CPU offload of a fixed suffix of the same BF16 model.
