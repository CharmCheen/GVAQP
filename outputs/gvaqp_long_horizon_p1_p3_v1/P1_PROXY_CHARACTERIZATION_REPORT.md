# P1 two-natural-proxy characterization

This post-freeze descriptive audit reports AUPRC, Recall@K, score/label rank correlation, score distributions, and cross-proxy rank correlation for both frozen query outcomes. It does not tune either proxy or select traces.

| query_id                           | video_id   | proxy_family                         | metric   |    value |   positive_units |   unknown_or_parse_units |   label_rank_spearman |
|:-----------------------------------|:-----------|:-------------------------------------|:---------|---------:|-----------------:|-------------------------:|----------------------:|
| Q_DRIVER_RESPONSE_V1               | DALI       | Proxy A YOLOv8n object/motion        | AUPRC    | 0.314615 |               82 |                        0 |            0.202595   |
| Q_DRIVER_RESPONSE_V1               | DALI       | Proxy B optical-flow visual dynamics | AUPRC    | 0.162104 |               82 |                        0 |           -0.00353845 |
| Q_DRIVER_RESPONSE_V1               | HANGZHOU   | Proxy A YOLOv8n object/motion        | AUPRC    | 0.258384 |               93 |                        1 |            0.159926   |
| Q_DRIVER_RESPONSE_V1               | HANGZHOU   | Proxy B optical-flow visual dynamics | AUPRC    | 0.162096 |               93 |                        1 |           -0.0129048  |
| Q_DRIVER_RESPONSE_V1               | WUHAN      | Proxy A YOLOv8n object/motion        | AUPRC    | 0.311228 |               76 |                        0 |            0.161942   |
| Q_DRIVER_RESPONSE_V1               | WUHAN      | Proxy B optical-flow visual dynamics | AUPRC    | 0.236056 |               76 |                        0 |            0.059406   |
| Q_VULNERABLE_ROAD_USER_CONFLICT_V1 | DALI       | Proxy A YOLOv8n object/motion        | AUPRC    | 0.379036 |              127 |                        1 |            0.217203   |
| Q_VULNERABLE_ROAD_USER_CONFLICT_V1 | DALI       | Proxy B optical-flow visual dynamics | AUPRC    | 0.227583 |              127 |                        1 |           -0.0501269  |
| Q_VULNERABLE_ROAD_USER_CONFLICT_V1 | HANGZHOU   | Proxy A YOLOv8n object/motion        | AUPRC    | 0.220578 |               84 |                        1 |            0.144376   |
| Q_VULNERABLE_ROAD_USER_CONFLICT_V1 | HANGZHOU   | Proxy B optical-flow visual dynamics | AUPRC    | 0.194132 |               84 |                        1 |            0.0924214  |
| Q_VULNERABLE_ROAD_USER_CONFLICT_V1 | WUHAN      | Proxy A YOLOv8n object/motion        | AUPRC    | 0.197831 |               53 |                        2 |            0.067499   |
| Q_VULNERABLE_ROAD_USER_CONFLICT_V1 | WUHAN      | Proxy B optical-flow visual dynamics | AUPRC    | 0.218414 |               53 |                        2 |            0.119922   |
