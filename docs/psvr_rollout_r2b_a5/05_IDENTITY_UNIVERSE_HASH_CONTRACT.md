# Identity-universe hash contract

The A5 hash is SHA-256 over canonical JSON containing the seed registry,
scientific configuration registry, method registry, canonical identity schema,
Cartesian-product rule, and parent-lineage commitment.  Every identity carries
both this `development_universe_hash` and `canonical_lineage_hash`; the manifest
also records a hash of the fully materialized identity list.

This fixes the old failure mode where only a sparse seed specification was
hashed.  A hash binding the original 390 set does not resolve the separate
authorization conflict, so it must not be read as an execution freeze.
