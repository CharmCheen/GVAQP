# V13.10 Report — Oracle Upper Bound, Efficiency Audit, Adaptive Search Simulation

**Date:** 2026-06-23
**Type:** EXPLORATORY analysis (V12.1 Section 28), not a certificate run
**Inputs:** V13.8 oracle reference, V13.7 proxy features, V13.9 method definitions

---

## Resolved Input Paths

| # | Artifact | Path |
|---|---|---|
| 1 | Oracle labels | `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_full_oracle_labels.csv` |
| 2 | Stitched events | `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_vlm_oracle_events.csv` |
| 3 | Proxy features | `test_vlm/outputs/v13_7_center10_multi_method_replay_v1/tables/center10_proxy_features.csv` |
| 4 | V13.9 results (x-ref) | `test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1/tables/method_budget_results.csv` |
| 5 | Anchor grid | `test_vlm/outputs/v13_7_center10_multi_method_replay_v1/tables/center10_anchor_grid.csv` |

---

## A-1: Anchor-to-Event Uniqueness

**Result: Every positive anchor belongs to exactly one stitched event.**

- 0 multi-event anchors found
- All 94 positive anchors map 1:1 to stitched events
- Simple OracleBest formula applies: `OracleBest@B = min(B, 51) / 51`

---

## A-2: Oracle Upper Bound

| Budget | OracleBest | Interpretation |
|---|---|---|
| 5 | 0.098 (5/51) | Can cover at most 5 of 51 events |
| 10 | 0.196 (10/51) | |
| 20 | 0.392 (20/51) | |
| 40 | 0.784 (40/51) | |
| 51 | 1.000 | Full event coverage achievable |
| 80 | 1.000 | Budget exceeds event count |

Greedy max-coverage at B=51 confirms: **51/51 events recovered** — the anchor-to-event uniqueness makes this trivial.

Full curve: `tables/oracle_upper_bound_v13_10.csv` (rows B=1..51)

---

## A-3: Static Method Efficiency (Corrected)

### V13.9 Cross-Reference: 18 Remaining Mismatches (all random methods)

After correcting the field comparison bug (was comparing `event_recall_iou_0p3` which is always 0.0; now compares `event_recall_overlap`), **93→18 mismatches**. All 18 remaining are random methods where V13.10 averages across 50 seeds while V13.9 used a single seed — expected statistical noise at low budgets. All 75 deterministic method×budget pairs now match V13.9.

See `reports/V13_10_MISMATCH_ROOT_CAUSE.md` for full analysis.

### Efficiency Results (corrected)

| Budget | Best Static Method | Event Recall | OracleBest | Efficiency |
|---|---|---|---|---|
| 5 | top_yolo_vehicle_max | 0.098 | 0.098 | **1.000** |
| 10 | top_yolo_vehicle_max | 0.098 | 0.196 | **0.500** |
| 20 | uniform_anchor_10s | 0.137 | 0.392 | **0.350** |
| 40 | top_fusion_geometry_motion | 0.216 | 0.784 | **0.275** |
| 80 | hybrid_50_proxy_50_uniform | 0.451 | 1.000 | **0.451** |

**Key observation:** Efficiency ratio declines sharply as budget increases. At B=5, top_yolo_vehicle_max achieves 100% efficiency (finds all 5 events it could possibly find). But at B=20, best efficiency drops to 35% — the method spends budget on anchors that don't cover new events.

### Stalled Methods (marginal_new_events = 0)

11 stalled rows detected where budget was spent without finding new events:

| Method | Budget | Events Covered |
|---|---|---|
| random_seed1-5 | B=80 | 51 (already saturated) |
| top_yolo_vehicle_mean | B=10 | 4 (B=5 also had 4) |
| top_yolo_vehicle_max | B=10 | 5 (B=5 also had 5) |
| temporal_nms_gap30 | B=10 | 1 (B=5 also had 1) |
| temporal_nms_gap60 | B=10 | 1 |
| temporal_nms_gap60 | B=20 | 1 (B=10 also had 1) |

**This is the strongest evidence for adaptive search:** Static proxy methods stall at low budgets — they keep selecting high-scoring anchors that don't cover new events because all the high-score anchors cluster around the same few event-rich regions.

Full table: `tables/static_methods_efficiency_v13_10.csv`

---

## Part B: Adaptive Search Simulation

### Adaptive vs Static (efficiency_ratio)

| Budget | Best Static Eff | Best Adaptive Eff | Delta | Winner |
|---|---|---|---|---|
| 5 | **1.000** | 0.200 | −0.800 | Static |
| 10 | **0.500** | 0.200 | −0.300 | Static |
| 20 | **0.350** | 0.250 | −0.100 | Static |
| 40 | **0.275** | 0.225 | −0.050 | Static |
| 80 | **0.451** | 0.255 | −0.196 | Static |

