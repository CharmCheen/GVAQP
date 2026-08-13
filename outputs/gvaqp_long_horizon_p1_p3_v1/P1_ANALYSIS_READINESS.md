# P1 analysis readiness and remaining gate

## Frozen available design

- Six human-reference clusters: DALI, HANGZHOU, WUHAN × `Q_DRIVER_RESPONSE_V1`, `Q_VULNERABLE_ROAD_USER_CONFLICT_V1`.
- Proxy A: released YOLOv8n object/motion score. Proxy B: frozen optical-flow / visual-dynamics score.
- Frozen traces: UniformTemporal, StaticProxyRank, CoverageFirst, fixed MMR variants, and seeded temporal hashes. Trace construction is outcome-blind.
- Oracle outcomes: existing released Qwen3-VL-32B outcomes for the original query; independently frozen Qwen3-VL-32B acquisition for the second query is in progress.
- Event reference: blinded human temporal events, two independent annotations plus adjudication; not C1/K3/Qwen outcomes.

## Primary endpoints (not materializer-only)

For each trace, acquired semantic evidence touches a human event if at least one queried unit with a verified positive semantic outcome overlaps that event. The primary endpoints are:

1. distinct human events touched;
2. human-event coverage / recall;
3. number of human events with zero acquired semantic evidence;
4. number of human events with one or more verified-positive anchors;
5. direct human EventRecall and EventF1 after applying the frozen C1 materializer.

## Required analyses

- Exact-yield matched traces within video × query × proxy × budget × verified-positive count; compare high vs low `number_of_temporal_regions_touched`, retaining one prespecified contrast per stratum.
- Yield-only versus yield-plus policy-visible / oracle-observed-after-verify geometry explanatory diagnostics under leave-one-video-out, leave-one-video-query-out, and cluster bootstrap by video-query.
- Never use human boundaries, event IDs, future unqueried outcomes, or reference-only variables as policy features.
- Characterize each proxy per query: AUPRC, Recall@K, rank correlation, distribution, and per-query failure patterns. No parameter may be chosen using these results.

## Gate boundary

P1 is PASS only if the independent human endpoints show stable equal-yield geometry benefit across multiple video-query clusters and both natural proxy families. A stronger C1-only association, a single-proxy effect, or a reference-only predictor is a P1 NO-GO. The currently completed preflight cannot establish either conclusion.

## Required external human action

Two independent annotators must complete all six frozen cases using:

```bash
python scripts/serve_p1_human_reference.py
```

The server is deliberately local, serves source video directly, and appends responses. Adjudication must preserve both original submissions. No P1 result may be reported before that reference is complete.
