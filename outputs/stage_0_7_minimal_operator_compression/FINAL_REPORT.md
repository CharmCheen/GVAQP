# Stage 0.7 Minimal Operator Compression for BB-EM

## Scope

This task compresses EVENT_MATERIALIZE only. It does not change oracle allocation, selected units, query order, proxy generation, model inference, or acquisition policy.

## Main Results

| materializer_variant                             |   event_F1_AUC |    B20_F1 |   B100_F1 |   max_duration |   overmerge_multiplicity |   prediction_count_error |   auc_ratio_to_C6 |   max_duration_ratio_to_C6 |   overmerge_ratio_to_C6 |
|:-------------------------------------------------|---------------:|----------:|----------:|---------------:|-------------------------:|-------------------------:|------------------:|---------------------------:|------------------------:|
| C6_full_EVENT_MATERIALIZE                        |      0.406993  | 0.245822  | 0.569108  |        33.1481 |                 0.797478 |                  14.4815 |          1        |                   1        |                 1       |
| K0_naive_merge                                   |      0.0772487 | 0.0783069 | 0.0783069 |       544.889  |                10.2333   |                  19.2185 |          0.189804 |                  16.438    |                12.8321  |
| K1_gap_limited                                   |      0.366715  | 0.246515  | 0.479542  |        40.037  |                 0.901013 |                  15.6741 |          0.901037 |                   1.20782  |                 1.12983 |
| K2_gap_duration                                  |      0.38935   | 0.245822  | 0.52887   |        21.037  |                 0.850014 |                  15.063  |          0.956651 |                   0.634637 |                 1.06588 |
| K3_gap_duration_negative_barrier                 |      0.406993  | 0.245822  | 0.569108  |        21.037  |                 0.797478 |                  14.4815 |          1        |                   0.634637 |                 1       |
| K4_gap_duration_negative_barrier_selected_expand |      0.406993  | 0.245822  | 0.569108  |        26.1852 |                 0.797478 |                  14.4815 |          1        |                   0.789944 |                 1       |

## Questions

1. K3 reaches 1.0000 of C6 AUC; K4 reaches 1.0000 of C6 AUC.
2. B=100 F1: C6=0.5691, K3=0.5691, K4=0.5691.
3. Max duration / overmerge: C6=33.1481/0.7975, K3=21.0370/0.7975, K4=26.1852/0.7975.
4. B=20 F1: K3=0.2458, K4=0.2458; K4 selected expansion does not materially improve B=20 over K3.
5. Proxy valley and duplicate suppression can be removed from the main method in this replay; K3 matches C6 without them. Conservative expansion is also unnecessary unless K4 materially improves low-budget metrics.
6. Final BB-EM materializer decision: `DECISION_FINAL_MATERIALIZER_K3`.
7. The selected operator is simple enough to define as a query physical operator if the decision is K3 or K4: anchors, bounded gap/duration merge, and optional selected-neighbor expansion are deterministic CSV-local operators.

## Decision

DECISION_FINAL_MATERIALIZER_K3

## Next Step

Stage 1A MAP-anchor-only is recommended next, using K3 as BB-EM.
