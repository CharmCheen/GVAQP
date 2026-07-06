# Trigger Activation Check — Frozen-LATE-AQP-v2

For budgets ≤ 20, v2 should skip audit/repair and use the full budget for discovery.

| Segment | Budget | Trial | audit_calls | discovery_calls | repair_calls | Path activated |
|---------|--------|-------|-------------|-----------------|--------------|----------------|
| realcartest_0_1570 | 5 | 0 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_0_1570 | 5 | 1 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_0_1570 | 5 | 2 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_0_1570 | 5 | 3 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_0_1570 | 5 | 4 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_0_1570 | 10 | 0 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_0_1570 | 10 | 1 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_0_1570 | 10 | 2 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_0_1570 | 10 | 3 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_0_1570 | 10 | 4 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_0_1570 | 20 | 0 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_0_1570 | 20 | 1 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_0_1570 | 20 | 2 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_0_1570 | 20 | 3 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_0_1570 | 20 | 4 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_0_1570 | 40 | 0 | 10 | 27 | 3 | v1_audit_repair |
| realcartest_0_1570 | 40 | 1 | 10 | 26 | 4 | v1_audit_repair |
| realcartest_0_1570 | 40 | 2 | 4 | 36 | 0 | v1_audit_repair |
| realcartest_0_1570 | 40 | 3 | 4 | 36 | 0 | v1_audit_repair |
| realcartest_0_1570 | 40 | 4 | 4 | 36 | 0 | v1_audit_repair |
| realcartest_0_1570 | 80 | 0 | 20 | 57 | 3 | v1_audit_repair |
| realcartest_0_1570 | 80 | 1 | 20 | 55 | 5 | v1_audit_repair |
| realcartest_0_1570 | 80 | 2 | 20 | 58 | 2 | v1_audit_repair |
| realcartest_0_1570 | 80 | 3 | 20 | 51 | 9 | v1_audit_repair |
| realcartest_0_1570 | 80 | 4 | 20 | 51 | 9 | v1_audit_repair |
| realcartest_0_1570 | 120 | 0 | 30 | 84 | 6 | v1_audit_repair |
| realcartest_0_1570 | 120 | 1 | 30 | 83 | 7 | v1_audit_repair |
| realcartest_0_1570 | 120 | 2 | 30 | 85 | 5 | v1_audit_repair |
| realcartest_0_1570 | 120 | 3 | 30 | 79 | 11 | v1_audit_repair |
| realcartest_0_1570 | 120 | 4 | 30 | 79 | 11 | v1_audit_repair |
| realcartest_2000_3200 | 5 | 0 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 5 | 1 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 5 | 2 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 5 | 3 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 5 | 4 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 10 | 0 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 10 | 1 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 10 | 2 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 10 | 3 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 10 | 4 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 20 | 0 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 20 | 1 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 20 | 2 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 20 | 3 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 20 | 4 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_2000_3200 | 40 | 0 | 10 | 26 | 4 | v1_audit_repair |
| realcartest_2000_3200 | 40 | 1 | 10 | 26 | 4 | v1_audit_repair |
| realcartest_2000_3200 | 40 | 2 | 4 | 36 | 0 | v1_audit_repair |
| realcartest_2000_3200 | 40 | 3 | 10 | 26 | 4 | v1_audit_repair |
| realcartest_2000_3200 | 40 | 4 | 4 | 36 | 0 | v1_audit_repair |
| realcartest_2000_3200 | 80 | 0 | 20 | 50 | 10 | v1_audit_repair |
| realcartest_2000_3200 | 80 | 1 | 20 | 53 | 7 | v1_audit_repair |
| realcartest_2000_3200 | 80 | 2 | 20 | 56 | 4 | v1_audit_repair |
| realcartest_2000_3200 | 80 | 3 | 6 | 74 | 0 | v1_audit_repair |
| realcartest_2000_3200 | 80 | 4 | 6 | 74 | 0 | v1_audit_repair |
| realcartest_2000_3200 | 120 | 0 | 30 | 79 | 11 | v1_audit_repair |
| realcartest_2000_3200 | 120 | 1 | 30 | 82 | 8 | v1_audit_repair |
| realcartest_2000_3200 | 120 | 2 | 30 | 82 | 8 | v1_audit_repair |
| realcartest_2000_3200 | 120 | 3 | 6 | 114 | 0 | v1_audit_repair |
| realcartest_2000_3200 | 120 | 4 | 6 | 114 | 0 | v1_audit_repair |
| realcartest_3200_3830 | 5 | 0 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 5 | 1 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 5 | 2 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 5 | 3 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 5 | 4 | 0 | 5 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 10 | 0 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 10 | 1 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 10 | 2 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 10 | 3 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 10 | 4 | 0 | 10 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 20 | 0 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 20 | 1 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 20 | 2 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 20 | 3 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 20 | 4 | 0 | 20 | 0 | cold_start_fallback |
| realcartest_3200_3830 | 40 | 0 | 10 | 26 | 4 | v1_audit_repair |
| realcartest_3200_3830 | 40 | 1 | 10 | 27 | 3 | v1_audit_repair |
| realcartest_3200_3830 | 40 | 2 | 10 | 28 | 2 | v1_audit_repair |
| realcartest_3200_3830 | 40 | 3 | 4 | 36 | 0 | v1_audit_repair |
| realcartest_3200_3830 | 40 | 4 | 4 | 36 | 0 | v1_audit_repair |
| realcartest_3200_3830 | 80 | 0 | 20 | 39 | 4 | v1_audit_repair |
| realcartest_3200_3830 | 80 | 1 | 20 | 38 | 5 | v1_audit_repair |
| realcartest_3200_3830 | 80 | 2 | 20 | 39 | 4 | v1_audit_repair |
| realcartest_3200_3830 | 80 | 3 | 6 | 57 | 0 | v1_audit_repair |
| realcartest_3200_3830 | 80 | 4 | 6 | 57 | 0 | v1_audit_repair |
| realcartest_3200_3830 | 120 | 0 | 30 | 30 | 3 | v1_audit_repair |
| realcartest_3200_3830 | 120 | 1 | 30 | 27 | 6 | v1_audit_repair |
| realcartest_3200_3830 | 120 | 2 | 30 | 30 | 3 | v1_audit_repair |
| realcartest_3200_3830 | 120 | 3 | 6 | 57 | 0 | v1_audit_repair |
| realcartest_3200_3830 | 120 | 4 | 6 | 57 | 0 | v1_audit_repair |

## Summary

- realcartest_0_1570 B=5: 5/5 trials activated cold_start_fallback (audit=0, repair=0).
- realcartest_0_1570 B=10: 5/5 trials activated cold_start_fallback (audit=0, repair=0).
- realcartest_0_1570 B=20: 5/5 trials activated cold_start_fallback (audit=0, repair=0).
- realcartest_2000_3200 B=5: 5/5 trials activated cold_start_fallback (audit=0, repair=0).
- realcartest_2000_3200 B=10: 5/5 trials activated cold_start_fallback (audit=0, repair=0).
- realcartest_2000_3200 B=20: 5/5 trials activated cold_start_fallback (audit=0, repair=0).
- realcartest_3200_3830 B=5: 5/5 trials activated cold_start_fallback (audit=0, repair=0).
- realcartest_3200_3830 B=10: 5/5 trials activated cold_start_fallback (audit=0, repair=0).
- realcartest_3200_3830 B=20: 5/5 trials activated cold_start_fallback (audit=0, repair=0).

**All B≤20 trials activated cold_start_fallback: Yes**

Interpretation: If 'No', then v2 did not actually behave differently from v1 on those trials, and any observed similarity between v1 and v2 is because the fallback path was not taken.
