# Single-GPU Feasibility Audit

Decision: `SINGLE_GPU_PHYSICALLY_INFEASIBLE_IN_CURRENT_FROZEN_RUNTIME`.

The frozen local checkpoint is `Qwen3-VL-32B-Instruct-FP8`.  On every
available A100-SXM4-80GB, its SM 8.0 capability triggers the frozen
Transformers runtime to dequantize the FP8 checkpoint to BF16.  The resulting
model-load footprint exceeds the 79.15 GiB usable capacity before any video
input or generation cache is allocated.

| Attempt | Execution-only placement | Result | Semantic exposure |
| --- | --- | --- | --- |
| R2 | whole model on GPU | 78.97 GiB allocated; failed on +250 MiB | none |
| R3 | whole model + `expandable_segments:True` | 78.17 GiB allocated; failed on +250 MiB | none |
| R4 | automatic CPU offload, 64 GiB target | FP8-size planner retained all weights; 78.11 GiB; failed | none |
| R5 | explicit fixed 44/64-layer GPU prefix, CPU suffix | FP8 conversion grouped tensors on GPU; 78.00 GiB; failed | none |

The R5 map was schema-checked by `accelerate.check_device_map`; the failure
is in the current Transformers FP8-to-BF16 weight-conversion loading path,
not in the topology binding.  Altering that loader or replacing the
checkpoint/runtime would no longer be the frozen execution semantics and is
not allowed by this amendment.

At the audit time, GPU 7 was the only completely idle A100.  The other A100s
had foreign compute contexts; no two-GPU exclusive topology was available.
No foreign process was terminated or modified.

Consequences:

* V9 admissibility remains `1454 / 1475`; the frozen missing set remains 21.
* The nine-unit shadow has not started semantic inference.
* Cross-seal compatibility is `NOT_RUN`, so missing-unit execution, reference
  release, P0, and any materializer decision are all prohibited.

Smallest next execution resource: two exclusive compatible A100-80GB GPUs
for a current V10-MS execution seal, or one compatible accelerator that can
hold the same BF16 realization with generation headroom.  This is a resource
requirement, not a request to change the model, prompt, parser, unitization,
or evaluation protocol.