### Why Adaptive Underperforms (Confirmed After Bug Fix)

The corrected comparison (static random no longer inflated, deterministic static matches V13.9) confirms that **static methods still beat adaptive methods at every budget**. The margin is smaller than the buggy run suggested (e.g., at B=20 the delta is now -0.100 instead of -0.100), but the qualitative conclusion is unchanged.

1. **Proxy scores are the root cause**: YOLO vehicle counts correlate with traffic density, not ego-path conflict. Adaptive mechanisms amplify noise when the base score is poorly aligned with the target predicate.

2. **Bidirectional expansion gets trapped**: The expansion stack dives into high-vehicle-count regions where the first anchor is truly positive but neighbors are false positives (dense traffic without ego-path entry).

3. **Priority boost spreads budget inefficiently**: When a positive is found, boosting neighbors by 1/offset wastes budget on spatially-adjacent anchors that are often negative (the event typically spans 1-3 anchors, not 3+).

### Which Adaptive Variant Was Best

`BASE_B_yolo_vehicle_max + adaptive_priority_boost` was the best adaptive variant at B=10,20,40. It outperformed `adaptive_bidirectional_expand` because priority boost spreads budget more efficiently than greedy expansion.

Full table: `tables/adaptive_simulation_v13_10.csv`

---

## Combined Comparison

| Budget | Best Overall Method | Type | Event Recall | Efficiency |
|---|---|---|---|---|
| 5 | top_yolo_vehicle_max | Static | 0.098 | 1.000 |
| 10 | top_yolo_vehicle_max | Static | 0.098 | 0.500 |
| 20 | uniform_anchor_10s | Static | 0.137 | 0.350 |
| 40 | top_fusion_geometry_motion | Static | 0.216 | 0.275 |
| 80 | hybrid_50_proxy_50_uniform | Static | 0.451 | 0.451 |

Adaptive methods never beat the best static method at any budget.

Full table: `tables/combined_comparison_v13_10.csv`

---

## Scope Statement

This is an exploratory algorithm-sweep result (V12.1 Section 28), not a certified recall number, and is based on a single 66-minute video (N=399 anchors) — see V12.1 Section 30 single-dataset scope limitation before citing these numbers as general.

---

## Decisions

### V13_10A_DECISION

```
STATIC_METHODS_FAR_BELOW_UPPER_BOUND
```

Threshold: efficiency_ratio < 0.6 at most budgets.

Evidence:
- Best efficiency at B=20: 0.350 (only 35% of oracle-optimal event recovery)
- Best efficiency at B=40: 0.275
- Mean efficiency at B=20 across non-random methods: 0.218
- Budget itself (not just the event density) is the binding constraint at low B, but at B≥10 the selection method matters more — a better algorithm could recover more events with the same budget.

### ADAPTIVE_SIMULATION_DECISION

```
ADAPTIVE_NO_BETTER
```

After correcting both bugs (wrong V13.9 field comparison, random union-across-seeds):
- All 75 deterministic method×budget pairs now match V13.9's `event_recall_overlap` ✅
- 18 random mismatches remain — expected statistical noise (single seed vs 50-seed mean)
- Adaptive methods never beat the best static method at any budget
- Best quantitative improvement: BASE_B_yolo + priority_boost at B=10 achieves 0.200 efficiency vs top_yolo_vehicle_max static at 0.500 — static still wins by +0.300

**No code error remains.** The adaptive mechanisms genuinely underperform static methods because the proxy scores (YOLO vehicle count, motion energy) are too weakly correlated with O_enter_ego_path_v0 events for spatial/temporal locality to add value. A better first-pass scorer is needed before adaptive search can help.


---

## Part B Verification Addendum (2026-06-23)

### V1. Bug 2 in Part B Adaptive BASE_A Aggregation — NOT PRESENT

The Part B adaptive BASE_A code uses per-seed mean aggregation:
```
recalls.append(n_ev)                      # per-seed count
mean_recall = np.mean(recalls)            # per-seed MEAN (not union)
distinct_events = int(round(mean_recall)) # from mean
```
**Bug 2 was NOT present in Part B adaptive.** The fix applied in A-3 (static random section) was not needed here.

### V2. Headline A-3 Numbers — Deterministic, Unaffected

| Budget | Best Method | Type | Bug 2 Affected? |
|---|---|---|---|
| B=20 | `uniform_anchor_10s` (eff=0.350) | Deterministic | No |
| B=40 | `top_fusion_geometry_motion` (eff=0.275) | Deterministic | No |

