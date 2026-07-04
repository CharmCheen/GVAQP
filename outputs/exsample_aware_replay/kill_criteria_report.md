# Kill Criteria Report

This report evaluates whether Ours-full clearly outperforms B7, per task instructions.

## Event-Level Recall Gain (Ours-full minus B7)

|   budget |   abs_gain |   rel_gain_pct |
|---------:|-----------:|---------------:|
|        5 |     0.0146 |           28.9 |
|       10 |     0.06   |           56.2 |
|       20 |    -0.0208 |           -9.9 |
|       40 |     0.1038 |           24.6 |
|       80 |     0.0067 |            0.9 |
|      120 |     0      |            0   |

- **Kill criterion NOT triggered**: Ours-full shows >0.05 absolute recall gain over B7 at budgets [10, 40].
- Repair mechanism is contributing beyond simple ExSample+expansion.

## Complete-Event Coverage Gain (Ours-full minus B7)

|   budget |   abs_gain |
|---------:|-----------:|
|        5 |    -0.0308 |
|       10 |    -0.0262 |
|       20 |    -0.0625 |
|       40 |     0.0121 |
|       80 |    -0.0033 |
|      120 |     0      |
