# 09 Paper Claim Audit

## Strong Claims

- Dataset3 full center10 pseudo-oracle is complete: 347 anchors, 40 positives, 307 negatives, 0 abstain/parse errors in the parsed CSV.
- Dataset3 is non-vacuous for oracle-relative clip-level event retrieval: positive rate 11.5%, 27 positive clusters.
- Temporal correlation exists: P(1->1)=0.325 vs base 0.115.

## Moderate Claims

- Event-Native AQP is a valid framing for this workload, but currently as oracle-relative empirical query processing, not a completed guarantee system.
- Score-fusion proxy weakness and non-monotonicity are real on dataset3: `score_fusion_geometry_motion` AUROC is 0.550; 17/40 positives are below its median score; 77 high-score negatives exist.
- Budget decomposition via `proxy_diversity_prefilter` beats score-fusion `top_proxy` at B=80 by 30% relative anchor recall in this replay, but not against the omitted `object_count_mean` top-B baseline.
- Temporal coverage/diversity is a useful allocation principle; evidence is single-video dataset3 plus earlier realcartest context and must be recomputed with corrected proxy baselines.
- Dataset3 shows proxy behavior differs sharply by video/object mix, but the claim that `object_count_mean` is anti-predictive is false.
- Cluster-aware upper bound shows opportunity, but only as an oracle upper bound.

## Weak Claims

- DCA as a main algorithm: motivated but unvalidated.
- Audit-aware low-score exploration: simple replay variant did not clearly win; richer audit remains a hypothesis.
- Adaptive cluster expansion/CFA: design only.
- Certificate under temporal correlation: not implemented in this sprint.
- Second-video generalization beyond dataset3 and realcartest: still needs another suitable long video.

## Unsafe Claims

- Claiming formal G-ARC recall certificates from these outputs.
- Claiming DCA improves over baselines experimentally.
- Claiming REFINE/event-boundary localization as a contribution on dataset3.
- Claiming best AUROC is 0.624 for score fusion or that `object_count_mean` is anti-predictive on dataset3.
- Claiming `proxy_diversity_prefilter` is the best non-oracle method before replay includes `object_count_mean`.
- Treating VLM labels as human truth.
- Treating `cluster_aware_selection` as deployable.
- Claiming VLDB/SIGMOD/ICDE-ready results without DCA validation, certificate mechanics, and second-video replication.

## Minimum Missing Experiments

- Correct AUROC implementation and rerun no-new-VLM replay with `object_count_mean` and score-fusion baselines.
- DCA replay with saved selections and fixed randomness after the proxy-score recomputation.
- Minimal certificate simulation on existing labels, clearly marked as mechanics/underpowered if needed.
- A new long-video P1 pilot before any broad generalization claim.
