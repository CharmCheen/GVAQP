# Univariate Headroom Report

| source_preview   | feature                                      |   min_video_recall_at_20 |   macro_recall_at_20 |   macro_auc |
|:-----------------|:---------------------------------------------|-------------------------:|---------------------:|------------:|
| P1_M             | p1_m__detector__bbox_bottom_y_max__mean      |                 0.321244 |             0.324907 |    0.611971 |
| P1_L             | p1_l__detector__bbox_bottom_y_max__mean      |                 0.3      |             0.318394 |    0.611704 |
| P2               | p2__motion__horizontal_activity_balance__max |                 0.26943  |             0.284715 |    0.540617 |
| P0               | p0__luma_std__std                            |                 0.264249 |             0.267839 |    0.546297 |

Nested train-video-only selections are in `nested_lovo_best_univariate.csv`. P0 metrics are reproduced only as a frozen baseline and are not used to reopen P0 tuning.
