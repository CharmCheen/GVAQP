# Ours Failure Audit Report

## Scope

This audit reads existing CSV outputs only. It does not rerun Ours, ARC, SUPG, ABae, GPU, VLM, YOLO, training, downloads, or proxy generation. All labels discussed here are pseudo-oracle/VLM-defined labels, not human ground truth.

## Headline

`Ours-Frozen-LATE-AQP-v1` has two failure modes:

- At low and mid budgets, it selects fewer unique reference-covering units than ARC-refinement or ABae.
- At high budget, it actually covers the reference universe at the unit level, but merges many selected units into very long segments. Under one-to-one event matching, one long segment can match only one reference, so over-merge suppresses measured event recall/F1.

The B=50 to B=100 drop in the official repaired metric is therefore a segment construction failure, not a lack of pseudo-oracle positives. Ours mean event recall goes from 0.550 at B=50 to 0.280 at B=100, while per-reference hit-any across seeds goes from 0.700 to 1.000. ARC-refinement hit-any reaches 0.950 at B=100 and ABae reaches 1.000.

## Metric Context

Main comparison rows:

| method                    |   budget |   event_detection_recall_mean |   event_detection_precision_mean |   event_detection_f1_mean |   oracle_calls_mean |   mean_overcoverage_ratio_mean |
|:--------------------------|---------:|------------------------------:|---------------------------------:|--------------------------:|--------------------:|-------------------------------:|
| Ours-Frozen-LATE-AQP-v1   |       20 |                          0.2  |                           0.4556 |                    0.2778 |                  20 |                         8.9915 |
| ARC-refinement            |       20 |                          0.45 |                           0.6547 |                    0.5325 |                  20 |                         9.4474 |
| ABae-stratified-confirmed |       20 |                          0.26 |                           0.8929 |                    0.3957 |                  20 |                         8.3909 |
| Ours-Frozen-LATE-AQP-v1   |       50 |                          0.55 |                           0.471  |                    0.5072 |                  50 |                        23.2001 |
| ARC-refinement            |       50 |                          0.61 |                           0.7638 |                    0.6765 |                  50 |                        10.1131 |
| ABae-stratified-confirmed |       50 |                          0.59 |                           0.9033 |                    0.7102 |                  50 |                        10.3538 |
| Ours-Frozen-LATE-AQP-v1   |       80 |                          0.47 |                           0.507  |                    0.487  |                  80 |                        34.106  |
| ARC-refinement            |       80 |                          0.77 |                           0.8569 |                    0.8029 |                  80 |                        10.5886 |
| ABae-stratified-confirmed |       80 |                          0.83 |                           0.9561 |                    0.8862 |                  80 |                        11.3456 |
| Ours-Frozen-LATE-AQP-v1   |      100 |                          0.28 |                           0.5364 |                    0.3669 |                 100 |                        25.7132 |
| ARC-refinement            |      100 |                          0.85 |                           0.9246 |                    0.8793 |                  97 |                        10.9758 |
| ABae-stratified-confirmed |      100 |                          0.96 |                           0.9895 |                    0.9744 |                 100 |                        12.1669 |

## Budget Monotonicity

B=100 contains B=50 selected/query units in 2/5 seeds. This confirms non-monotonic budget behavior in 3/5 seeds. However, B=100 queries all pseudo-oracle positive units, so the non-monotonicity is not the direct cause of the B=100 recall drop.

Missing positive units from B=50 when moving to B=100 include:

`none`

Lost reference hits from B=50 to B=100 include:

`none`

Non-monotonicity still matters because a budgeted method should be interpretable as an incremental process. But for the B=50 to B=100 metric collapse, the decisive issue is that B=100 turns broad unit coverage into overly long merged segments.

## Per-reference Findings

References hit by ARC/ABae but not Ours at B=20/50/100 include:

`B20:realcartest_event_0022, B20:realcartest_event_0023, B20:realcartest_event_0024, B20:realcartest_event_0025, B20:realcartest_event_0026, B20:realcartest_event_0027, B20:realcartest_event_0028, B20:realcartest_event_0031, B20:realcartest_event_0032, B20:realcartest_event_0034, B20:realcartest_event_0035, B20:realcartest_event_0038, B20:realcartest_event_0039, B20:realcartest_event_0040, B50:realcartest_event_0023, B50:realcartest_event_0024, B50:realcartest_event_0026, B50:realcartest_event_0027, B50:realcartest_event_0030, B50:realcartest_event_0038`

At B=100, references hit by all inspected methods:

`realcartest_event_0022|realcartest_event_0025|realcartest_event_0028|realcartest_event_0029|realcartest_event_0031|realcartest_event_0033|realcartest_event_0034|realcartest_event_0035|realcartest_event_0036|realcartest_event_0037|realcartest_event_0039|realcartest_event_0040|realcartest_event_0041`

At B=100, references hit by no budget-respecting method:

`none`

Full matrix: `per_reference_method_hit_matrix.csv`.

## Selected Unit Quality

Mean selected-unit quality:

