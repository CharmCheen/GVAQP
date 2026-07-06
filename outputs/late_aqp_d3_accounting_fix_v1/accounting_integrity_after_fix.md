# Accounting Integrity After Fix

## Dry-run result

Across 12 dry-run trials, `duplicate_query_after_audit_repair_count` is **0**.

## Duplicate comparison (seed 0)

- Original D3-core mean duplicate calls per trial: 11.21
- Fixed D3-core mean duplicate calls per trial: 0.51
- D3-norepair mean duplicate calls per trial: 0.65

## Verdict

**PASS.** The queried-state accounting bug is fixed. Discovery no longer re-queries audit/repair bins.
