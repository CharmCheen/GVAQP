# Data and provenance

No raw video is included. Runtime and examples accept caller-owned manifests. Selected-Frontier input auditing requires an original complete video and sibling `<video>.source.json` with hash binding, capture-session ID, immutable registration time, derivation declarations, and confirmation that target-event information was not used for selection.

The audit performs probe, full decode, deterministic random seeks, exact-hash/session checks, and sparse perceptual overlap detection. Passing sparse overlap checks cannot prove total independence; provenance evidence remains necessary. This is `RESEARCH_SUPPORT`, not runtime scheduling.

All scientific lineage points to source commit `5047241b0561b911b9a519b18e8e7591c0074e70`. See `provenance/migration_manifest.csv`, `omitted_legacy_manifest.csv`, and `source_snapshot.json`.
