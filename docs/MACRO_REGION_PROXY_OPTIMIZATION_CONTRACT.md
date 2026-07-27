# Macro-Region Proxy Optimization Experiment Contract

```text
DOCUMENT_ID = MRPO-CONTRACT-V1
STATUS = FROZEN_BEFORE_AUTONOMOUS_SEARCH
RESEARCH_STAGE = CONSTRAINED_AUTONOMOUS_DEVELOPMENT
```

## Frozen objective and scope

The sole question is whether a legal low-cost preview can rank macro-regions by
evaluator-only residual distinct-event yield. The proxy is a value ranker, not
an event classifier, hard filter, reference replacement, or Oracle replacement.

```text
PRIMARY_STAGE = STATIC_MACRO_REGION_RANKING
SECONDARY_STAGE = ONE_STEP_REGION_ALLOCATION_ONLY_AFTER_ALL_STAGE_A_GATES
GUARDED_MARGINAL_SCAN = STOPPED
RL_BANDIT_MDP_SMDP = PROHIBITED
CONFIRM_INTEGRATION = OUT_OF_SCOPE
EVENT_CLAIM_SCOPE = RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE
```

The two current complete videos are design inputs only. At least four new
independent validation videos and six total independent videos are required for
formal selection. Splits are whole-video only.

## Frozen units and labels

- Existing 10-second microchunk boundaries are immutable.
- Candidate macro lengths are exactly 40, 60, 90, and 120 seconds; at most one
  may be selected after design-only sensitivity analysis.
- Tail regions are retained with actual duration and cost.
- Each reference event maps to exactly one region by event midpoint; a midpoint
  exactly on a boundary maps to the smaller region index.
- The primary universe is offset-0 full-SCAN-exposable pseudo-reference events.
  All 268 references and the 263/268 full-SCAN ceiling are also reported.
- Stage-A residual labels use an empty initial-probe set (`H0 = EMPTY`).

## Legal preview search

At most four configurations may be evaluated from no more than three families:

1. `P0_METADATA_FRAMESTAT`: metadata and fixed sparse thumbnails; no DNN.
2. `P1_LOW_RATE_LOW_RESOLUTION_DETECTION`: frozen light detector, detection
   only, low resolution/rate, no full-SCAN cache or full-rate tracker.
3. `P2_COMPRESSED_OR_SPARSE_MOTION`: compressed-domain or sparse low-resolution
   motion, not full optical flow.

Every operator records decode, model, feature and total wall-clock, seconds per
video hour, peak memory, determinism, coverage and missingness. A primary
candidate must cost no more than 10% of full SCAN. Preview selection may not use
event labels.

## Feature and leakage contract

At most eight feature families are legal: object occupancy, class composition,
bbox geometry, motion/change, temporal aggregation, scene diversity/novelty,
preview-only weak triggers, and support/reliability.

The main model may not consume video/session/source identity, filenames,
absolute or normalized time position, references, candidate-event mapping,
full-SCAN candidates/detections/tracks, offline greedy rank, future reward/cost,
or split names. Time index is a negative control only.

## Models, controls, and metrics

At most five model families and 50 primary configurations are allowed. Permitted
families are fixed heuristic, L2 logistic, Poisson, justified over-dispersed
count regression, and constrained shallow tree/LightGBM. Deep sequence models,
foundation-model features, RL and bandits are prohibited. Prefer Logistic when
its primary metric is within 0.02 of the strongest complex model.

Mandatory controls are cost-matched random (100 seeds), constant global rate,
region cost only, time index only, best univariate, strongest geometric region
order, shuffled labels, shuffled scores, and evaluator-only full-information
order.

Primary metric is event Recall at 20% complete-region high-quality-SCAN cost;
regions are never partially selected. Secondary metrics include Recall@10/30,
ranking recall AUC, binary AUPRC/Brier, count MAE, Spearman, per-video and
leave-one-video-out direction, leave-best-region/video-out, contribution ratios,
preview cost, enrichment over cost-matched random, and net yield after paying
preview cost.

## Gates and stop rules

The two-video exploratory gate requires Recall@20 >= 0.40 and enrichment > 1.5
on both videos, wins over shuffled scores on both, macro-average win over time
index, preview ratio <= 0.10, and nonnegative net yield on both videos. Passing
may produce only `CANDIDATE_PROXY_HYPOTHESIS`.

Formal validation requires all G1–G6 conditions in the frozen user contract,
including macro Recall@20 >= 0.50, macro enrichment >= 2.5, control/stability
wins, preview ratio <= 0.10 and positive cost-adjusted yield. It cannot run
without at least four independent validation videos.

Search stops when gains are one-video-only, single-region-driven, cost-negative,
leaky, below the frozen recall gates, or require changing labels, references,
budgets or metrics. Only one repair cycle is allowed, solely for implementation,
schema, cache, boundary, accounting, numerical, or determinism defects.

The complete original authority text is the user-provided
`MRPO-CONTRACT-V1`; its SHA-256 is frozen into
`outputs/macro_region_proxy_optimization_v1/contracts/frozen_contract.json`.

