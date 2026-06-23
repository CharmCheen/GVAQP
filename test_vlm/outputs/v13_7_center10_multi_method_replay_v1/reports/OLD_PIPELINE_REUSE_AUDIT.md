# Stage 7: Old Pipeline Reuse Audit

## Reusable Scripts Found

| Script | Relevance | Classification |
|---|---|---|
| `nexar_candidate_feasibility_v2.py` | Full candidate generation + eval framework; IoU, event_hit, budget curves | **REUSE_WITH_ADAPTER** |
| `clip_aqp_phase1_candidate_v1/scripts/30_evaluate_candidates.py` | Candidate eval with recall, precision, budget curves | **REUSE_WITH_ADAPTER** |
| `clip_aqp_phase1_local_candidate_smoke_v1/scripts/40_evaluate_local_candidates.py` | Local candidate eval with IoU, budget | **REUSE_WITH_ADAPTER** |
| `kinematic_proxy/05_budget_simulation.py` | Budget curve simulation, SUPG budget allocation | **REUSE_WITH_ADAPTER** |
| `roadclip_budget_v2/05_run_budget_simulation.py` | Budget simulation with VLM oracle | **REUSE_WITH_ADAPTER** |
| `candidate_coverage_gate_v1/scripts/run_candidate_coverage_gate_v1.py` | Coverage gate logic | **NOT_REUSABLE** (Phase 0 specific) |
| `focused_validation_outputs/07_sampling_baseline_comparison/scripts/compare_sampling_baselines.py` | Sampling baseline comparison | **NOT_REUSABLE** (sampling-specific) |

## Reuse Strategy

The core evaluation functions (IoU computation, event hit counting, budget curve generation) from `nexar_candidate_feasibility_v2.py` and `30_evaluate_candidates.py` can be adapted for center10 anchor evaluation. The adaptation would:

1. Replace clip-based candidate generation with anchor-based selection
2. Replace Nexar-derived-boundary event labels with V13.6 VLM-oracle-relative labels
3. Use center10_proxy_features.csv for proxy scoring instead of 5s features

## Classification

```
REUSE_WITH_ADAPTER — core eval functions are reusable with minor adaptation
```

The evaluation logic (IoU, hit counting, recall curves) is well-tested and can be wrapped rather than rewritten. No scripts were modified.
