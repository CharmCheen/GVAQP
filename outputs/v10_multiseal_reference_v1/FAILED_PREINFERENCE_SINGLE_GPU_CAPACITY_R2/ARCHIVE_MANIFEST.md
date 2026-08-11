# Failed Pre-Inference Single-GPU Capacity Attempt R2

Status: `FAILED_PREINFERENCE_SINGLE_GPU_CAPACITY`.

The single-GPU topology binding was correct: model loading began with GPU 7
visible as `cuda:0`.  The frozen FP8 checkpoint was dequantized to BF16 on
the A100 (SM 8.0), reached 78.97 GiB allocated of 79.15 GiB, and failed while
requesting a further 250 MiB.  No raw output, parsed semantic outcome, or
authoritative checkpoint was produced.

`semantic_output_exposure = NONE`.  This archive is not a semantic attempt
and is retained only as execution-capacity provenance.  The successor
amendment adds allocator configuration as frozen execution-only provenance;
the semantic contract is unchanged.
