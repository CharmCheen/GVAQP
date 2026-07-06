# Oracle Usage Report

| Method | audit | discovery | repair | guard | total | guard_fraction |
|--------|-------|-----------|--------|-------|-------|----------------|
| B6 | 0 | 9735 | 0 | 0 | 9735 | 0.000 |
| B6-core | 0 | 6412 | 0 | 1957 | 8369 | 0.234 |
| B7 | 0 | 9735 | 0 | 0 | 9735 | 0.000 |
| B7-core | 0 | 8089 | 0 | 1069 | 9158 | 0.117 |
| LATE-AQP-core | 2009 | 4253 | 499 | 2212 | 8973 | 0.247 |

## Notes

- Guard calls are counted within the same total budget for core methods.
- LATE-AQP-core has non-zero audit/repair calls; B6/B7 spend all budget on discovery.
- Guard overhead is highest for core methods at low budgets.
