# Multi-Seal Recovery Decision

Decision: `TRUE_BLOCKER — SINGLE_GPU_PHYSICALLY_INFEASIBLE_IN_CURRENT_FROZEN_RUNTIME`.

* V9 admissible outcomes: `1454 / 1475`.
* Frozen missing set: `21` (`566d27190e3d724febd4ec70aadf55f40b4d960962136a245a00b5545c19e024`).
* New semantic outputs: `0`.
* Cross-seal compatibility: `NOT_RUN`.
* P0 authorization: `NO`.

The frozen FP8 checkpoint is dequantized to BF16 on A100 SM 8.0 and its
load-time realization exceeds a single A100-80GB.  Four execution-only
placements, including allocator and CPU-offload variants, failed before an
oracle call.  Details: `SINGLE_GPU_FEASIBILITY_AUDIT.md`.

Minimum resource to resume without changing semantics: two exclusive
compatible A100-80GB GPUs for a newly frozen current V10-MS seal, or one
compatible larger accelerator with enough BF16 model plus generation headroom.
