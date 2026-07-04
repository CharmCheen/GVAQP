# Budget Accounting Audit

All methods were run with the same oracle-call budgets. This report checks that actual consumption matches the target.

- Max absolute discrepancy: 0.00%
- Cases exceeding 5% tolerance: 0
- **Status: GREEN** — all methods consumed exactly their target budget.

## Per-Method Budget Consumption Summary

| method                     |   n_settings |   min_discrepancy_pct |   max_discrepancy_pct |   mean_discrepancy_pct |
|:---------------------------|-------------:|----------------------:|----------------------:|-----------------------:|
| B6_ExSample                |          180 |                     0 |                     0 |                      0 |
| B7_ExSample_plus_expansion |          720 |                     0 |                     0 |                      0 |
| Ours_full_LATE_AQP         |          180 |                     0 |                     0 |                      0 |

## Ours-full Ledger Breakdown (sample)

| e0_pct   |   budget |   trial |   budget_used |   n_audit |   n_discovery |   n_repair |   p_in_hat |   p_out_hat |   L_out_hat_s |
|:---------|---------:|--------:|--------------:|----------:|--------------:|-----------:|-----------:|------------:|--------------:|
| top10    |        5 |       0 |             5 |         1 |             4 |          0 |          0 |           1 |          1080 |
| top10    |        5 |       1 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
| top10    |        5 |       2 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
| top10    |        5 |       3 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
| top10    |        5 |       4 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
| top10    |        5 |       5 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
| top10    |        5 |       6 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
| top10    |        5 |       7 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
| top10    |        5 |       8 |             5 |         1 |             4 |          0 |          0 |           1 |          1080 |
| top10    |        5 |       9 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
| top20    |        5 |       0 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
| top20    |        5 |       1 |             5 |         1 |             4 |          0 |          0 |           0 |             0 |
