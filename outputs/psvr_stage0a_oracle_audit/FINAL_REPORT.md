# PSVR Stage 0A — Split Integrity and Capability Audit

`ORACLE_REFERENCE_INTEGRITY = PASS`

`RUNTIME_CAPABILITY_ISOLATION = PASS`

`STAGE_0A = PASS`

## Reference integrity

All 347 raw responses hash-verify and reparse through the frozen parser. The complete normalized observation table matches the saved table, and raw-derived materialization deterministically reconstructs all 26 reference events.

## Runtime capability boundary

The compliant runtime uses a process-isolated oracle service. Its launcher-owned accessor surface is exactly `query`, `queried_ids`, and `query_count`; the accessor is never passed to policy code. Selector/scheduler policy executes in a clean-spawn, empty-chroot worker after permanent uid/gid drop and receives only immutable public units, scanned proxy observations, and queried observations. Unchanged K3 executes in a separate clean-spawn worker with only public units and the queried trace. Real import, direct `open()`, stack, and GC attacks against evaluator/reference/cache state fail. Evaluation executes later in a separate process outside this boundary.

All 15 adversarial tests passed. At zero queries, visible labels and confirmed events are both zero; after 5 queries, exactly those 5 labels are visible. Full enumeration, reference access, and cache-path access fail.

The historical frozen runner remains unchanged for provenance but is quarantined from runtime use because its `load_frozen()` and legacy `.table` interface are unsafe.
