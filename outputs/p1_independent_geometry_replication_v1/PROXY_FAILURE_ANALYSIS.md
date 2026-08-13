# P1 natural-proxy characterization and failure analysis

Proxy A is the frozen YOLOv8n object/track/motion-oriented score. Proxy B is a frozen grayscale Farneback optical-flow plus frame-difference score sampled four times per unit. Proxy B uses no detector, language model, semantic outcome, reference event, or human label and is materially cheaper than the VLM oracle.

Across the six video-query clusters, Proxy A AUPRC ranges from 0.198 to 0.379 and Proxy B from 0.162 to 0.236. A/B rank Spearman by video is approximately -0.029 to 0.176, confirming different rankings/error mechanisms. Proxy B is weaker on most cluster/query cells; that weakness is retained and is not tuned away. The same frozen trace and geometry protocol is used for both proxies.

`PROXY_CHARACTERIZATION.csv` reports AUPRC, Recall@K, score/label rank correlation, and A/B rank correlation. Unknown/parse-failure units remain in the denominator as non-positive for descriptive ranking diagnostics and are counted in the table.
