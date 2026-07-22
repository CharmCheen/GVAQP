# Stage 1A MAP-anchor-only with final K3 BB-EM



## 1. Scope

CPU CSV replay only. MAP-anchor-only uses proxy/time components for query selection, reveals oracle_label only after budgeted selection, and materializes with frozen K3 BB-EM.



## 2. Main Low-budget Ranking

|   budget | method                               | selector                   | variant            |   event_detection@overlap_any_F1 |   unique_events_per_query |   positive_anchor_rate |
|---------:|:-------------------------------------|:---------------------------|:-------------------|---------------------------------:|--------------------------:|-----------------------:|
|        5 | ARC-refinement native                | ARC-refinement@th0.3       | native             |                        0.524158  |                  2.76     |               0.24     |
|        5 | ARC-refinement native                | ARC-refinement@th0.4       | native             |                        0.368182  |                  1.2      |               0.2      |
|        5 | ARC-refinement native                | ARC-refinement@th0.2       | native             |                        0.342529  |                  6        |               0        |
|        5 | SUPG-RT-all-selected native          | SUPG-RT-all-selected       | native             |                        0.262324  |                  4        |               0.13     |
|        5 | MAP-anchor-only + K3 BB-EM           | MAP-anchor-only + K3 BB-EM | MAP_anchor_only_K3 |                        0.181818  |                  0.4      |               0.4      |
|        5 | ABae-stratified-confirmed + K3 BB-EM | ABae-stratified-confirmed  | strengthened_K3    |                        0.162996  |                  0.36     |               0.36     |
|        5 | ABae-stratified-confirmed native     | ABae-stratified-confirmed  | native             |                        0.162996  |                  0.36     |               0.36     |
|        5 | Ours old + K3 BB-EM                  | Ours-Frozen-LATE-AQP-v1    | strengthened_K3    |                        0.112554  |                  0.24     |               0.4      |
|        5 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.3       | strengthened_K3    |                        0.110823  |                  0.24     |               0.24     |
|        5 | Ours-Frozen-LATE-AQP-v1 native       | Ours-Frozen-LATE-AQP-v1    | native             |                        0.101449  |                  0.24     |               0.4      |
|        5 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.4       | strengthened_K3    |                        0.0952381 |                  0.2      |               0.2      |
|        5 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.5       | strengthened_K3    |                        0.0952381 |                  0.2      |               0.36     |
|        5 | ARC-refinement native                | ARC-refinement@th0.1       | native             |                        0.0952381 |                  6        |               0.4      |
|        5 | ARC-refinement native                | ARC-refinement@th0.5       | native             |                        0.0935065 |                  0.2      |               0.36     |
|        5 | SUPG-RT-all-selected + K3 BB-EM      | SUPG-RT-all-selected       | strengthened_K3    |                        0.0554113 |                  0.13     |               0.13     |
|        5 | SUPG-RT-confirmed-only + K3 BB-EM    | SUPG-RT-confirmed-only     | strengthened_K3    |                        0.0554113 |                  0.13     |               0.13     |
|        5 | SUPG-RT-confirmed-only native        | SUPG-RT-confirmed-only     | native             |                        0.0554113 |                  0.13     |               0.13     |
|        5 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.1       | strengthened_K3    |                        0.0380952 |                  0.3      |               0.4      |
|        5 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.2       | strengthened_K3    |                        0         |                  0        |               0        |
|       10 | ARC-refinement native                | ARC-refinement@th0.3       | native             |                        0.524158  |                  1.38     |               0.18     |
|       10 | ARC-refinement native                | ARC-refinement@th0.4       | native             |                        0.40205   |                  0.66     |               0.16     |
|       10 | MAP-anchor-only + K3 BB-EM           | MAP-anchor-only + K3 BB-EM | MAP_anchor_only_K3 |                        0.4       |                  0.5      |               0.5      |
|       10 | ARC-refinement native                | ARC-refinement@th0.2       | native             |                        0.342529  |                  6        |               0        |
|       10 | ABae-stratified-confirmed native     | ABae-stratified-confirmed  | native             |                        0.287378  |                  0.34     |               0.36     |
|       10 | ABae-stratified-confirmed + K3 BB-EM | ABae-stratified-confirmed  | strengthened_K3    |                        0.271568  |                  0.34     |               0.36     |
|       10 | Ours old + K3 BB-EM                  | Ours-Frozen-LATE-AQP-v1    | strengthened_K3    |                        0.245059  |                  0.28     |               0.48     |
|       10 | Ours-Frozen-LATE-AQP-v1 native       | Ours-Frozen-LATE-AQP-v1    | native             |                        0.202198  |                  0.28     |               0.48     |
|       10 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.3       | strengthened_K3    |                        0.164502  |                  0.18     |               0.18     |
|       10 | SUPG-RT-all-selected + K3 BB-EM      | SUPG-RT-all-selected       | strengthened_K3    |                        0.155204  |                  0.186667 |               0.206667 |
|       10 | SUPG-RT-confirmed-only + K3 BB-EM    | SUPG-RT-confirmed-only     | strengthened_K3    |                        0.155204  |                  0.186667 |               0.206667 |
|       10 | SUPG-RT-confirmed-only native        | SUPG-RT-confirmed-only     | native             |                        0.155204  |                  0.186667 |               0.206667 |
|       10 | SUPG-RT-all-selected native          | SUPG-RT-all-selected       | native             |                        0.155143  |                  2.08889  |               0.206667 |
|       10 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.4       | strengthened_K3    |                        0.147186  |                  0.16     |               0.16     |
|       10 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.5       | strengthened_K3    |                        0.110107  |                  0.151667 |               0.526667 |
|       10 | ARC-refinement native                | ARC-refinement@th0.5       | native             |                        0.110107  |                  0.151667 |               0.526667 |
|       10 | ARC-refinement native                | ARC-refinement@th0.1       | native             |                        0.0952381 |                  6        |               0.4      |
|       10 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.1       | strengthened_K3    |                        0.0380952 |                  0.3      |               0.4      |
|       10 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.2       | strengthened_K3    |                        0         |                  0        |               0        |
|       20 | MAP-anchor-only + K3 BB-EM           | MAP-anchor-only + K3 BB-EM | MAP_anchor_only_K3 |                        0.571429  |                  0.4      |               0.45     |
|       20 | ARC-refinement native                | ARC-refinement@th0.4       | native             |                        0.532452  |                  0.45     |               0.23     |
|       20 | ARC-refinement native                | ARC-refinement@th0.3       | native             |                        0.531127  |                  0.7      |               0.13     |
|       20 | ABae-stratified-confirmed native     | ABae-stratified-confirmed  | native             |                        0.395666  |                  0.26     |               0.33     |
|       20 | SUPG-RT-all-selected + K3 BB-EM      | SUPG-RT-all-selected       | strengthened_K3    |                        0.389624  |                  0.269883 |               0.302632 |
|       20 | SUPG-RT-confirmed-only + K3 BB-EM    | SUPG-RT-confirmed-only     | strengthened_K3    |                        0.389624  |                  0.269883 |               0.302632 |
|       20 | SUPG-RT-confirmed-only native        | SUPG-RT-confirmed-only     | native             |                        0.388043  |                  0.269883 |               0.302632 |
|       20 | ABae-stratified-confirmed + K3 BB-EM | ABae-stratified-confirmed  | strengthened_K3    |                        0.374909  |                  0.26     |               0.33     |
|       20 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.4       | strengthened_K3    |                        0.345507  |                  0.22     |               0.23     |
|       20 | ARC-refinement native                | ARC-refinement@th0.2       | native             |                        0.342529  |                  6        |               0        |
|       20 | Ours old + K3 BB-EM                  | Ours-Frozen-LATE-AQP-v1    | strengthened_K3    |                        0.32      |                  0.2      |               0.45     |
|       20 | Ours-Frozen-LATE-AQP-v1 native       | Ours-Frozen-LATE-AQP-v1    | native             |                        0.277833  |                  0.2      |               0.45     |
|       20 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.3       | strengthened_K3    |                        0.227931  |                  0.13     |               0.13     |
|       20 | ARC-refinement native                | ARC-refinement@th0.5       | native             |                        0.12987   |                  0.131667 |               0.506667 |
|       20 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.5       | strengthened_K3    |                        0.126708  |                  0.131667 |               0.506667 |
|       20 | ARC-refinement native                | ARC-refinement@th0.1       | native             |                        0.0952381 |                  6        |               0.4      |
|       20 | SUPG-RT-all-selected native          | SUPG-RT-all-selected       | native             |                        0.0952381 |                  1.07719  |               0.302632 |
|       20 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.1       | strengthened_K3    |                        0.0380952 |                  0.3      |               0.4      |
|       20 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.2       | strengthened_K3    |                        0         |                  0        |               0        |