| method                    |   budget |   query_units |   output_selected_units |   oracle_positive_selected_units |   selected_positive_rate |   reference_covered_selected_units |   unique_reference_events_hit_by_selected_units |   duplicate_selected_units_per_reference |   average_proxy_score_selected_units |   average_proxy_score_selected_positives |
|:--------------------------|---------:|--------------:|------------------------:|---------------------------------:|-------------------------:|-----------------------------------:|------------------------------------------------:|-----------------------------------------:|-------------------------------------:|-----------------------------------------:|
| ABae-stratified-confirmed |       20 |            20 |                     6.6 |                              6.6 |                   1      |                                6.6 |                                             5.2 |                                      1.4 |                               0.3739 |                                   0.3739 |
| ABae-stratified-confirmed |       50 |            50 |                    17   |                             17   |                   1      |                               17   |                                            11.8 |                                      5.2 |                               0.3829 |                                   0.3829 |
| ABae-stratified-confirmed |      100 |           100 |                    30.8 |                             30.8 |                   1      |                               30.8 |                                            19.2 |                                     11.6 |                               0.3642 |                                   0.3642 |
| ARC-refinement            |       20 |            20 |                    21.4 |                             14   |                   0.6581 |                               14   |                                             9   |                                      5   |                               0.4251 |                                   0.4203 |
| ARC-refinement            |       50 |            50 |                    23.8 |                             19   |                   0.799  |                               19   |                                            12.2 |                                      6.8 |                               0.4055 |                                   0.3988 |
| ARC-refinement            |      100 |            97 |                    29   |                             28   |                   0.9664 |                               28   |                                            17   |                                     11   |                               0.3742 |                                   0.3724 |
| Ours-Frozen-LATE-AQP-v1   |       20 |            20 |                    20   |                              9   |                   0.45   |                                9   |                                             4   |                                      5   |                               0.4572 |                                   0.464  |
| Ours-Frozen-LATE-AQP-v1   |       50 |            50 |                    50   |                             20.8 |                   0.416  |                               20.8 |                                            13.2 |                                      7.6 |                               0.3996 |                                   0.4118 |
| Ours-Frozen-LATE-AQP-v1   |      100 |           100 |                   100   |                             32   |                   0.32   |                               32   |                                            20   |                                     12   |                               0.3376 |                                   0.3602 |

ABae wins because confirmed-only output concentrates on sampled positives and covers more unique reference events as budget grows without merging the whole timeline into a few broad predictions. ARC-refinement wins because its clip refinement produces broad proxy-derived candidate coverage while keeping output segments more useful under one-to-one matching. Ours spends the whole budget and reaches all positive/reference-covered units at B=100, but its segment construction turns that coverage into a small number of long segments.

## Segment Construction

Ours segment construction summary:

|   budget |   num_segments_mean |   mean_segment_duration |   max_segment_duration_mean |   segments_with_no_reference_overlap |   refs_by_long_60 |
|---------:|--------------------:|------------------------:|----------------------------:|-------------------------------------:|------------------:|
|        5 |                 3.8 |                 13.3333 |                          22 |                                  2.6 |               0   |
|       10 |                 7.6 |                 13.3333 |                          30 |                                  4.8 |               0   |
|       20 |                 8.8 |                 22.7778 |                          50 |                                  4.8 |               0   |
|       30 |                17.4 |                 17.5978 |                          52 |                                 10.2 |               0   |
|       40 |                19.6 |                 20.5154 |                          60 |                                 10   |               0.2 |
|       50 |                23.4 |                 21.4078 |                         100 |                                 12.4 |               3.6 |
|       80 |                18.6 |                 43.2847 |                         210 |                                  9.2 |               8.6 |
|      100 |                10.4 |                 97.4747 |                         478 |                                  4.8 |              17.6 |

Ours does form segments from queried units, and it queries all 32 pseudo-oracle positive units at B=100. The failure is that high-budget output merges too aggressively: mean segment duration rises to about 97s at B=100, max segment duration averages about 478s, and long segments cover most references. Under one-to-one matching, those long segments cannot receive credit for every reference they overlap.

## B=50 To B=100 Drop

The direct reason for the B=50 to B=100 performance drop is over-merge in segment construction. The B=100 query/output units cover all 20 reference events at least at the unit-overlap level, but the output collapses many adjacent selected units into far fewer, much longer segments. The repaired metric uses one-to-one matching between predictions and references, so a single broad prediction overlapping many short VLM-defined references only counts once.

There is also non-monotonic query behavior: B=100 is not a strict extension of B=50 in 3/5 seeds. That should be fixed for auditability, but the B=100 drop is explained by segment construction rather than missing positives.

## Module Diagnosis

- Candidate selection: weak at low/mid budgets, because B=20 and B=50 cover fewer unique references than ARC/ABae.
- Oracle budget allocation: secondary but real. The method allocates audit/repair/discovery from scratch per budget and is non-monotonic.
- Segment merge: primary high-budget failure. Segments are constructed, but B=80/B=100 over-merge selected units into long predictions that lose credit under one-to-one event matching.
- Boundary expansion: secondary. Boundary quality remains poor, but the main metric is overlap_any and the larger issue is missed events.
- Duplicate handling: not the main failure; duplicate rates are not the dominant observed gap.

## Answered Questions

- Why does Ours lose? Low/mid budgets suffer weaker selected-unit/reference coverage; high budgets suffer segment over-merge.
- Why does B=50 to B=100 drop? B=100 covers more units and all positives, but merges them into long segments that one-to-one matching cannot credit against multiple references.
- Does Ours have non-monotonic budget behavior? Yes.
- Did Ours query positives but fail to form effective segments? Yes at high budget: positives are queried and represented, but the merged segments are too broad to be effective under the repaired matching protocol.
- Where do ARC/ABae win? ARC keeps useful refined candidate segments; ABae outputs confirmed-positive unit groups with much better precision and less harmful over-merge.

## Decision

FIX_SEGMENT_MERGE_FIRST

## Next Fix Priority

Fix segment merge first: split high-budget selected units into event-sized components or add a non-reference-aware temporal NMS/segmentation rule so one broad selected region does not collapse many events into one prediction. Then make the budget process incremental/monotonic and improve low-budget selection coverage.
