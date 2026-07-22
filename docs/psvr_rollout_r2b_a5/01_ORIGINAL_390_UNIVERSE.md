# Original 390-identity universe

`outputs/psvr_rollout_r2b_dev/H1B_DEVELOPMENT_COVERAGE_MATRIX.json` is the
original frozen registry.  It contains 13 unique rows.  The fixed public seed
registry has six values and the declared method registry has five identities;
the materialized product is therefore `13 × 6 × 5 = 390` unique identities.

The full materialization and hashes are in
`outputs/psvr_rollout_r2b_a5/A5_AUTHORIZED_IDENTITY_UNIVERSE.json` and
`A5_DEVELOPMENT_UNIVERSE_MANIFEST.json`.  This preserves the original registry;
it does not authorize a new run.
