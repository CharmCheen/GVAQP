# GVAQP Main-Thesis Alignment & Proxy-Robust Query Execution Audit

## Executive decision

`PROJECT_MAINLINE_DECISION = TWO_STAGE_UNIFIED`

The historical core question is budgeted construction of a semantic `EventRelation` when cheap evidence is incomplete or inaccurate.  This audit fixes the supported C1 gap-only materializer and tests proxy ranking, exposure, policy, and oracle-call budget without new semantic inference.

## Experimental contract

- Protocol `14e0b391a87d1a5546df49dc74374fc598e673269c8e843e6b3e3313825fc72c` was frozen before any new proxy-stress Event-F1 was computed.
- Three independent videos: DALI, HANGZHOU, WUHAN; one frozen model-relative query/reference.
- Seven regimes: one natural prospective V3 proxy, three outcome-blind ranking degradations, three outcome-blind exposure degradations.
- Policies: UniformTemporal, StaticProxyRank, TemporalCoverage; budgets: 5/10/20/50/80/100 oracle calls.
- Materializer: C1, gap ≤10 seconds, no duration cap, negative barrier, or K3 extras.
- Semantic oracle calls: zero.  These are cached `QUERY_BUDGET` results, not wall-clock deadlines.

## Current proxy characterization

Original candidate exposure is 100% because every V3 unit becomes a candidate.  Ranking AUPRC by video is: DALI=0.3146, HANGZHOU=0.2584, WUHAN=0.3112.  Therefore original exposure quality is structurally maximal while ranking quality is empirical and video-dependent.

## Proxy and policy results

- Proxy inaccuracy bottleneck: `PARTIAL`.
- Ranking severe-vs-original low-budget median gap: `0.0951`.
- Exposure severe-vs-original low-budget median gap: `0.0000`.
- Policy median spread under original proxy: `0.1709`.
- Policy median spread under poor regimes: `0.1337`.
- Policy effect with C1 fixed over all regimes: `0.1403`.

| Video | Mean F1 original | Mean F1 rank-severe | Mean F1 exposure-severe |
|---|---:|---:|---:|
| DALI | 0.1948 | 0.1816 | 0.2018 |
| HANGZHOU | 0.1808 | 0.1442 | 0.1469 |
| WUHAN | 0.2327 | 0.1990 | 0.2336 |

## Resource monotonicity and anytime quality

For nested StaticProxyRank and TemporalCoverage traces, monotonicity is `YES` with `0.48%` transition violations.  UniformTemporal exact subsets are non-nested and excluded from the primary anytime reliability judgment.  `ANYTIME_BUDGET_CURVES.csv` contains normalized trapezoidal AUC from `(0,0)` plus marginal F1/oracle-call values.

More oracle calls can expose additional positives but can also add false events under a precision-sensitive event metric.  A violation is thus a genuine query-result reliability finding, not floating noise (epsilon `1e-12`).

## Poor-vs-good gap compression

Current policies compress the gap: `PARTIAL`.  The best high-budget descriptive compression is `0.2164079385968407`; undefined ratios remain blank when the budget-5 denominator is zero.  Ranking and exposure gaps are reported separately in `PROXY_GAP_COMPRESSION.csv`.

## Robust-policy comparison

| Policy | Worst poor-regime mean F1 | Poor-regime Anytime AUC | Monotonic violations | Robust rank |
|---|---:|---:|---:|---:|
| StaticProxyRank | 0.2079 | 0.2730 | 0.95% | 1 |
| UniformTemporal | 0.1927 | 0.2323 | 13.33% | 2 |
| TemporalCoverage | 0.1046 | 0.1261 | 0.00% | 3 |

The robust rank is not best-point cherry-picking: it follows the pre-frozen lexicographic rule (worst poor-regime F1, poor Anytime AUC, then monotonicity).

## Materialization comparison and interaction

Historical model-relative median K3−K0 is `+0.1457`; mechanism ablation attributes about `+0.1377` to C1.  With C1 fixed, current policy spread is `0.1403`.  The representative same-trace C0/C1 subset yields interaction `SYSTEMATIC` with subgroup range `0.2573`.  This determines whether the stages can be treated as nearly separable in the paper.

## Adaptive action-selection opportunity

`ACTION_SELECTOR_OPPORTUNITY = WEAK`; `CONTEXTUAL_BANDIT_REOPEN = NO`.  Cached counterfactuals contain both SCAN-better and VERIFY-better states, but observable-state learned rules have more regret than a tiny-regret fixed always-VERIFY policy.  The current precomputed-candidate replay does not test progressive SCAN/VERIFY control.

## Mainline interpretation

The selected route is `TWO_STAGE_UNIFIED`.  Full K3 remains unsupported as the core algorithm; C1 is the frozen supported materialization operator.  Deadline awareness remains contextual because the current quality curves are invocation-budget curves.

## Evidence limitations and conflicts

1. Proxy degradations are prospective, deterministic and outcome-blind, but synthetic; no natural three-regime proxy family exists on this current interface.
2. The reference is Qwen model-relative and K3-grouped.  Independent human continuity remains pending; SmolVLM evidence remains inconclusive.
3. One candidate per unit makes original exposure recall trivially 100%; this design tests ranking, while thinning is only a stress model of exposure loss.
4. UniformTemporal is non-nested across budgets; its curves must not be called strict anytime execution.
5. Historical controller results use different videos/references and abstract or physical costs; they support thesis provenance, not the current primary matrix.
6. The P0 report's broad anti-overmerge language is stronger than its causal mechanism ablation: duration-cap and queried-negative-barrier marginal medians are zero; gap-only C1 carries the demonstrated median gain.

## Single next experiment

Run one preregistered **natural-proxy replication** on the same frozen three-video/unit interface using a second maintained cheap visual proxy, without tuning on semantic labels.  It is the single experiment that can distinguish robust query-policy evidence from artifacts of synthetic corruption while preserving C1 and the evaluation contract.
