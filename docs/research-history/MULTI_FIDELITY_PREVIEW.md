# Multi-fidelity preview

- Original hypothesis: cheap P0/P1/P2 previews could establish a deployable region-value proxy.
- Scope: two design videos, zero validation/test videos, frozen pseudo-reference.
- Main metrics: P1-L Recall@20 0.329/0.321 versus a 0.40 Gate; AUC 0.594/0.613; cost ratio 0.032729836; net event yield lost 2/4 at 60 s and gained 1/8 at 20% wall-clock.
- Result/failure mechanism: P1-L missed the recall Gate, P1-M was video-unstable, and P2 was near random. P3 was not authorized.
- Failed Gate: exploratory/static ranking; formal validation also blocked by insufficient videos.
- Current disposition: preview and region-value signals not established; implementations excluded.
- Source: `outputs/multi_fidelity_region_preview_v1/reports/FINAL_PREVIEW_DECISION.md`, commit `5047241b0561b911b9a519b18e8e7591c0074e70`.
