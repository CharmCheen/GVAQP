# 07 AQP Algorithm Innovation Audit

## validated_methods

- `proxy_diversity_prefilter`: validated as a non-oracle replay baseline for the score-fusion proxy, but not yet validated against corrected `object_count_mean` baselines.
- `uniform_temporal_grid`: validated as a surprisingly strong coverage baseline at some low/mid budgets.
- `top_proxy`: validated as weak direct-ranking baseline.
- `audit_aware_selection`: implemented, but not validated as an improvement.

## hypothesis_only_methods

- `DCA`: proposed in `AQP_ALGORITHM_DESIGN.md`; not present in replay output.
- `CFA` / cluster-first adaptive: design only.
- Adaptive DCA and certificate/audit machinery: next actions only.

## unsafe_claims

- Calling DCA the main validated algorithm.
- Writing `cluster_aware_selection` as a feasible method.
- Claiming audit/certificate has been implemented.
- Claiming REFINE or event-IoU boundary quality from dataset3.

## recommended_main_algorithm

Use `proxy_diversity_prefilter` / budget decomposition only as the current validated score-fusion replay result. Do not call it the overall main method until replay is recomputed with corrected AUROC and object-count baselines. Present DCA as the next algorithmic hypothesis motivated by replay diagnostics.

## recommended_next_experiment

First fix the AUROC implementation and rerun Stage 3/5 no-new-VLM replay with `object_count_mean`, `score_fusion_geometry_motion`, and score-combination baselines. Then implement DCA as a deterministic method with fixed seeds for any random audit component, saved selected-anchor lists, and sanity checks.
