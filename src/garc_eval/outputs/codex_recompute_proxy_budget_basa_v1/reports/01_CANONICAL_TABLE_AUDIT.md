# 01 Canonical Table Audit

## Inputs

- Oracle labels: `/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/oracle_outputs/dataset3_full_center10_parsed.csv` (347 rows)
- Proxy features: `/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/metadata/center10_proxy_features.csv` (347 rows)
- P1 labels: `/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/oracle_outputs/dataset3_oracle_parsed.csv` (50 rows)

## Join And Integrity Checks

- Join key: `anchor_id`.
- Oracle duplicate anchor IDs: 0.
- Proxy duplicate anchor IDs: 0.
- Missing proxy rows for oracle anchors: 0.
- Extra proxy rows not in oracle: 0.
- P1 reused anchors present in canonical table: 50.

## Canonical Label/Cluster Counts

- Anchors: 347.
- Positives / negatives: 40 / 307.
- Positive rate: 0.115274.
- Positive clusters: 27.
- Singleton / multi-anchor clusters: 21 / 6.
- Largest cluster size: 9.
- P(1->1): 0.325; base positive rate: 0.115.

The recomputed split is 21 singleton clusters and 6 multi-anchor clusters. This matches the prior Codex audit and corrects the GLM report text drift.

## Boundary Policy

`event_start` / `event_end` are retained only as source columns if present. They are not used for replay, BASA, cluster construction, or certificate simulation because dataset3 boundary localization is templated.

## Output

Canonical table written to `/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv`. All downstream scripts in this output directory read this table as the authoritative per-anchor source.
