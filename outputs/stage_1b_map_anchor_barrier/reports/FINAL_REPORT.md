# Stage 1B MAP-anchor-barrier Final Report

## 1. Task scope

This task only adds budget-gated PLACE_BARRIER to MAP-anchor-only for B>=50. K3 BB-EM is fixed. It does not implement SEHS, event graph, typed planner, actor model, risk model, learned policy, proxy valley, duplicate suppression, or selected expansion.

## 2. Method

B<=20 calls the Stage 1A MAP-anchor-only policy exactly and uses no PLACE_BARRIER. B>=50 uses a deterministic 60/20/20 CONFIRM_ANCHOR/AUDIT_UNCOVERED/PLACE_BARRIER action mix. Barrier candidates are gaps between confirmed anchors and/or high-proxy suspected components, scored using only proxy/time and queried history. K3 materialization remains gap limit + duration prior + queried-negative hard barrier.

## 3. Low-budget preservation

|   budget | method                                | selector                      | variant               |   event_detection@overlap_any_F1 |   event_detection@overlap_any_precision |   event_detection@overlap_any_recall |   unique_events_per_query |   positive_anchor_rate |
|---------:|:--------------------------------------|:------------------------------|:----------------------|---------------------------------:|----------------------------------------:|-------------------------------------:|--------------------------:|-----------------------:|
|        5 | ARC-refinement native                 | ARC-refinement@th0.3          | native                |                         0.524158 |                                0.509524 |                                 0.54 |                  2.76     |               0.24     |
|        5 | ARC-refinement native                 | ARC-refinement@th0.4          | native                |                         0.368182 |                                0.476923 |                                 0.3  |                  1.2      |               0.2      |
|        5 | MAP-anchor-barrier + K3 BB-EM         | MAP-anchor-barrier + K3 BB-EM | MAP_anchor_barrier_K3 |                         0.181818 |                                1        |                                 0.1  |                  0.4      |               0.4      |
|        5 | MAP-anchor-only + K3 BB-EM            | MAP-anchor-only + K3 BB-EM    | MAP_anchor_only_K3    |                         0.181818 |                                1        |                                 0.1  |                  0.4      |               0.4      |
|        5 | ABae-stratified-confirmed native      | ABae-stratified-confirmed     | native                |                         0.162996 |                                1        |                                 0.09 |                  0.36     |               0.36     |
|        5 | Best strengthened baseline + K3 BB-EM | ABae-stratified-confirmed     | best_strengthened_K3  |                         0.162996 |                                1        |                                 0.09 |                  0.36     |               0.36     |
|        5 | Ours-Frozen-LATE-AQP-v1 native        | Ours-Frozen-LATE-AQP-v1       | native                |                         0.101449 |                                0.333333 |                                 0.06 |                  0.24     |               0.4      |
|       10 | ARC-refinement native                 | ARC-refinement@th0.3          | native                |                         0.524158 |                                0.509524 |                                 0.54 |                  1.38     |               0.18     |
|       10 | ARC-refinement native                 | ARC-refinement@th0.4          | native                |                         0.40205  |                                0.515385 |                                 0.33 |                  0.66     |               0.16     |
|       10 | MAP-anchor-barrier + K3 BB-EM         | MAP-anchor-barrier + K3 BB-EM | MAP_anchor_barrier_K3 |                         0.4      |                                1        |                                 0.25 |                  0.5      |               0.5      |
|       10 | MAP-anchor-only + K3 BB-EM            | MAP-anchor-only + K3 BB-EM    | MAP_anchor_only_K3    |                         0.4      |                                1        |                                 0.25 |                  0.5      |               0.5      |
|       10 | ABae-stratified-confirmed native      | ABae-stratified-confirmed     | native                |                         0.287378 |                                1        |                                 0.17 |                  0.34     |               0.36     |
|       10 | Best strengthened baseline + K3 BB-EM | ABae-stratified-confirmed     | best_strengthened_K3  |                         0.271568 |                                1        |                                 0.16 |                  0.34     |               0.36     |
|       10 | Ours-Frozen-LATE-AQP-v1 native        | Ours-Frozen-LATE-AQP-v1       | native                |                         0.202198 |                                0.366667 |                                 0.14 |                  0.28     |               0.48     |
|       20 | MAP-anchor-barrier + K3 BB-EM         | MAP-anchor-barrier + K3 BB-EM | MAP_anchor_barrier_K3 |                         0.571429 |                                1        |                                 0.4  |                  0.4      |               0.45     |
|       20 | MAP-anchor-only + K3 BB-EM            | MAP-anchor-only + K3 BB-EM    | MAP_anchor_only_K3    |                         0.571429 |                                1        |                                 0.4  |                  0.4      |               0.45     |
|       20 | ARC-refinement native                 | ARC-refinement@th0.4          | native                |                         0.532452 |                                0.654652 |                                 0.45 |                  0.45     |               0.23     |
|       20 | ARC-refinement native                 | ARC-refinement@th0.3          | native                |                         0.531127 |                                0.513853 |                                 0.55 |                  0.7      |               0.13     |
|       20 | ABae-stratified-confirmed native      | ABae-stratified-confirmed     | native                |                         0.395666 |                                0.892857 |                                 0.26 |                  0.26     |               0.33     |
|       20 | Best strengthened baseline + K3 BB-EM | SUPG-RT-all-selected          | best_strengthened_K3  |                         0.389624 |                                1        |                                 0.25 |                  0.269883 |               0.302632 |
|       20 | Ours-Frozen-LATE-AQP-v1 native        | Ours-Frozen-LATE-AQP-v1       | native                |                         0.277833 |                                0.455556 |                                 0.2  |                  0.2      |               0.45     |

