# Oracle Usage Report - dataset3

| Method | audit | discovery | repair | guard | total | guard_fraction |
|--------|-------|-----------|--------|-------|-------|----------------|
| B6 | 0 | 9425 | 0 | 0 | 9425 | 0.000 |
| B6-core | 0 | 7912 | 0 | 880 | 8792 | 0.100 |
| B7 | 0 | 9425 | 0 | 0 | 9425 | 0.000 |
| B7-core | 0 | 8432 | 0 | 606 | 9038 | 0.067 |
| LATE-AQP-core | 1051 | 6921 | 75 | 1112 | 9159 | 0.121 |

## Notes

- Guard calls are counted within the same total budget for core methods.
- LATE-AQP-core has non-zero audit/repair calls; B6/B7 spend all budget on discovery.
- Guard overhead is highest for core methods at low budgets.