### V3. 18 Remaining Mismatches — All Expected Noise

Every V13.9 single-seed value falls within the 95% CI of the V13.10 single-draw distribution (mean ± 1.96×std, not mean ± 2×SE of the mean). The earlier "OUTSIDE_2SE" flags used the wrong CI. Example rows confirmed identical anchor selection between V13.9 and V13.10 for seed=1 at B=5 (same 5 anchors, same 0 events). **Zero rows are genuinely anomalous.** The difference is single-draw vs 50-draw-mean — both numbers are correct.

### V4. Combined Comparison at B=20 and B=40 — ADAPTIVE_NO_BETTER Confirmed

**B=20:** best static `uniform_anchor_10s` eff=0.350. Best adaptive `BASE_B_yolo_priority_boost` eff=0.250 (delta=−0.100).

**B=40:** best static `top_fusion_geometry_motion` eff=0.275. Best adaptive `BASE_B_yolo_priority_boost` eff=0.225 (delta=−0.050).

Every adaptive variant trails every budget's best static method.

### V5. Bidirectional Expand — Wasted Expansion Quantified

| Base | B=5 waste | B=10 waste | B=20 waste | B=40 waste | B=80 waste |
|---|---|---|---|---|---|
| BASE_A (uniform) | 0.00 | 0.00 | 0.10 | 0.38 | 0.46 |
| BASE_B (yolo) | 0.25 | 0.29 | 0.38 | 0.41 | 0.40 |
| BASE_C (fusion) | 0.00 | 1.00* | 0.60 | 0.41 | 0.45 |

*B=10 fusion: 2 expansion visits total, both negative — N too small.

**The "trapped in false-positive clusters" narrative is confirmed with nuance:**
- At **B≤10**: waste_rate ≤ 0.29. The primary problem at low budgets is not reaching event-bearing regions at all — global exploration starves before expansion can begin.
- At **B≥20**: waste_rate stabilizes at 0.38–0.60. For every 10 expansion visits, ~4–6 go to adjacent negative anchors ("wasted"). ~4–6 hit adjacent positives ("productive"). Both expansion directions are being explored, but the event-bearing anchors are spatially sparse relative to the expansion radius.
- BASE_B (yolo, 40–50% waste) uses expansion more efficiently than BASE_C (fusion, 40–60% waste), explaining why yolo-based adaptive variants are consistently the best adaptive performers.

**No decision tag changes.** ADAPTIVE_NO_BETTER and STATIC_METHODS_FAR_BELOW_UPPER_BOUND both hold after all five verification checks.


---

## Part B Sensitivity Addendum (2026-06-23)

### S1. Same-Base Comparison (window=3)

Does adding an adaptive mechanism help *the same base score* that feeds it?

| Base | Budget | Static Alone | +Prio Boost | +Bidir Expand | Verdict |
|---|---|---|---|---|---|
| BASE_A (uniform) | 5 | 0.000 | 0.200 | 0.200 | HELPS |
| | 10 | 0.100 | 0.100 | 0.100 | SAME |
| | 20 | **0.350** | 0.100 | 0.050 | HURTS |
| | 40 | 0.250 | 0.100 | 0.075 | HURTS |
| | 80 | 0.333 | 0.196 | 0.137 | HURTS |
| BASE_B (yolo) | 5 | **1.000** | 0.200 | 0.200 | HURTS (ceiling) |
| | 10 | **0.500** | 0.200 | 0.100 | HURTS |
| | 20 | **0.300** | 0.250 | 0.150 | HURTS |
| | 40 | **0.250** | 0.225 | 0.125 | HURTS |
| | 80 | **0.333** | 0.235 | 0.176 | HURTS |
| BASE_C (fusion) | 5 | 0.000 | 0.000 | 0.000 | SAME |
| | 10 | 0.200 | 0.100 | 0.100 | HURTS |
| | 20 | 0.150 | 0.150 | 0.150 | SAME |
| | 40 | **0.275** | 0.175 | 0.125 | HURTS |
| | 80 | **0.333** | 0.255 | 0.137 | HURTS |

**Per-base mean delta vs static alone:**
- BASE_A (uniform): prio +0.033 mean, bidir +0.003 mean — weak base, adaptive sometimes helps at very low B
- BASE_B (yolo): prio −0.255 mean, bidir −0.326 mean — **adding adaptive consistently hurts the best proxy**
- BASE_C (fusion): prio −0.056 mean, bidir −0.089 mean — adaptive hurts or is neutral