## 4. Medium/high-budget diagnostics

|   budget | method                                | selector                      |   event_detection@overlap_any_F1 |   max_segment_duration |   overcoverage_ratio |   overmerge_multiplicity |   matched_mean_iou |   iou_0.3 |   iou_0.5 |   negative_barrier_count |   barrier_query_count |   barrier_negative_rate |
|---------:|:--------------------------------------|:------------------------------|---------------------------------:|-----------------------:|---------------------:|-------------------------:|-------------------:|----------:|----------:|-------------------------:|----------------------:|------------------------:|
|       50 | Best strengthened baseline + K3 BB-EM | ABae-stratified-confirmed     |                         0.683775 |                     40 |              1.40824 |                  1.1     |           0.28823  |  0.250728 |  0.202437 |                     33   |                     0 |                    0    |
|       50 | MAP-anchor-barrier + K3 BB-EM         | MAP-anchor-barrier + K3 BB-EM |                         0.6875   |                     30 |              1.1985  |                  1       |           0.341568 |  0.3125   |  0.1875   |                     34   |                    10 |                    0.8  |
|       50 | MAP-anchor-only + K3 BB-EM            | MAP-anchor-only + K3 BB-EM    |                         0.6875   |                     40 |              1.57303 |                  1.08333 |           0.281777 |  0.25     |  0.1875   |                     31   |                     0 |                    0    |
|       80 | Best strengthened baseline + K3 BB-EM | ABae-stratified-confirmed     |                         0.850807 |                     40 |              2.03745 |                  1.06069 |           0.243481 |  0.274856 |  0.242708 |                     54.2 |                     0 |                    0    |
|       80 | MAP-anchor-barrier + K3 BB-EM         | MAP-anchor-barrier + K3 BB-EM |                         0.864865 |                     40 |              1.94757 |                  1       |           0.263565 |  0.324324 |  0.27027  |                     54   |                    16 |                    0.75 |
|       80 | MAP-anchor-only + K3 BB-EM            | MAP-anchor-only + K3 BB-EM    |                         0.8      |                     40 |              1.94757 |                  1.06667 |           0.306617 |  0.285714 |  0.285714 |                     55   |                     0 |                    0    |
|      100 | Best strengthened baseline + K3 BB-EM | ABae-stratified-confirmed     |                         0.938968 |                     40 |              2.36704 |                  1.03105 |           0.24949  |  0.303152 |  0.303152 |                     69.2 |                     0 |                    0    |
|      100 | MAP-anchor-barrier + K3 BB-EM         | MAP-anchor-barrier + K3 BB-EM |                         0.97561  |                     40 |              2.3221  |                  1       |           0.249007 |  0.292683 |  0.292683 |                     69   |                    20 |                    0.75 |
|      100 | MAP-anchor-only + K3 BB-EM            | MAP-anchor-only + K3 BB-EM    |                         0.923077 |                     40 |              2.17228 |                  1       |           0.268897 |  0.307692 |  0.307692 |                     71   |                     0 |                    0    |

