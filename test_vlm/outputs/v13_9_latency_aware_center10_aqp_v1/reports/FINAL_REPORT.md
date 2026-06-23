# V13.9 Final Report — Latency-Aware AQP Simulation

**Date:** 2026-06-23
**Oracle reference:** V13.8 full center10 (399 anchors, 51 events)

## 1. Goal

Evaluate whether proxy-guided anchor selection can recover VLM-oracle events at strict 32B call budgets.

## 2. Methods Compared

19 methods × 5 budgets (B32=5,10,20,40,80) = 95 evaluations

## 3. Results

| B32 | Best Method | Event Recall | Random Mean | Delta |
|---|---|---|---|---|
| 5 | top_yolo_vehicle_max | 0.098 | 0.016 | +0.082 |
| 10 | top_yolo_vehicle_max | 0.098 | 0.027 | +0.071 |
| **20** | **uniform_anchor_10s** | **0.137** | 0.078 | +0.059 |
| 40 | top_fusion_geometry_motion | 0.216 | 0.165 | +0.051 |
| 80 | hybrid_50_proxy_50_uniform | 0.451 | 0.255 | +0.196 |

## 4. Decision Rules Applied

```
STRONG_PASS: B20 event_recall >= 0.60 AND delta >= 0.15 AND B40 >= 0.75
  → B20: 0.137 < 0.60 → NOT MET

PASS: B20 >= 0.45 AND delta >= 0.15, OR B40 >= 0.60
  → B20: 0.137 < 0.45, B40: 0.216 < 0.60 → NOT MET

PARTIAL: delta >= 0.10 at some budget
  → max delta = +0.082 at B5, +0.196 at B80
  → At B20 (primary): delta = +0.059 < 0.10 → NOT MET

FAIL: methods do not beat random meaningfully
  → uniform_anchor_10s beats proxy at B20 → PROXY NOT MEANINGFUL
  → APPLIES
```

## 5. Why Proxy Methods Underperform

The V13.7 labeled-subset results (0.448 recall at B20) were biased by pilot sampling (25% high-YOLO samples). On the unbiased full 399-anchor oracle:

1. **Events are sparse**: 51 events in 399 anchors (13% event-bearing anchors). At B=20 (5% of anchors), expected hit is ~2.6 events regardless of method.
2. **YOLO vehicle count is weakly correlated with O_enter_ego_path_v0 events**: High-vehicle-count anchors often contain dense traffic, not ego-path conflicts.
3. **Uniform sampling is competitive**: At B=20, uniform spacing beats all proxy methods. At B=40, proxy advantage is only +0.051 over random.
4. **Motion energy is noisy**: Motion energy captures many non-event motions (turning, braking in traffic) that don't correspond to ego-path entry.

## 6. Output Files

- `tables/method_budget_results.csv` (95 rows)
- `tables/method_selected_anchors.csv`
- `tables/event_hit_trace.csv`
- `tables/random_seed_summary.csv`
- `tables/best_methods_by_budget.csv`

## 7. Gate Decision

```
V13_9_DECISION: LATENCY_AWARE_AQP_FAIL
```

Proxy-guided anchor selection does not provide meaningful advantage over uniform sampling on the unbiased full-video center10 oracle reference. Event recovery at low budgets is dominated by temporal coverage rather than proxy quality.
