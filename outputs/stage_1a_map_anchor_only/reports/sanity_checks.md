# Stage 1A Sanity Checks

| check                                               | status   | detail                                                                                                      |
|:----------------------------------------------------|:---------|:------------------------------------------------------------------------------------------------------------|
| native and strengthened baseline files not modified | PASS     | files=540                                                                                                   |
| MAP policy does not read unqueried oracle_label     | PASS     | selection functions receive proxy/time public table; label_by_unit is accessed only after unit_id selection |
| components built only from proxy_score and time     | PASS     | component_tables=6                                                                                          |
| reference events used only for evaluation           | PASS     | reference dataframe is passed only to evaluator                                                             |
| K3 materializer is Stage 0.7 final implementation   | PASS     | uses S7.construct_k_segments with K3_gap_duration_negative_barrier                                          |
| MAP B=5 query count <= budget                       | PASS     | calls=5                                                                                                     |
| MAP B=5 call_idx increasing                         | PASS     | calls=5                                                                                                     |
| MAP B=5 no duplicate queried units                  | PASS     | unique=5 calls=5                                                                                            |
| MAP B=10 query count <= budget                      | PASS     | calls=10                                                                                                    |
| MAP B=10 call_idx increasing                        | PASS     | calls=10                                                                                                    |
| MAP B=10 no duplicate queried units                 | PASS     | unique=10 calls=10                                                                                          |
| MAP B=20 query count <= budget                      | PASS     | calls=20                                                                                                    |
| MAP B=20 call_idx increasing                        | PASS     | calls=20                                                                                                    |
| MAP B=20 no duplicate queried units                 | PASS     | unique=20 calls=20                                                                                          |
| MAP B=50 query count <= budget                      | PASS     | calls=50                                                                                                    |
| MAP B=50 call_idx increasing                        | PASS     | calls=50                                                                                                    |
| MAP B=50 no duplicate queried units                 | PASS     | unique=50 calls=50                                                                                          |
| MAP B=80 query count <= budget                      | PASS     | calls=80                                                                                                    |
| MAP B=80 call_idx increasing                        | PASS     | calls=80                                                                                                    |
| MAP B=80 no duplicate queried units                 | PASS     | unique=80 calls=80                                                                                          |
| MAP B=100 query count <= budget                     | PASS     | calls=100                                                                                                   |
| MAP B=100 call_idx increasing                       | PASS     | calls=100                                                                                                   |
| MAP B=100 no duplicate queried units                | PASS     | unique=100 calls=100                                                                                        |
| MAP B=5 segment no NaN                              | PASS     | segments=2                                                                                                  |
| MAP B=5 segment nonnegative                         | PASS     | segments=2                                                                                                  |
| MAP B=5 K3 duration cap                             | PASS     | D_seg=60.0                                                                                                  |
| MAP B=5 K3 negative barrier                         | PASS     | negatives=3                                                                                                 |
| MAP B=10 segment no NaN                             | PASS     | segments=5                                                                                                  |
| MAP B=10 segment nonnegative                        | PASS     | segments=5                                                                                                  |
| MAP B=10 K3 duration cap                            | PASS     | D_seg=60.0                                                                                                  |
| MAP B=10 K3 negative barrier                        | PASS     | negatives=5                                                                                                 |
| MAP B=20 segment no NaN                             | PASS     | segments=8                                                                                                  |
| MAP B=20 segment nonnegative                        | PASS     | segments=8                                                                                                  |
| MAP B=20 K3 duration cap                            | PASS     | D_seg=60.0                                                                                                  |
| MAP B=20 K3 negative barrier                        | PASS     | negatives=11                                                                                                |
| MAP B=50 segment no NaN                             | PASS     | segments=12                                                                                                 |
| MAP B=50 segment nonnegative                        | PASS     | segments=12                                                                                                 |
| MAP B=50 K3 duration cap                            | PASS     | D_seg=60.0                                                                                                  |
| MAP B=50 K3 negative barrier                        | PASS     | negatives=31                                                                                                |
| MAP B=80 segment no NaN                             | PASS     | segments=15                                                                                                 |
| MAP B=80 segment nonnegative                        | PASS     | segments=15                                                                                                 |
| MAP B=80 K3 duration cap                            | PASS     | D_seg=60.0                                                                                                  |
| MAP B=80 K3 negative barrier                        | PASS     | negatives=55                                                                                                |
| MAP B=100 segment no NaN                            | PASS     | segments=19                                                                                                 |
| MAP B=100 segment nonnegative                       | PASS     | segments=19                                                                                                 |
| MAP B=100 K3 duration cap                           | PASS     | D_seg=60.0                                                                                                  |
| MAP B=100 K3 negative barrier                       | PASS     | negatives=71                                                                                                |
| evaluator reads newly generated MAP segments        | PASS     | rows=6                                                                                                      |