## 5. Barrier effectiveness

|   budget |   barrier_query_count |   barrier_negative_count |   barrier_negative_rate |   barriers_used_by_K3 |   prevented_merges | used_barrier_ids   | action_type_counts                                                 |
|---------:|----------------------:|-------------------------:|------------------------:|----------------------:|-------------------:|:-------------------|:-------------------------------------------------------------------|
|        5 |                     0 |                        0 |                    0    |                     0 |                  0 |                    | {'CONFIRM_ANCHOR': 4, 'AUDIT_UNCOVERED': 1}                        |
|       10 |                     0 |                        0 |                    0    |                     0 |                  0 |                    | {'CONFIRM_ANCHOR': 8, 'AUDIT_UNCOVERED': 2}                        |
|       20 |                     0 |                        0 |                    0    |                     0 |                  0 |                    | {'CONFIRM_ANCHOR': 16, 'AUDIT_UNCOVERED': 4}                       |
|       50 |                    10 |                        8 |                    0.8  |                     1 |                  1 | 80                 | {'CONFIRM_ANCHOR': 30, 'AUDIT_UNCOVERED': 10, 'PLACE_BARRIER': 10} |
|       80 |                    16 |                       12 |                    0.75 |                     2 |                  2 | 78|80              | {'CONFIRM_ANCHOR': 39, 'AUDIT_UNCOVERED': 25, 'PLACE_BARRIER': 16} |
|      100 |                    20 |                       15 |                    0.75 |                     4 |                  4 | 6|8|78|80          | {'AUDIT_UNCOVERED': 41, 'CONFIRM_ANCHOR': 39, 'PLACE_BARRIER': 20} |

Barrier examples:

|   budget |   unit_id |   oracle_label_after_query | helped_k3_prevent_merge   | diagnosis                   |   proxy_score |   call_idx |
|---------:|----------:|---------------------------:|:--------------------------|:----------------------------|--------------:|-----------:|
|       50 |        74 |                          0 | False                     | negative_but_not_used_by_k3 |      0.20472  |          4 |
|       50 |        69 |                          0 | False                     | negative_but_not_used_by_k3 |      0.315853 |          9 |
|       50 |        72 |                          0 | False                     | negative_but_not_used_by_k3 |      0.332914 |         14 |
|       50 |         8 |                          0 | False                     | negative_but_not_used_by_k3 |      0.280752 |         19 |
|       50 |        83 |                          1 | False                     | positive_bridge_or_anchor   |      0.34916  |         24 |
|       50 |        44 |                          0 | False                     | negative_but_not_used_by_k3 |      0.187161 |         29 |
|       50 |        45 |                          0 | False                     | negative_but_not_used_by_k3 |      0.180193 |         34 |
|       50 |        78 |                          0 | False                     | negative_but_not_used_by_k3 |      0.331322 |         39 |
|       50 |         4 |                          1 | False                     | positive_bridge_or_anchor   |      0.276679 |         44 |
|       50 |        80 |                          0 | True                      | helped                      |      0.378503 |         49 |
|       80 |        74 |                          0 | False                     | negative_but_not_used_by_k3 |      0.20472  |          4 |
|       80 |        69 |                          0 | False                     | negative_but_not_used_by_k3 |      0.315853 |          9 |
|       80 |        72 |                          0 | False                     | negative_but_not_used_by_k3 |      0.332914 |         14 |
|       80 |         8 |                          0 | False                     | negative_but_not_used_by_k3 |      0.280752 |         19 |
|       80 |        83 |                          1 | False                     | positive_bridge_or_anchor   |      0.34916  |         24 |
|       80 |        44 |                          0 | False                     | negative_but_not_used_by_k3 |      0.187161 |         29 |
|       80 |        45 |                          0 | False                     | negative_but_not_used_by_k3 |      0.180193 |         34 |
|       80 |        78 |                          0 | True                      | helped                      |      0.331322 |         39 |
|       80 |         4 |                          1 | False                     | positive_bridge_or_anchor   |      0.276679 |         44 |
|       80 |        80 |                          0 | True                      | helped                      |      0.378503 |         49 |
|       80 |        77 |                          1 | False                     | positive_bridge_or_anchor   |      0.342948 |         54 |
|       80 |       109 |                          0 | False                     | negative_but_not_used_by_k3 |      0.266564 |         59 |
|       80 |       110 |                          0 | False                     | negative_but_not_used_by_k3 |      0.186232 |         64 |
|       80 |        53 |                          1 | False                     | positive_bridge_or_anchor   |      0.245194 |         68 |
|       80 |        52 |                          0 | False                     | negative_but_not_used_by_k3 |      0.28747  |         69 |
|       80 |        46 |                          0 | False                     | negative_but_not_used_by_k3 |      0.183267 |         70 |
|      100 |        74 |                          0 | False                     | negative_but_not_used_by_k3 |      0.20472  |          4 |
|      100 |        69 |                          0 | False                     | negative_but_not_used_by_k3 |      0.315853 |          9 |
|      100 |        72 |                          0 | False                     | negative_but_not_used_by_k3 |      0.332914 |         14 |
|      100 |         8 |                          0 | True                      | helped                      |      0.280752 |         19 |