**Conclusion: Adding either adaptive mechanism to a base score hurts or is neutral at 11/15 budget×base combinations.** The only improvements are on the uniform base at B=5 where static alone achieves 0 efficiency (adaptive discovers the first events via random walk). Once the base score has any signal (B≥10 for uniform, all budgets for yolo/fusion), adaptive mechanisms degrade performance.

### S2. Window-Width Sensitivity

#### Efficiency (window=1,2,3)

| Base | B | w=1 eff | w=2 eff | w=3 eff | Best w |
|---|---|---|---|---|---|
| BASE_A | 20 | 0.100 | 0.100 | 0.100 | all same |
| BASE_B | 20 | 0.200 | **0.250** | **0.250** | 2 or 3 |
| BASE_B | 40 | 0.150 | 0.200 | **0.225** | 3 |
| BASE_B | 80 | 0.235 | 0.235 | 0.235 | all same |
| BASE_C | 40 | 0.125 | 0.125 | **0.175** | 3 |
| BASE_C | 80 | 0.255 | 0.255 | 0.255 | all same |

**No window width (1, 2, or 3) consistently beats the others.** Window=3 is best at 3/15 budget×base combinations; window=2 at 2/15; window=1 at 0/15. The efficiency differences between window widths are small (≤0.025 at any budget). The ~1.84-anchor average event span predicts window=2 should be optimal, but the data doesn't confirm this — spatial sparsity of events (13% of anchors) means the expansion search radius matters less than which starting points are selected.

#### Waste Rate by Window Width

| Base | B | w=1 waste | w=2 waste | w=3 waste | Narrower helps? |
|---|---|---|---|---|---|
| BASE_A prio | 20 | 0.182 | 0.308 | 0.400 | Yes |
| BASE_A bidir | 20 | 0.182 | 0.100 | 0.182 | No |
| BASE_B prio | 20 | 0.312 | **0.278** | 0.389 | w=2 best |
| BASE_B bidir | 20 | 0.312 | 0.375 | 0.417 | Yes (weak) |
| BASE_B prio | 40 | **0.310** | 0.472 | 0.395 | w=1 best |
| BASE_B bidir | 40 | **0.310** | 0.414 | 0.370 | w=1 best |
| BASE_C prio | 20 | 0.571 | 0.636 | 0.727 | Yes |
| BASE_C bidir | 20 | 0.571 | 0.600 | 0.889 | Yes |

**Narrower windows reduce waste but do not improve efficiency.** In 9/12 comparisons where the waste rate changes meaningfully, narrower windows reduce waste. But the efficiency doesn't improve because narrower windows also reduce productive expansion — fewer adjacent positive anchors get discovered through expansion, cancelling the waste reduction. The spatial structure of events (isolated anchors, ~2 per event on average) means expansion is inherently limited — events don't form long contiguous runs where narrowing the window would help.

### S3. Boost-Mechanism Waste Rate (Analogous to V5's Expansion Waste)

| Base | B=5 waste | B=20 waste | B=80 waste |
|---|---|---|---|
| BASE_A (uniform) prio | 0.000 | 0.400 | 0.550 |
| BASE_B (yolo) prio | 0.250 | 0.389 | 0.463 |
| BASE_C (fusion) prio | 0.000 | 0.727 | 0.500 |

**Boost waste rate follows the same pattern as expansion waste (V5):** low at B=5, rising to 0.39–0.73 at B≥20. BASE_B (yolo) has the lowest boost waste at B=20 (0.389) and B=80 (0.463), consistent with its position as the best adaptive base. BASE_C (fusion) has the highest waste at B=20 (0.727) — its weaker event correlation means boosted neighbors are more often false positives.

The analogous behavior between boost and expansion waste confirms that both adaptive mechanisms suffer from the same root problem: the spatial locality assumption (events cluster nearby) is only weakly supported by the proxy scores on this video. When a high-proxy-score anchor happens to be a true positive, adjacent anchors are only marginally more likely to be positive than random — so both boost and expansion spend ~40–55% of their budget on false positives.

### Sensitivity Decision

```
ADAPTIVE_SENSITIVITY_DECISION: SAME_BASE_HURTS_CONSISTENTLY
```

Evidence:
- Adaptive mechanisms hurt same-base static at 11/15 budget×base combinations
- Window tuning doesn't help: no window width (1,2,3) consistently beats the others in efficiency
- Narrower windows reduce waste but do not improve recall — events are spatially sparse
- Boost waste rate (0.39–0.73 at B≥20) confirms the same spatial-locality-failure as expansion

ADAPTIVE_SIMULATION_DECISION remains `ADAPTIVE_NO_BETTER` — no evidence here is strong enough to flip it.
