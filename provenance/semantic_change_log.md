# Semantic change log

| change | reason | old_behavior | new_behavior | behavior_preserving | validation |
|---|---|---|---|---|---|
| Rename `PublicScanState` to `CoverageState` and package to `garc` | Standalone API | Same immutable public fields | Same fields and policy inputs | yes | exhaustive SCAN parity test |
| Inline trusted coverage policies | Remove dependency on legacy `scan_headroom` subsystem | Delegated exact policy logic | Same midpoint, distance, and tie rules | yes | exhaustive SCAN parity test |
| Narrow fixed policy class to selected R4 | Exclude non-selected controller implementations | Multi-policy dispatch included R0-R7 | Only R4 public API | yes for R4 | fixed-ratio grid parity test |
| Split candidate generation/Frontier/CONFIRM/parsing/materialization/commit | Explicit complete online chain | Logic embedded in dataset-specific replay and physical runners | Frozen candidate binding and Frontier plus injected adapter, parsed/materialized event IDs, transactional action/final snapshots | yes over replay contract | Frontier and post-SCAN differential tests |
| Match causal q90 and global fallback | Deadline admission parity | Curated runner used nearest-rank estimates and constant fallback | Linear-interpolated q90 after observations; measured global manifest fallback before observations | yes over frozen valid domain | deadline differential tests |
| Add explicit failure atomicity and final STOP commit | Preserve last durable result | Exceptions could escape after partial in-memory mutation; no final durable state | Failed CONFIRM does not terminalize or append; commit precedes runtime terminalization; STOP/failure snapshot is fsync-committed | integration strengthening | failure injection and durable-result parity tests |
| Reject negative deadline estimates | Defensive validation outside frozen valid-cost domain | Negative values would compare as fitting | Invalid negative estimates do not fit | no, invalid-domain hardening | deadline test; no valid-domain mismatch |
| Replace pandas/numpy dataset runner with standard-library replay runner | Remove hard-coded data/output dependencies | Read legacy project tables and model outputs | Caller supplies portable replay manifest | not an equivalence claim for data loading; algorithm behavior preserved | differential semantics and CLI smoke tests |
| Generalize selected-Frontier input audit paths | Make research support portable | Fixed local media inventory | Caller-provided input/output directories | technical Gate intent preserved | registration and overlap tests |
