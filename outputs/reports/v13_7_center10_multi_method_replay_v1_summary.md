# V13.7 Center10 Multi-Method Replay — Compact Summary

**Date:** 2026-06-23
**Full report:** `test_vlm/outputs/v13_7_center10_multi_method_replay_v1/reports/FINAL_REPORT.md`

## What This Is

A **no-new-VLM replay** using existing V13.6 labels to compare 17 center10 anchor selection methods across 8 budgets. No GPU inference — pure data processing from V13.5 proxy features and V13.6 VLM labels.

## Key Result: Proxy Methods Beat Random by ≥0.10 at All Budgets

| Budget | Best Method | Recall | vs Random | vs Uniform |
|---|---|---|---|---|
| **B=5** | top_yolo_vehicle_mean | 0.172 | +0.172 | +79% enrich |
| **B=10** | top_yolo_vehicle_mean | 0.207 | +0.186 | +20% enrich |
| **B=20** | top_yolo_vehicle_max | **0.448** | +0.414 | +17% enrich |
| **B=40** | top_yolo_vehicle_max | **0.517** | +0.414 | +3% enrich |

## Method Rankings

1. **YOLO vehicle count** (top_yolo_vehicle_max/mean) — best at all budgets
2. **Fusion yolo+motion** (top_fusion_yolo_motion) — competitive at low budgets
3. **Hybrid proxy+uniform** (hybrid_70_30) — good defense against proxy blind spots
4. Motion energy alone — beats random but weaker than YOLO
5. Temporal NMS — underperforms due to coverage loss

## Cost Reduction

| Pipeline | Full Calls | Budgeted (B=20) | vs 5s baseline |
|---|---|---|---|
| fixed_5s_nonoverlap | 798 | 798 | 1.00× |
| center10_uniform_anchor | 399 | 399 | 0.50× |
| **center10_proxy_guided** | 399 | **20** | **0.025×** |

## Artifacts (7 tables, 4 reports)

- `center10_anchor_grid.csv` — 399 anchors
- `center10_proxy_features.csv` — 399 anchors with 19 features
- `center10_labeled_eval_subset.csv` — 52 labeled clips
- `method_budget_results.csv` — 136 method×budget evaluations
- `method_selected_anchors.csv` — per-method anchor selections
- `fixed5_vs_center10_comparison.csv` — pipeline comparison

## Caveat

Labeled subset is **pilot-derived and biased** (25% high-YOLO samples). Findings overestimate proxy performance on unbiased full grid. Full center10 oracle reference needed for unbiased evaluation.

## Decision

```
FINAL_DECISION: CENTER10_FULL_REFERENCE_RECOMMENDED
```

Run Qwen3-VL-32B on all 399 center10 anchors to build an unbiased full-video VLM-oracle-relative reference.
