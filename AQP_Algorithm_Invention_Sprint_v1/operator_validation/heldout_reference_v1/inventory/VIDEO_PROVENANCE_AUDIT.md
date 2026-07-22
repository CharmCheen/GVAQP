# Video provenance audit

Status: `FAIL_NO_INPUT`.

At `2026-07-12T13:20:49Z`, the required directory
`data/realcam/heldout_v1/raw` was absent. No candidate filename, byte size,
hash, media metadata, source, license, or development-use history can be
recorded. The strict benchmark hash is preserved in the comparison table, but
the requirement that every held-out hash differ from every prior video hash
cannot be evaluated until held-out files exist.

This is evidence of missing input, not evidence of video independence.
