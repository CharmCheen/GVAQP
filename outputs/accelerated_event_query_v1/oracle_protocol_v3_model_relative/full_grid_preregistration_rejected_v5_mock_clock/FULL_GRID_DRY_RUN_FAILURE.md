# Full-Grid Dry-Run Failure — Rejected Seal V5

Decision: `REVISE_FULL_GRID_PREREGISTRATION`

Execution seal SHA-256:
`595a74dc93ce985bceb5b52c0e9f34fc14ea855e55b814d967c5577cea13ede9`

The 130-test suite passed, but the complete mock stopped before analysis with
`loaded-worker idle exceeded emergency reservation`. The mock opened all three
model-load sessions and then processed the canonical manifest serially by
video. HANGZHOU and WUHAN therefore accumulated the wall time required to
write hundreds of DALI mock records despite formal execution using three
parallel worker processes.

No formal output, approval, model load, inference call, or GPU-hour was
produced. The formal eight-second emergency reservation remains unchanged.
The mock must open each static worker session when its serialized shard begins,
then close and account its exit before advancing to the next shard.
