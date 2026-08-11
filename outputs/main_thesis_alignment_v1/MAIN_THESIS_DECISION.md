# GVAQP Main-Thesis Decision

`PROJECT_MAINLINE_DECISION = TWO_STAGE_UNIFIED`

## Answers to the five primary questions

1. `IS PROXY INACCURACY A FIRST-ORDER QUALITY BOTTLENECK? PARTIAL`  Ranking-stress median low-budget gap is `0.0951`; exposure-stress median is `0.0000`.
2. `DOES MORE RESOURCE RELIABLY IMPROVE QUALITY? YES`  Nested-policy violation rate is `0.48%`.
3. `CAN CURRENT POLICIES COMPRESS THE POOR-vs-GOOD PROXY GAP? PARTIAL`  Best descriptive high-budget compression is `0.2164079385968407`.
4. `DOES POLICY CHOICE MATTER MORE UNDER POOR PROXY? NO`  Median spread good=`0.1709`, poor=`0.1337`.
5. With C1 fixed, median three-policy spread is `0.1403`, versus historical model-relative materializer median `0.1457`.

## Thesis

Robust sparse event-query execution requires both evidence acquisition under imperfect proxy and explicit EventRelation materialization, with the primary algorithmic gap remaining query-policy robustness.

- Materialization role: `CORE_STAGE`.
- Query-policy role: `CORE_STAGE`.
- Deadline role: `CONTEXT / UNPROVEN`; all primary numbers are query-count replay.
- Best robust current policy: `StaticProxyRank` under the frozen lexicographic worst-proxy rule.
- Selector × materializer interaction: `SYSTEMATIC`.
- Action selector opportunity: `WEAK`; contextual bandit reopen: `NO`.

## Claim boundary

The audit supports only deterministic, model-relative, outcome-blind proxy-stress claims over three videos and one query.  It does not establish robustness across natural proxy models, human semantic correctness, learned-controller benefit, or hard-deadline superiority.
