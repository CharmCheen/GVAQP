# Agent Loop Final Summary — V13.8 → V13.9

**Date:** 2026-06-23

## Stages Completed

| Stage | Status | Decision |
|---|---|---|
| V13.8 Full Center10 Oracle | ✅ Complete | FULL_CENTER10_ORACLE_REFERENCE_READY |
| V13.9 Latency-Aware AQP | ✅ Complete | LATENCY_AWARE_AQP_FAIL |

## V13.8 Key Metrics

- 399/399 anchors processed (100% success, 0 failures)
- 94 positive anchors (23.6%), 0% abstain
- 51 stitched VLM-oracle-relative events
- 100% complete events, 0% truncation
- GPU: A800, 74 min runtime

## V13.9 Key Metrics

- 19 methods × 5 budgets evaluated on full oracle
- Best B=20 event recall: 0.137 (uniform, NOT proxy)
- Best B=40 event recall: 0.216 (top_fusion_geometry_motion)
- Proxy delta vs random at B=20: +0.059 (fails +0.10 threshold)
- Proxy delta vs random at B=80: +0.196 (but B=80 is 20% of full scan)

## Why Proxy Methods Fail at Low Budgets

1. **Sparsity**: 51 events in 66.5 min → 13% of anchors are event-bearing. At B=20 (5% of anchors), expected hit is ~2.6 events.
2. **Weak proxy correlation**: YOLO vehicle count correlates with dense traffic, not ego-path entry events.
3. **Uniform is hard to beat**: Even spacing provides good temporal coverage that proxy scores can't overcome at low budgets.
4. **V13.7 bias revealed**: The V13.7 labeled subset (25% high-YOLO) inflated proxy performance by ~3×.

## Output Paths

### V13.8
```
test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/
├── tables/center10_full_oracle_labels.csv       (399 rows)
├── tables/center10_vlm_oracle_events.csv         (51 events)
├── tables/center10_event_stitching_trace.csv
├── raw_vlm_responses/                            (399 JSON)
└── reports/FINAL_REPORT.md
```

### V13.9
```
test_vlm/outputs/v13_9_latency_aware_center10_aqp_v1/
├── tables/method_budget_results.csv              (95 rows)
├── tables/method_selected_anchors.csv
├── tables/event_hit_trace.csv
├── tables/random_seed_summary.csv
├── tables/best_methods_by_budget.csv
└── reports/FINAL_REPORT.md
```

## Final Decisions

- V13.8: `FULL_CENTER10_ORACLE_REFERENCE_READY`
- V13.9: `LATENCY_AWARE_AQP_FAIL`

## Next Action

**Introduce 8B cascade or representation-based proxy.** The current cheap proxy features (YOLO count + motion energy) are insufficient for budgeted event recovery. Options:

1. **8B cascade**: Use Qwen3-VL-8B as a cheap first-pass scorer on all 399 anchors, then apply 32B only to top-ranked anchors. The 8B model may capture semantic features (ego-path conflict) that YOLO counts miss.

2. **Representation-based proxy**: Compute CLIP/SigLIP embeddings for each anchor and use embedding similarity to known conflict scenes for ranking.

3. **Boundary refinement**: For the 94 positive anchors, run 2s refinement VLM to get tighter event boundaries. This won't help with the budgeted recall problem but would improve returned-duration efficiency.

4. **Revisit proxy features**: Compute more targeted features (optical flow direction, ego-lane estimation, object trajectory toward ego path) rather than raw vehicle counts.

## Caveats

1. All labels are VLM_ORACLE_RELATIVE (Qwen3-VL-32B), not human truth.
2. Single video only (realcartest.mp4, 66.5 min). No generalization claim.
3. YOLOv8n was used for proxy features. YOLOv8x or larger models might provide better features.
4. No certificate simulation was run.
5. The "event" definition is O_enter_ego_path_v0 as interpreted by Qwen3-VL-32B.

## Loop Final Decision

```
LOOP_FINAL_DECISION: V13_9_NEEDS_8B_OR_REPRESENTATION_CASCADE
```

The full center10 oracle reference (V13.8) is valid and useful. But current cheap proxy features are insufficient for budgeted AQP. A better first-pass scorer (8B VLM cascade or representation-based proxy) is needed before re-evaluating budgeted query plans.
