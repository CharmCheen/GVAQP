# Stage 2 Sanity Checks

| check                                                                                | status   | detail                                                                                     |
|:-------------------------------------------------------------------------------------|:---------|:-------------------------------------------------------------------------------------------|
| Frozen config file was loaded                                                        | PASS     | loaded                                                                                     |
| No frozen parameter changed                                                          | PASS     | Params(g_max=1, d_core_max=40.0, d_seg_max=60.0, e=1, low_proxy_quantile=0.3, nms_iou=0.7) |
| No reference events used for query selection                                         | PASS     | reference CSV is passed only to evaluator                                                  |
| No unqueried oracle_label read before selection                                      | PASS     | Stage 1A/1B selection fixes unit_id before reading label                                   |
| dataset3_0_1200 MAP-anchor-only + K3 B=5 query count <= budget                       | PASS     | calls=5                                                                                    |
| dataset3_0_1200 MAP-anchor-only + K3 B=5 no duplicate queried units                  | PASS     | unique=5 calls=5                                                                           |
| dataset3_0_1200 MAP-anchor-only + K3 B=5 oracle call_idx strictly increasing         | PASS     | calls=5                                                                                    |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=5 query count <= budget                    | PASS     | calls=5                                                                                    |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=5 no duplicate queried units               | PASS     | unique=5 calls=5                                                                           |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=5 oracle call_idx strictly increasing      | PASS     | calls=5                                                                                    |
| dataset3_0_1200 MAP-anchor-barrier B=5 no PLACE_BARRIER                              | PASS     | barriers=0                                                                                 |
| dataset3_0_1200 MAP-anchor-only + K3 B=10 query count <= budget                      | PASS     | calls=10                                                                                   |
| dataset3_0_1200 MAP-anchor-only + K3 B=10 no duplicate queried units                 | PASS     | unique=10 calls=10                                                                         |
| dataset3_0_1200 MAP-anchor-only + K3 B=10 oracle call_idx strictly increasing        | PASS     | calls=10                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=10 query count <= budget                   | PASS     | calls=10                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=10 no duplicate queried units              | PASS     | unique=10 calls=10                                                                         |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=10 oracle call_idx strictly increasing     | PASS     | calls=10                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier B=10 no PLACE_BARRIER                             | PASS     | barriers=0                                                                                 |
| dataset3_0_1200 MAP-anchor-only + K3 B=20 query count <= budget                      | PASS     | calls=20                                                                                   |
| dataset3_0_1200 MAP-anchor-only + K3 B=20 no duplicate queried units                 | PASS     | unique=20 calls=20                                                                         |
| dataset3_0_1200 MAP-anchor-only + K3 B=20 oracle call_idx strictly increasing        | PASS     | calls=20                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=20 query count <= budget                   | PASS     | calls=20                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=20 no duplicate queried units              | PASS     | unique=20 calls=20                                                                         |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=20 oracle call_idx strictly increasing     | PASS     | calls=20                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier B=20 no PLACE_BARRIER                             | PASS     | barriers=0                                                                                 |
| dataset3_0_1200 MAP-anchor-only + K3 B=50 query count <= budget                      | PASS     | calls=50                                                                                   |
| dataset3_0_1200 MAP-anchor-only + K3 B=50 no duplicate queried units                 | PASS     | unique=50 calls=50                                                                         |
| dataset3_0_1200 MAP-anchor-only + K3 B=50 oracle call_idx strictly increasing        | PASS     | calls=50                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=50 query count <= budget                   | PASS     | calls=50                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=50 no duplicate queried units              | PASS     | unique=50 calls=50                                                                         |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=50 oracle call_idx strictly increasing     | PASS     | calls=50                                                                                   |
| dataset3_0_1200 MAP-anchor-only + K3 B=80 query count <= budget                      | PASS     | calls=80                                                                                   |
| dataset3_0_1200 MAP-anchor-only + K3 B=80 no duplicate queried units                 | PASS     | unique=80 calls=80                                                                         |
| dataset3_0_1200 MAP-anchor-only + K3 B=80 oracle call_idx strictly increasing        | PASS     | calls=80                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=80 query count <= budget                   | PASS     | calls=80                                                                                   |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=80 no duplicate queried units              | PASS     | unique=80 calls=80                                                                         |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=80 oracle call_idx strictly increasing     | PASS     | calls=80                                                                                   |
| dataset3_0_1200 MAP-anchor-only + K3 B=100 query count <= budget                     | PASS     | calls=100                                                                                  |
| dataset3_0_1200 MAP-anchor-only + K3 B=100 no duplicate queried units                | PASS     | unique=100 calls=100                                                                       |
| dataset3_0_1200 MAP-anchor-only + K3 B=100 oracle call_idx strictly increasing       | PASS     | calls=100                                                                                  |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=100 query count <= budget                  | PASS     | calls=100                                                                                  |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=100 no duplicate queried units             | PASS     | unique=100 calls=100                                                                       |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=100 oracle call_idx strictly increasing    | PASS     | calls=100                                                                                  |
| dataset3_1200_2400 MAP-anchor-only + K3 B=5 query count <= budget                    | PASS     | calls=5                                                                                    |
| dataset3_1200_2400 MAP-anchor-only + K3 B=5 no duplicate queried units               | PASS     | unique=5 calls=5                                                                           |
| dataset3_1200_2400 MAP-anchor-only + K3 B=5 oracle call_idx strictly increasing      | PASS     | calls=5                                                                                    |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=5 query count <= budget                 | PASS     | calls=5                                                                                    |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=5 no duplicate queried units            | PASS     | unique=5 calls=5                                                                           |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=5 oracle call_idx strictly increasing   | PASS     | calls=5                                                                                    |
| dataset3_1200_2400 MAP-anchor-barrier B=5 no PLACE_BARRIER                           | PASS     | barriers=0                                                                                 |
| dataset3_1200_2400 MAP-anchor-only + K3 B=10 query count <= budget                   | PASS     | calls=10                                                                                   |
| dataset3_1200_2400 MAP-anchor-only + K3 B=10 no duplicate queried units              | PASS     | unique=10 calls=10                                                                         |
| dataset3_1200_2400 MAP-anchor-only + K3 B=10 oracle call_idx strictly increasing     | PASS     | calls=10                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=10 query count <= budget                | PASS     | calls=10                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=10 no duplicate queried units           | PASS     | unique=10 calls=10                                                                         |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=10 oracle call_idx strictly increasing  | PASS     | calls=10                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier B=10 no PLACE_BARRIER                          | PASS     | barriers=0                                                                                 |
| dataset3_1200_2400 MAP-anchor-only + K3 B=20 query count <= budget                   | PASS     | calls=20                                                                                   |
| dataset3_1200_2400 MAP-anchor-only + K3 B=20 no duplicate queried units              | PASS     | unique=20 calls=20                                                                         |
| dataset3_1200_2400 MAP-anchor-only + K3 B=20 oracle call_idx strictly increasing     | PASS     | calls=20                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=20 query count <= budget                | PASS     | calls=20                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=20 no duplicate queried units           | PASS     | unique=20 calls=20                                                                         |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=20 oracle call_idx strictly increasing  | PASS     | calls=20                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier B=20 no PLACE_BARRIER                          | PASS     | barriers=0                                                                                 |
| dataset3_1200_2400 MAP-anchor-only + K3 B=50 query count <= budget                   | PASS     | calls=50                                                                                   |
| dataset3_1200_2400 MAP-anchor-only + K3 B=50 no duplicate queried units              | PASS     | unique=50 calls=50                                                                         |
| dataset3_1200_2400 MAP-anchor-only + K3 B=50 oracle call_idx strictly increasing     | PASS     | calls=50                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=50 query count <= budget                | PASS     | calls=50                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=50 no duplicate queried units           | PASS     | unique=50 calls=50                                                                         |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=50 oracle call_idx strictly increasing  | PASS     | calls=50                                                                                   |
| dataset3_1200_2400 MAP-anchor-only + K3 B=80 query count <= budget                   | PASS     | calls=80                                                                                   |
| dataset3_1200_2400 MAP-anchor-only + K3 B=80 no duplicate queried units              | PASS     | unique=80 calls=80                                                                         |
| dataset3_1200_2400 MAP-anchor-only + K3 B=80 oracle call_idx strictly increasing     | PASS     | calls=80                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=80 query count <= budget                | PASS     | calls=80                                                                                   |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=80 no duplicate queried units           | PASS     | unique=80 calls=80                                                                         |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=80 oracle call_idx strictly increasing  | PASS     | calls=80                                                                                   |
| dataset3_1200_2400 MAP-anchor-only + K3 B=100 query count <= budget                  | PASS     | calls=100                                                                                  |
| dataset3_1200_2400 MAP-anchor-only + K3 B=100 no duplicate queried units             | PASS     | unique=100 calls=100                                                                       |
| dataset3_1200_2400 MAP-anchor-only + K3 B=100 oracle call_idx strictly increasing    | PASS     | calls=100                                                                                  |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=100 query count <= budget               | PASS     | calls=100                                                                                  |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=100 no duplicate queried units          | PASS     | unique=100 calls=100                                                                       |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=100 oracle call_idx strictly increasing | PASS     | calls=100                                                                                  |
| dataset3_2400_3462 MAP-anchor-only + K3 B=5 query count <= budget                    | PASS     | calls=5                                                                                    |
| dataset3_2400_3462 MAP-anchor-only + K3 B=5 no duplicate queried units               | PASS     | unique=5 calls=5                                                                           |
| dataset3_2400_3462 MAP-anchor-only + K3 B=5 oracle call_idx strictly increasing      | PASS     | calls=5                                                                                    |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=5 query count <= budget                 | PASS     | calls=5                                                                                    |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=5 no duplicate queried units            | PASS     | unique=5 calls=5                                                                           |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=5 oracle call_idx strictly increasing   | PASS     | calls=5                                                                                    |
| dataset3_2400_3462 MAP-anchor-barrier B=5 no PLACE_BARRIER                           | PASS     | barriers=0                                                                                 |
| dataset3_2400_3462 MAP-anchor-only + K3 B=10 query count <= budget                   | PASS     | calls=10                                                                                   |
| dataset3_2400_3462 MAP-anchor-only + K3 B=10 no duplicate queried units              | PASS     | unique=10 calls=10                                                                         |
| dataset3_2400_3462 MAP-anchor-only + K3 B=10 oracle call_idx strictly increasing     | PASS     | calls=10                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=10 query count <= budget                | PASS     | calls=10                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=10 no duplicate queried units           | PASS     | unique=10 calls=10                                                                         |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=10 oracle call_idx strictly increasing  | PASS     | calls=10                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier B=10 no PLACE_BARRIER                          | PASS     | barriers=0                                                                                 |
| dataset3_2400_3462 MAP-anchor-only + K3 B=20 query count <= budget                   | PASS     | calls=20                                                                                   |
| dataset3_2400_3462 MAP-anchor-only + K3 B=20 no duplicate queried units              | PASS     | unique=20 calls=20                                                                         |
| dataset3_2400_3462 MAP-anchor-only + K3 B=20 oracle call_idx strictly increasing     | PASS     | calls=20                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=20 query count <= budget                | PASS     | calls=20                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=20 no duplicate queried units           | PASS     | unique=20 calls=20                                                                         |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=20 oracle call_idx strictly increasing  | PASS     | calls=20                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier B=20 no PLACE_BARRIER                          | PASS     | barriers=0                                                                                 |
| dataset3_2400_3462 MAP-anchor-only + K3 B=50 query count <= budget                   | PASS     | calls=50                                                                                   |
| dataset3_2400_3462 MAP-anchor-only + K3 B=50 no duplicate queried units              | PASS     | unique=50 calls=50                                                                         |
| dataset3_2400_3462 MAP-anchor-only + K3 B=50 oracle call_idx strictly increasing     | PASS     | calls=50                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=50 query count <= budget                | PASS     | calls=50                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=50 no duplicate queried units           | PASS     | unique=50 calls=50                                                                         |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=50 oracle call_idx strictly increasing  | PASS     | calls=50                                                                                   |
| dataset3_2400_3462 MAP-anchor-only + K3 B=80 query count <= budget                   | PASS     | calls=80                                                                                   |
| dataset3_2400_3462 MAP-anchor-only + K3 B=80 no duplicate queried units              | PASS     | unique=80 calls=80                                                                         |
| dataset3_2400_3462 MAP-anchor-only + K3 B=80 oracle call_idx strictly increasing     | PASS     | calls=80                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=80 query count <= budget                | PASS     | calls=80                                                                                   |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=80 no duplicate queried units           | PASS     | unique=80 calls=80                                                                         |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=80 oracle call_idx strictly increasing  | PASS     | calls=80                                                                                   |
| dataset3_2400_3462 MAP-anchor-only + K3 B=100 query count <= budget                  | PASS     | calls=100                                                                                  |
| dataset3_2400_3462 MAP-anchor-only + K3 B=100 no duplicate queried units             | PASS     | unique=100 calls=100                                                                       |
| dataset3_2400_3462 MAP-anchor-only + K3 B=100 oracle call_idx strictly increasing    | PASS     | calls=100                                                                                  |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=100 query count <= budget               | PASS     | calls=100                                                                                  |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=100 no duplicate queried units          | PASS     | unique=100 calls=100                                                                       |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=100 oracle call_idx strictly increasing | PASS     | calls=100                                                                                  |
| dataset3_0_1200 MAP-anchor-only + K3 B=5 K3 no negative barrier crossing             | PASS     | negatives=5                                                                                |
| dataset3_0_1200 MAP-anchor-only + K3 B=5 K3 duration constraints                     | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=5 K3 no negative barrier crossing          | PASS     | negatives=5                                                                                |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=5 K3 duration constraints                  | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-only + K3 B=10 K3 no negative barrier crossing            | PASS     | negatives=10                                                                               |
| dataset3_0_1200 MAP-anchor-only + K3 B=10 K3 duration constraints                    | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=10 K3 no negative barrier crossing         | PASS     | negatives=10                                                                               |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=10 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-only + K3 B=20 K3 no negative barrier crossing            | PASS     | negatives=20                                                                               |
| dataset3_0_1200 MAP-anchor-only + K3 B=20 K3 duration constraints                    | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=20 K3 no negative barrier crossing         | PASS     | negatives=20                                                                               |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=20 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-only + K3 B=50 K3 no negative barrier crossing            | PASS     | negatives=47                                                                               |
| dataset3_0_1200 MAP-anchor-only + K3 B=50 K3 duration constraints                    | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=50 K3 no negative barrier crossing         | PASS     | negatives=50                                                                               |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=50 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-only + K3 B=80 K3 no negative barrier crossing            | PASS     | negatives=76                                                                               |
| dataset3_0_1200 MAP-anchor-only + K3 B=80 K3 duration constraints                    | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=80 K3 no negative barrier crossing         | PASS     | negatives=74                                                                               |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=80 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-only + K3 B=100 K3 no negative barrier crossing           | PASS     | negatives=94                                                                               |
| dataset3_0_1200 MAP-anchor-only + K3 B=100 K3 duration constraints                   | PASS     | D_seg=60.0                                                                                 |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=100 K3 no negative barrier crossing        | PASS     | negatives=93                                                                               |
| dataset3_0_1200 MAP-anchor-barrier + K3 B=100 K3 duration constraints                | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-only + K3 B=5 K3 no negative barrier crossing          | PASS     | negatives=5                                                                                |
| dataset3_1200_2400 MAP-anchor-only + K3 B=5 K3 duration constraints                  | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=5 K3 no negative barrier crossing       | PASS     | negatives=5                                                                                |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=5 K3 duration constraints               | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-only + K3 B=10 K3 no negative barrier crossing         | PASS     | negatives=8                                                                                |
| dataset3_1200_2400 MAP-anchor-only + K3 B=10 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=10 K3 no negative barrier crossing      | PASS     | negatives=8                                                                                |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=10 K3 duration constraints              | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-only + K3 B=20 K3 no negative barrier crossing         | PASS     | negatives=16                                                                               |
| dataset3_1200_2400 MAP-anchor-only + K3 B=20 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=20 K3 no negative barrier crossing      | PASS     | negatives=16                                                                               |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=20 K3 duration constraints              | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-only + K3 B=50 K3 no negative barrier crossing         | PASS     | negatives=41                                                                               |
| dataset3_1200_2400 MAP-anchor-only + K3 B=50 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=50 K3 no negative barrier crossing      | PASS     | negatives=39                                                                               |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=50 K3 duration constraints              | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-only + K3 B=80 K3 no negative barrier crossing         | PASS     | negatives=67                                                                               |
| dataset3_1200_2400 MAP-anchor-only + K3 B=80 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=80 K3 no negative barrier crossing      | PASS     | negatives=63                                                                               |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=80 K3 duration constraints              | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-only + K3 B=100 K3 no negative barrier crossing        | PASS     | negatives=85                                                                               |
| dataset3_1200_2400 MAP-anchor-only + K3 B=100 K3 duration constraints                | PASS     | D_seg=60.0                                                                                 |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=100 K3 no negative barrier crossing     | PASS     | negatives=82                                                                               |
| dataset3_1200_2400 MAP-anchor-barrier + K3 B=100 K3 duration constraints             | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-only + K3 B=5 K3 no negative barrier crossing          | PASS     | negatives=4                                                                                |
| dataset3_2400_3462 MAP-anchor-only + K3 B=5 K3 duration constraints                  | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=5 K3 no negative barrier crossing       | PASS     | negatives=4                                                                                |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=5 K3 duration constraints               | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-only + K3 B=10 K3 no negative barrier crossing         | PASS     | negatives=9                                                                                |
| dataset3_2400_3462 MAP-anchor-only + K3 B=10 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=10 K3 no negative barrier crossing      | PASS     | negatives=9                                                                                |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=10 K3 duration constraints              | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-only + K3 B=20 K3 no negative barrier crossing         | PASS     | negatives=17                                                                               |
| dataset3_2400_3462 MAP-anchor-only + K3 B=20 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=20 K3 no negative barrier crossing      | PASS     | negatives=17                                                                               |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=20 K3 duration constraints              | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-only + K3 B=50 K3 no negative barrier crossing         | PASS     | negatives=44                                                                               |
| dataset3_2400_3462 MAP-anchor-only + K3 B=50 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=50 K3 no negative barrier crossing      | PASS     | negatives=44                                                                               |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=50 K3 duration constraints              | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-only + K3 B=80 K3 no negative barrier crossing         | PASS     | negatives=70                                                                               |
| dataset3_2400_3462 MAP-anchor-only + K3 B=80 K3 duration constraints                 | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=80 K3 no negative barrier crossing      | PASS     | negatives=70                                                                               |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=80 K3 duration constraints              | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-only + K3 B=100 K3 no negative barrier crossing        | PASS     | negatives=89                                                                               |
| dataset3_2400_3462 MAP-anchor-only + K3 B=100 K3 duration constraints                | PASS     | D_seg=60.0                                                                                 |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=100 K3 no negative barrier crossing     | PASS     | negatives=88                                                                               |
| dataset3_2400_3462 MAP-anchor-barrier + K3 B=100 K3 duration constraints             | PASS     | D_seg=60.0                                                                                 |
| Baseline outputs are not modified                                                    | PASS     | no baseline outputs for dataset3 Stage 2 were found or written                             |
| Native and strengthened baselines are reported separately                            | PASS     | reported unavailable separately in manifest/final report                                   |
| If any window lacks baselines, clearly marked                                        | PASS     | baseline_availability=none_for_ARC_SUPG_ABae_Ours_in_stage2_format                         |
| If fewer than 3 windows usable, report LIMITED_CROSS_VIDEO                           | PASS     | usable_windows=3                                                                           |
| No parameter tuning after seeing results                                             | PASS     | single frozen run; no parameter branches                                                   |