Summary:

- Low-budget preservation: B=5/10/20 F1 is identical to Stage 1A (0.181818/0.400000/0.571429).
- High-budget max duration mean changes 40.000000 -> 36.666667.
- High-budget overcoverage mean changes 1.897628 -> 1.822722.
- High-budget overmerge mean changes 1.050000 -> 1.000000.
- Event-F1 AUC changes 0.681462 -> 0.704061.
- High-budget IoU@0.3 mean changes 0.281136 -> 0.309836; IoU@0.5 mean changes 0.260302 -> 0.250151.
- Because IoU@0.5 decreases slightly at high budget, this is WEAK_GO rather than GO even though AUC and boundedness improve.

## 6. AUC and ranking

|   rank | method                           | selector                      | variant               |   event_F1_AUC |    B5_F1 |   B10_F1 |   B20_F1 |   B50_F1 |   B80_F1 |   B100_F1 |
|-------:|:---------------------------------|:------------------------------|:----------------------|---------------:|---------:|---------:|---------:|---------:|---------:|----------:|
|      1 | MAP-anchor-barrier + K3 BB-EM    | MAP-anchor-barrier + K3 BB-EM | MAP_anchor_barrier_K3 |       0.704061 | 0.181818 | 0.4      | 0.571429 | 0.6875   | 0.864865 |  0.97561  |
|      2 | MAP-anchor-only + K3 BB-EM       | MAP-anchor-only + K3 BB-EM    | MAP_anchor_only_K3    |       0.681462 | 0.181818 | 0.4      | 0.571429 | 0.6875   | 0.8      |  0.923077 |
|      3 | ARC-refinement native            | ARC-refinement@th0.4          | native                |       0.670982 | 0.368182 | 0.40205  | 0.532452 | 0.676479 | 0.802859 |  0.879258 |
|      4 | ABae-stratified-confirmed native | ABae-stratified-confirmed     | native                |       0.670325 | 0.162996 | 0.287378 | 0.395666 | 0.710224 | 0.886177 |  0.974359 |
|      5 | ARC-refinement native            | ARC-refinement@th0.3          | native                |       0.598508 | 0.524158 | 0.524158 | 0.531127 | 0.62065  | 0.639275 |  0.639275 |
|      6 | Ours-Frozen-LATE-AQP-v1 native   | Ours-Frozen-LATE-AQP-v1       | native                |       0.404073 | 0.101449 | 0.202198 | 0.277833 | 0.507191 | 0.487027 |  0.36688  |

## 7. Decision

MAP_BARRIER_WEAK_GO

## 8. Next step

Proceed to cross-video validation with both MAP-anchor-only and MAP-anchor-barrier variants.

Sanity failures: 0.
