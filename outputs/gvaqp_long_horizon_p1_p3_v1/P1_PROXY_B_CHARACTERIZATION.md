# P1 Proxy characterization (existing query, post-freeze diagnostic)

Proxy B was frozen and scored before this evaluation joined cached Q_DRIVER_RESPONSE_V1 outcomes. These are characterization metrics, not tuning criteria.

- DALI: AUPRC Proxy A=0.315, Proxy B=0.162; A/B rank Spearman=0.176; positives=82/567.
- HANGZHOU: AUPRC Proxy A=0.258, Proxy B=0.162; A/B rank Spearman=0.158; positives=93/561.
- WUHAN: AUPRC Proxy A=0.311, Proxy B=0.236; A/B rank Spearman=-0.029; positives=76/347.

Per-video AUPRC, Recall@K, and label-rank correlation are in `PROXY_CHARACTERIZATION.csv`. Proxy B must be characterized again on Q_VULNERABLE_ROAD_USER_CONFLICT_V1 only after its Qwen32 full-grid outcomes complete.
