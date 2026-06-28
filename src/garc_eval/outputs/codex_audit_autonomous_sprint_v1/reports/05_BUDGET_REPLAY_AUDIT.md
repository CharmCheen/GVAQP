# 05 Budget Replay Audit

## Completeness

- Methods in replay CSV: 10; expected 10.
- Budget points: 8; expected 8: [10, 20, 30, 40, 60, 80, 100, 150].
- No selection-output files were found, so method results can be checked by reimplementing deterministic selection but cannot be audited from saved selected-anchor lists.

## Best Methods By Budget

- B=10: best overall `cluster_aware_selection` event_recall=0.3704; best non-oracle `top_proxy` event_recall=0.1111, anchor_recall=0.0750
- B=20: best overall `cluster_aware_selection` event_recall=0.7407; best non-oracle `proxy_diversity_prefilter` event_recall=0.1852, anchor_recall=0.1250
- B=30: best overall `cluster_aware_selection` event_recall=1.0000; best non-oracle `uniform_temporal_grid` event_recall=0.2593, anchor_recall=0.1750
- B=40: best overall `cluster_aware_selection` event_recall=1.0000; best non-oracle `top_proxy` event_recall=0.2222, anchor_recall=0.1500
- B=60: best overall `cluster_aware_selection` event_recall=1.0000; best non-oracle `uniform_temporal_grid` event_recall=0.3333, anchor_recall=0.2500
- B=80: best overall `cluster_aware_selection` event_recall=1.0000; best non-oracle `proxy_diversity_prefilter` event_recall=0.4444, anchor_recall=0.3250
- B=100: best overall `cluster_aware_selection` event_recall=1.0000; best non-oracle `hybrid_explore_exploit` event_recall=0.4815, anchor_recall=0.3500
- B=150: best overall `cluster_aware_selection` event_recall=1.0000; best non-oracle `proxy_diversity_prefilter` event_recall=0.6667, anchor_recall=0.5500

## B=80 Claim Check

- `top_proxy` anchor recall at B=80: 0.250.
- `proxy_diversity_prefilter` anchor recall at B=80: 0.325.
- Absolute gain: 0.075; relative gain: 30.0%. The `+30% over top_proxy` claim is correct for anchor recall at B=80.
- This comparison is only against score-fusion `top_proxy`. A simple `object_count_mean` top-B baseline finds 15/40 positives at B=80, so the reported "best non-oracle" conclusion is incomplete.

## Method Claim Boundaries

- Supported non-oracle methods: `proxy_diversity_prefilter`, `uniform_temporal_grid`, `top_proxy`, `audit_aware_selection` as replay baselines.
- `cluster_aware_selection` is oracle-informed and should be written only as an upper bound.
- `DCA` is not in the replay CSV and must remain a hypothesis.
- `audit_aware_selection` was tried but does not clearly beat top-proxy; the simple 15% low-score audit design is not validated.
- `hybrid_explore_exploit` used unseeded random sampling with `n_repeats=1`; its ranking is not reproducible enough for a strong claim.
- Because the strongest recomputed single feature was omitted as a replay score, Stage 5 needs no-new-VLM recomputation before paper-level claims about the best non-oracle method.

## Label Leakage

The budget replay uses full oracle labels only for evaluation, except `cluster_aware_selection`, whose selection itself reads oracle clusters. That row is a leakage upper bound, not an algorithm.

Detailed comparison is in `tables/budget_replay_recomputed_summary.csv`.
