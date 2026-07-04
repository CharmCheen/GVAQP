# Error Cases and Anomalies

- No budget mismatch cases detected.

## Zero-Selected-Precision Cases
- 35 trials selected only negative bins.
| method                     |   chunk_size_s |   k |   e0_pct |   budget |   trial |
|:---------------------------|---------------:|----:|---------:|---------:|--------:|
| B6_ExSample                |             30 | nan |      nan |        5 |       1 |
| B6_ExSample                |             30 | nan |      nan |        5 |       8 |
| B6_ExSample                |             60 | nan |      nan |        5 |       3 |
| B6_ExSample                |             60 | nan |      nan |        5 |       4 |
| B6_ExSample                |             60 | nan |      nan |        5 |       6 |
| B6_ExSample                |             60 | nan |      nan |        5 |       8 |
| B7_ExSample_plus_expansion |             30 |   1 |      nan |        5 |       0 |
| B7_ExSample_plus_expansion |             30 |   1 |      nan |        5 |       6 |
| B7_ExSample_plus_expansion |             30 |   2 |      nan |        5 |       0 |
| B7_ExSample_plus_expansion |             30 |   2 |      nan |        5 |       6 |
| B7_ExSample_plus_expansion |             30 |   3 |      nan |        5 |       0 |
| B7_ExSample_plus_expansion |             30 |   3 |      nan |        5 |       6 |
| B7_ExSample_plus_expansion |             30 |   5 |      nan |        5 |       0 |
| B7_ExSample_plus_expansion |             30 |   5 |      nan |        5 |       6 |
| B7_ExSample_plus_expansion |             60 |   1 |      nan |        5 |       1 |
| B7_ExSample_plus_expansion |             60 |   1 |      nan |        5 |       2 |
| B7_ExSample_plus_expansion |             60 |   2 |      nan |        5 |       1 |
| B7_ExSample_plus_expansion |             60 |   2 |      nan |        5 |       2 |
| B7_ExSample_plus_expansion |             60 |   3 |      nan |        5 |       1 |
| B7_ExSample_plus_expansion |             60 |   3 |      nan |        5 |       2 |

## High Duplicate-Rate Cases
- 15 trials had duplicate_rate > 2.0 (many bins covering the same few events).
| method                     |   budget |   trial |   duplicate_rate |
|:---------------------------|---------:|--------:|-----------------:|
| B7_ExSample_plus_expansion |        5 |       9 |              4   |
| B7_ExSample_plus_expansion |        5 |       9 |              4   |
| B7_ExSample_plus_expansion |        5 |       9 |              4   |
| B7_ExSample_plus_expansion |        5 |       4 |              3   |
| B7_ExSample_plus_expansion |        5 |       4 |              3   |
| B7_ExSample_plus_expansion |        5 |       4 |              3   |
| B7_ExSample_plus_expansion |       10 |       9 |              2.5 |
| B7_ExSample_plus_expansion |       10 |       9 |              2.5 |
| B7_ExSample_plus_expansion |       10 |       8 |              4   |
| B7_ExSample_plus_expansion |       10 |       8 |              5   |
| B7_ExSample_plus_expansion |       10 |       8 |              5   |
| B7_ExSample_plus_expansion |       10 |       9 |              5   |
| B7_ExSample_plus_expansion |       20 |       1 |              2.5 |
| B7_ExSample_plus_expansion |       20 |       9 |              2.5 |
| B7_ExSample_plus_expansion |       20 |       6 |              2.5 |
