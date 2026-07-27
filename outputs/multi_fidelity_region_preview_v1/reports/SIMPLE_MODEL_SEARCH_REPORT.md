# Simple Model Search Report

| preview   |   min_video_recall_at_20 |   macro_recall_at_20 |   min_video_auc |   macro_auc |   max_brier |   macro_count_mae |   max_best_region_contribution |   min_leave_best_region_out_recall20 | selected_exploratory_branch   |
|:----------|-------------------------:|---------------------:|----------------:|------------:|------------:|------------------:|-------------------------------:|-------------------------------------:|:------------------------------|
| P1_L      |                 0.321244 |             0.324907 |        0.593571 |    0.603275 |    0.218711 |          0.904186 |                       0.130435 |                             0.303191 | True                          |
| P1_M      |                 0.217617 |             0.244523 |        0.563756 |    0.568093 |    0.229808 |          0.931975 |                       0.157895 |                             0.202128 | False                         |
| P2        |                 0.2      |             0.224352 |        0.5      |    0.524158 |    0.262901 |          0.959369 |                       0.214286 |                             0.212121 | False                         |

All 45 configurations were frozen before univariate metrics. Feature columns and hyperparameters are selected on the training video only for each complete-video fold.
