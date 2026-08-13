# P1-B protocol review

## PASS

- Zero formal annotations and no human outcome seen.
- Historical region implementation was reconstructed and all 198 orientations reproduced.
- Anchor attribution, quantitative reference gate, source-level inference, primary LOVO, shared-control deduplication, and fail-closed state transitions are explicit.

## REQUIRES_AMENDMENT

- Pre-annotation v1.1 used overlap-any as primary attribution and did not fully specify the historical connected-component region semantics.
- Its reference gate omitted the requested count rule and IoU>0 matching fraction; LOVO and LOVQO were not ordered.
- Generic static serving required an allowlist privacy hardening.

These issues are amended in v1.2 before the first formal annotation.

## BLOCKING_ISSUES

None after v1.2 validation. Pair membership did not change.
