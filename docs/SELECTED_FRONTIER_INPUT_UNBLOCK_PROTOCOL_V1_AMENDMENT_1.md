# Selected-Frontier Input Unblock Protocol V1 — Amendment 1

Status: `FROZEN_BEFORE_ANY_CANDIDATE_REGISTRATION`

The initial pipeline verification found two ordering defects while the inbox
and immutable registry both still contained zero candidates. No candidate
technical audit, semantic access, Oracle call, or model run had occurred.

This amendment replaces only the discovery-order mechanics:

- Existing `registration_order` values are append-only and never recomputed.
- Assets first discovered in the same invocation are ordered by valid declared
  `registration_utc`, filename, then SHA-256, and receive the next ordinals.
- A later-discovered asset is always appended, even if its sidecar claims an
  earlier timestamp; backdating cannot reorder or displace prior candidates.
- Identity for discovery deduplication is `(registered path, SHA-256)`, not
  SHA-256 alone. Identical bytes at another path are registered and then fail
  the exact-duplicate independence check.
- Empty registration and failure ledgers are materialized at initialization so
  their absence cannot be mistaken for an audit omission.

All eligibility, replacement, semantic-prohibition, and PASS rules remain
unchanged.

