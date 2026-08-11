# Failed Pre-Inference Single-GPU Allocator Attempt R3

Status: `FAILED_PREINFERENCE_SINGLE_GPU_CAPACITY`.

With `PYTORCH_ALLOC_CONF=expandable_segments:True`, the frozen checkpoint
still required 78.17 GiB allocated on the 79.15 GiB visible A100 and failed
during model loading with a further 250 MiB request.  This establishes that
the all-on-GPU BF16 placement does not fit; it is not allocator fragmentation.

No raw output, parsed semantic outcome, or authoritative checkpoint was
produced. `semantic_output_exposure = NONE`.  The successor may alter only
execution placement (CPU offload); it retains the same model weights, BF16
dtype, processor, prompt, generation configuration, parser, and unit inputs.
