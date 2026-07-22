# Hypothesis Construction Repair v1 Final Report

Decision: `HYPOTHESIS_REPAIR_WEAK_GO`

## Strongest supported conclusion

H0 reproduced exactly (AUC `0.294270147221311`, 141 hypotheses, 100/100 core actions). The failed state was not 141 local peaks: source audit finds 55 high-proxy islands and 86 low/uncovered chunks, all incorrectly assigned event-existence mass. H0 evaluator-only fragmentation is `1.230769` and false burden `0.794326`. Source separation yields 87 initial hypotheses, fragmentation `1.052632`, false burden `0.793103`.

Best repaired variant is `H1` with bridge-safe event-F1 AUC `0.314990`, versus H0 `0.294270`, MAP/M1 `0.388056`, and best native `0.389659`. This is single-video, VLM-defined pseudo-oracle development evidence.

## Per-budget primary materializer results

| variant   |   budget |   event_precision |   event_recall |   event_f1 |
|:----------|---------:|------------------:|---------------:|-----------:|
| H0        |        5 |          0        |      0         |  0         |
| H0        |       10 |          1        |      0.0384615 |  0.0740741 |
| H0        |       20 |          1        |      0.0769231 |  0.142857  |
| H0        |       50 |          1        |      0.192308  |  0.322581  |
| H0        |       80 |          0.875    |      0.269231  |  0.411765  |
| H0        |      100 |          0.888889 |      0.307692  |  0.457143  |
| H1        |        5 |          0        |      0         |  0         |
| H1        |       10 |          1        |      0.0384615 |  0.0740741 |
| H1        |       20 |          1        |      0.0769231 |  0.142857  |
| H1        |       50 |          1        |      0.192308  |  0.322581  |
| H1        |       80 |          0.888889 |      0.307692  |  0.457143  |
| H1        |      100 |          0.909091 |      0.384615  |  0.540541  |
| H2        |        5 |          0        |      0         |  0         |
| H2        |       10 |          1        |      0.0384615 |  0.0740741 |
| H2        |       20 |          1        |      0.0769231 |  0.142857  |
| H2        |       50 |          1        |      0.192308  |  0.322581  |
| H2        |       80 |          0.888889 |      0.307692  |  0.457143  |
| H2        |      100 |          0.909091 |      0.384615  |  0.540541  |
| H3        |        5 |          0        |      0         |  0         |
| H3        |       10 |          1        |      0.0384615 |  0.0740741 |
| H3        |       20 |          1        |      0.0769231 |  0.142857  |
| H3        |       50 |          1        |      0.192308  |  0.322581  |
| H3        |       80 |          0.888889 |      0.307692  |  0.457143  |
| H3        |      100 |          0.909091 |      0.384615  |  0.540541  |
| H4        |        5 |          0        |      0         |  0         |
| H4        |       10 |          1        |      0.0384615 |  0.0740741 |
| H4        |       20 |          1        |      0.0769231 |  0.142857  |
| H4        |       50 |          1        |      0.192308  |  0.322581  |
| H4        |       80 |          0.888889 |      0.307692  |  0.457143  |
| H4        |      100 |          0.909091 |      0.384615  |  0.540541  |

## Causal decomposition

F4 semantic overpopulation is supported and H1 has independent ablation value (`+0.020720` AUC). F3 missing saturation exists in H0 but is not a demonstrated performance cause: H2 adds zero and triggers no absorption. Generic F1 enumeration failure is rejected: H0 structure and owner-follow-up candidates were eligible at 55 steps but always outscored; the semantic F1 defect is that genuine uncovered exploration was encoded as fake hypotheses. Under H4, output-changing structure probes were eligible at 55 B=100 steps but again outscored and never selected. F2 score-scale failure is not demonstrated because action-score ranges overlap, so HS was not run. F5 outcome-belief failure remains plausible but unisolated.

## Repair attribution

| component                                | variant   |     auc |   increment_vs_previous |   materializer_gain_m1_minus_m0 |
|:-----------------------------------------|:----------|--------:|------------------------:|--------------------------------:|
| candidate_representation                 | H1        | 0.31499 |               0.0207203 |                       0.0338661 |
| event_saturation                         | H2        | 0.31499 |               0         |                       0.0338661 |
| dynamic_exploration                      | H3        | 0.31499 |               0         |                       0.0338661 |
| triggered_counterfactual_materialization | H4        | 0.31499 |               0         |                       0.0338661 |

## Mechanism activation

| variant   |   logical_calls |   initial_hypotheses |   terminal_live_hypotheses |   core_selected |   explore_selected |   structure_selected | all_first_100_core   |   structure_eligible_steps |   max_structure_score |   positive_branch_output_change_rate |   negative_branch_output_change_rate |   dynamic_creations |   absorptions |   exploration_yield |
|:----------|----------------:|---------------------:|---------------------------:|----------------:|-------------------:|---------------------:|:---------------------|---------------------------:|----------------------:|-------------------------------------:|-------------------------------------:|--------------------:|--------------:|--------------------:|
| H1        |             100 |                   87 |                         87 |             100 |                  0 |                    0 | True                 |                          0 |         nan           |                                    1 |                                    0 |                   0 |             0 |                 nan |
| H2        |             100 |                   87 |                         87 |             100 |                  0 |                    0 | True                 |                          0 |         nan           |                                    1 |                                    0 |                   0 |             0 |                 nan |
| H3        |             100 |                   87 |                         87 |             100 |                  0 |                    0 | True                 |                          0 |         nan           |                                    1 |                                    0 |                   0 |             0 |                 nan |
| H4        |             100 |                   87 |                         87 |             100 |                  0 |                    0 | True                 |                         55 |           0.000247643 |                                    1 |                                    0 |                   0 |             0 |                 nan |

Acquisition/materializer separation is reported in `analysis/acquisition_materializer_matrix.csv`. No reference labels entered online planning, no score grid or lambda tuning was performed, and physical VLM calls were zero.

## Next action

Freeze the winning semantic repair and test it unchanged on multiple held-out videos with outcome calibration diagnostics.
