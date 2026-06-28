# HIGH_SELECTIVITY_SCOUT.md

## Scope

Scout for candidate predicates that could be used for high-selectivity dense estimation, **without running new models or new oracle calls**.

## Available Data

### dataset3 (canonical anchor, 347 anchors, center10_10s)
- Oracle labels (Qwen) per anchor: 40 positives, 27 clusters (21 singleton + 6 multi-anchor)
- Per-anchor proxy features: object_count_mean, vehicle_count_mean, near_ego_vehicle_count_mean, person_count_mean, motion_energy_mean, lateral_presence_mean
- Track transition features: has_outside_to_inside_transition, n_transition_tracks (from track-transition analysis)

### realcartest (V13, 399 anchors, center10_10s)
- Oracle labels (Qwen) per anchor: 94 positives, by object: vehicle=67, pedestrian=13, cyclist=13, motorcycle=1
- 51 stitched events (all enter_ego_path type)
- Per-anchor proxy features: NOT directly available for the 399 V13 anchors. The kinematic_proxy/proxy_scores.csv has 102 rows for a different realcartest_5k clip, not 1:1 with V13 anchors.
- v13.9 method_budget_results has method-level results (95 rows x 20 cols) but not per-anchor proxy

## Predicate Scout (dataset3)

Base positive rate: 40/347 = 11.53%
Base cluster coverage: 26/27 = 96.3% (1 cluster has all anchors negative, which is the "negative" cluster -1)

### Top 10 most selective predicates (candidates >= 20)

| Predicate | Candidates | Positives | Rate | Singletons | Clusters | Coverage | Selectivity |
|-----------|-----------|-----------|------|------------|----------|----------|-------------|
| person_count_mean > 2 | 33 | 16 | 48.5% | 7/21 | 12/27 | 44.4% | 4.21x |
| person_count_mean > 1 | 75 | 24 | 32.0% | 10/21 | 15/27 | 55.6% | 2.78x |
| object_count_mean > 10 | 51 | 10 | 19.6% | 3/21 | 7/27 | 25.9% | 1.70x |
| person_count_mean > 0 | 193 | 37 | 19.2% | 19/21 | 25/27 | 92.6% | 1.66x |
| lateral_presence_mean > 3 | 149 | 28 | 18.8% | 13/21 | 19/27 | 70.4% | 1.63x |
| lateral_presence_mean > 2 | 210 | 35 | 16.7% | 17/21 | 23/27 | 85.2% | 1.45x |
| object_count_mean > 7 | 137 | 22 | 16.1% | 10/21 | 15/27 | 55.6% | 1.39x |
| object_count_mean > 5 | 210 | 31 | 14.8% | 15/21 | 21/27 | 77.8% | 1.28x |
| lateral_presence_mean > 1 | 283 | 37 | 13.1% | 19/21 | 25/27 | 92.6% | 1.13x |
| motion_energy_mean > 30 | 177 | 23 | 13.0% | 12/21 | 17/27 | 63.0% | 1.13x |


### Key findings

1. **person_count_mean > 2** is the most selective: 16/33 = 48.5% positive rate (4.21x base). But:
   - Only 12/27 clusters covered (44% coverage)
   - Only 7/21 singletons captured
   - Misses pedestrian/cyclist-free vehicle events

2. **person_count_mean > 1**: 24/75 = 32.0% rate (2.78x base)
   - 15/27 clusters (56% coverage)
   - 10/21 singletons (48%)
   - Captures the "people nearby" cluster (pedestrian events)

3. **lateral_presence_mean > 3**: 28/149 = 18.8% rate (1.63x base)
   - 19/27 clusters (70% coverage)
   - 13/21 singletons (62%)
   - Broader coverage, more selective than base

4. **object_count_mean > 10**: 10/51 = 19.6% rate (1.70x base)
   - 7/27 clusters (26% coverage)
   - 3/21 singletons (14%)
   - High-density-only

5. **near_ego_vehicle_count_mean > 0**: 32/324 = 9.9% rate (0.86x base, UNDER-enriched)
   - This is the ego-corridor signal; it's under-enriched for positives
   - Consistent with the track-transition negative finding

### Predicate combinations

Some predicates may be combined:
- `person_count_mean > 0` AND `lateral_presence_mean > 1`: 25/157 anchors, ~16% positive rate
- `object_count_mean > 5` AND `lateral_presence_mean > 1`: 22/124 anchors, ~18% positive rate

These could be useful for a "high-selectivity dense estimation" branch, but require explicit calculation.

### Track transition features

- `has_outside_to_inside_transition`: 26/40 positives with transition (65.0%) - UNDER-enriched (0.78x)
- Not useful as a selectivity booster on dataset3 (consistent with track-transition negative result)

## Realcartest

realcartest has V13 oracle labels (94/399 positives, 51 events) but **lacks per-anchor proxy features for the 399 V13 anchors** in directly accessible form. The kinematic_proxy pipeline was run on a 102-clip subset (realcartest_5k), which is a different set of anchors from the V13 399-anchor set.

Without per-anchor proxy for V13's 399 anchors, predicate-based dense estimation on realcartest requires either:
- Re-running YOLOv8n on V13 anchors (forbidden)
- Using the kinematic_proxy 102-clip subset (different anchor set, not 1:1)
- Joining V13 anchors to kinematic_proxy by time (approximate, not 1:1)

So **realcartest predicate scout is not possible** without new model inference.

## No-new-oracle pilot feasibility

For dataset3:
- All required data is in place
- Predicate subsets can be evaluated against existing Qwen labels
- The most selective predicate (`person_count_mean > 2`) gives 4.21x enrichment but only 44% cluster coverage
- Trade-off between selectivity and coverage is the key design question

For realcartest:
- Labels exist (V13 oracle)
- Per-anchor proxy features do NOT exist for the 399 V13 anchors
- Cannot run a no-new-oracle pilot without first producing per-anchor proxy for the 399 V13 anchors

## Decision

**`HIGH_SELECTIVITY_PILOT_AVAILABLE_NO_NEW_ORACLE` (for dataset3 only)**

Conditions:
- dataset3 has full Qwen labels + per-anchor proxy + cluster/singleton metadata
- A no-new-oracle dense estimation pilot is feasible: define predicate(s), measure positive rate / cluster coverage, compare with L3 baseline
- The most selective dataset3 predicate (`person_count_mean > 2`, 4.21x) covers 44% of clusters and 33% of singletons — useful for "high-selectivity dense estimation" framing
- The complementary predicate `lateral_presence_mean > 3` covers 70% of clusters at 1.63x selectivity — better for "broader coverage with selectivity boost" framing

For realcartest, the per-anchor proxy is missing for the 399 V13 anchors (only the 102-clip kinematic_proxy subset is available). Realcartest cannot be piloted without new YOLO inference.

## Recommendation

If the project wants to pursue the high-selectivity branch:

1. **dataset3 first**: pilot a predicate-based dense estimation replay on existing data
   - Test: predicate -> uniform sampling vs L3 top-B vs predicate-conditioned L3
   - Metrics: positive rate, cluster coverage, singleton coverage, anchor recall at fixed B
2. **realcartest deferred**: needs per-anchor proxy for the 399 V13 anchors first, which requires new YOLO (forbidden by current task)
3. The predicate with best selectivity-coverage trade-off is `person_count_mean >= 1` (2.78x, 56% cluster coverage) or `lateral_presence_mean > 3` (1.63x, 70% cluster coverage). Avoid `object_count_mean > 10` (only 26% cluster coverage).