## 3. Event-F1 AUC Ranking

|   rank | method                               | selector                   | variant            |   event_F1_AUC |     B5_F1 |    B10_F1 |    B20_F1 |   B100_F1 |
|-------:|:-------------------------------------|:---------------------------|:-------------------|---------------:|----------:|----------:|----------:|----------:|
|      1 | MAP-anchor-only + K3 BB-EM           | MAP-anchor-only + K3 BB-EM | MAP_anchor_only_K3 |      0.681462  | 0.181818  | 0.4       | 0.571429  | 0.923077  |
|      2 | ARC-refinement native                | ARC-refinement@th0.4       | native             |      0.670982  | 0.368182  | 0.40205   | 0.532452  | 0.879258  |
|      3 | ABae-stratified-confirmed native     | ABae-stratified-confirmed  | native             |      0.670325  | 0.162996  | 0.287378  | 0.395666  | 0.974359  |
|      4 | Ours old + K3 BB-EM                  | Ours-Frozen-LATE-AQP-v1    | strengthened_K3    |      0.653977  | 0.112554  | 0.245059  | 0.32      | 0.97561   |
|      5 | ABae-stratified-confirmed + K3 BB-EM | ABae-stratified-confirmed  | strengthened_K3    |      0.643321  | 0.162996  | 0.271568  | 0.374909  | 0.938968  |
|      6 | ARC-refinement native                | ARC-refinement@th0.3       | native             |      0.598508  | 0.524158  | 0.524158  | 0.531127  | 0.639275  |
|      7 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.4       | strengthened_K3    |      0.596574  | 0.0952381 | 0.147186  | 0.345507  | 0.886536  |
|      8 | SUPG-RT-confirmed-only native        | SUPG-RT-confirmed-only     | native             |      0.548538  | 0.0554113 | 0.155204  | 0.388043  | 0.73425   |
|      9 | SUPG-RT-all-selected + K3 BB-EM      | SUPG-RT-all-selected       | strengthened_K3    |      0.543666  | 0.0554113 | 0.155204  | 0.389624  | 0.724571  |
|     10 | SUPG-RT-confirmed-only + K3 BB-EM    | SUPG-RT-confirmed-only     | strengthened_K3    |      0.543666  | 0.0554113 | 0.155204  | 0.389624  | 0.724571  |
|     11 | Ours-Frozen-LATE-AQP-v1 native       | Ours-Frozen-LATE-AQP-v1    | native             |      0.404073  | 0.101449  | 0.202198  | 0.277833  | 0.36688   |
|     12 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.3       | strengthened_K3    |      0.39174   | 0.110823  | 0.164502  | 0.227931  | 0.496474  |
|     13 | ARC-refinement native                | ARC-refinement@th0.2       | native             |      0.342529  | 0.342529  | 0.342529  | 0.342529  | 0.342529  |
|     14 | ARC-refinement native                | ARC-refinement@th0.5       | native             |      0.255893  | 0.0935065 | 0.110107  | 0.12987   | 0.345987  |
|     15 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.5       | strengthened_K3    |      0.251895  | 0.0952381 | 0.110107  | 0.126708  | 0.337143  |
|     16 | SUPG-RT-all-selected native          | SUPG-RT-all-selected       | native             |      0.104364  | 0.262324  | 0.155143  | 0.0952381 | 0.0952381 |
|     17 | ARC-refinement native                | ARC-refinement@th0.1       | native             |      0.0952381 | 0.0952381 | 0.0952381 | 0.0952381 | 0.0952381 |
|     18 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.1       | strengthened_K3    |      0.0380952 | 0.0380952 | 0.0380952 | 0.0380952 | 0.0380952 |
|     19 | ARC-refinement + K3 BB-EM            | ARC-refinement@th0.2       | strengthened_K3    |      0         | 0         | 0         | 0         | 0         |



## 4. Required Answers

1. MAP vs Ours old + K3 B=5/10/20 F1: MAP=0.1818/0.4000/0.5714; Ours+K3=0.1126/0.2451/0.3200.

2. Best baseline + K3 B=5/10/20 F1: {5: 0.16299642386598906, 10: 0.2715678524374177, 20: 0.3896237096237096}.

3. Event-F1 AUC: MAP=0.6815, Ours+K3=0.6540.

4. Unique events/query at B=20: MAP=0.4000, Ours+K3=0.2000. Positive anchor rate B=20: MAP=0.4500, Ours+K3=0.4500.

5. High-budget B=50/80/100 F1 MAP=0.6875/0.8000/0.9231.

6. Stage 1B barrier probing recommendation: yes.

7. MAP acquisition claim: MAP_ANCHOR_GO.



## 5. Decision

MAP_ANCHOR_GO



Sanity failures: 0.
