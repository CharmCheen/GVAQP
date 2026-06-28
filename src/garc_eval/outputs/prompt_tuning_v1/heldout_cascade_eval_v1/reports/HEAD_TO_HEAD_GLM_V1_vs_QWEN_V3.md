# GLM-4.1V (BEST prompt) vs Qwen3-VL-32B Reference — Held-Out Gate

**Date**: 2026-06-26
**Test set**: qwen_test_small.csv (10 samples: 2 positive, 8 negative)
**GLM prompt**: BEST_glm_final.md (v1_lower_threshold, tuning F1=0.706 on GLM test set)
**Status**: Held-out — GLM was NOT tuned on these samples

---

## Confusion Matrix

| GLM → / Qwen ↓ | positive | negative | uncertain | parse_error |
|-----------------|----------|----------|-----------|-------------|
| positive (2) | 2 | 0 | 0 | — |
| negative (8) | 3 | 4 | 0 | — |

## Metrics

| Metric | Value |
|--------|-------|
| GLM positive rate | 50.0% |
| GLM negative rate | 40.0% |
| GLM uncertain rate | 0.0% |
| Parse error count | 1 |
| **Recall (positive only)** | 100.0% (2/2) |
| **Recall (positive+uncertain)** | 100.0% (2.0/2) |
| **Qwen-positive in GLM negative** | 0 |
| Precision (positive only) | 40.0% |
| F1 (positive only) | 0.571 |

## Latency

| Stat | Value |
|------|-------|
| Avg latency | 32.41s |
| P50 latency | 27.89s |
| P95 latency | 67.05s |
| Avg output tokens | 752.4 |
| Contains `think` tags | 10/10 |

## Per-Sample Details

```
  center10_anchor_0230: gt=negative pred=positive conf=0.8 ✗ (20.9s, 385 tok)
  center10_anchor_0341: gt=negative pred=negative conf=0.9 ✓ (31.9s, 750 tok)
  center10_anchor_0251: gt=negative pred=negative conf=0.9 ✓ (31.0s, 729 tok)
  center10_anchor_0147: gt=negative pred=positive conf=0.7 ✗ (22.8s, 534 tok)
  center10_anchor_0342: gt=negative pred=parse_error conf=None ✗ (86.4s, 2048 tok)
  center10_anchor_0227: gt=negative pred=negative conf=1.0 ✓ (24.8s, 581 tok)
  center10_anchor_0345: gt=negative pred=negative conf=1.0 ✓ (43.4s, 1024 tok)
  center10_anchor_0213: gt=negative pred=positive conf=0.8 ✗ (40.1s, 945 tok)
  center10_anchor_0075: gt=positive pred=positive conf=0.8 ✓ (10.7s, 246 tok)
  center10_anchor_0325: gt=positive pred=positive conf=0.9 ✓ (12.2s, 282 tok)
```

## Gate Decision

**GATE: GLM_TEST_GATE_PASS** (with caveat: only 2 Qwen positives in test set)

- Qwen positives covered by GLM positive+uncertain: 2/2 (100%)
- Qwen-positives missed in GLM negative: 0
- Parse errors: 1 (anchor 0342; acceptable)
- GLM positive rate: 50% (5/10; 3 false positives on Qwen-negatives)

Gate criteria met mechanically (recall_rate=1.0 ≥ 0.8, missed=0 ≤ 1, parse_err=1 ≤ 1, precision=0.4 ≥ 0.25). Caveat: test set has only 2 Qwen positives (both are singletons from different event clusters), so the gate has limited statistical power. A larger gate test would be desirable but is not available within the current task scope.

Gate PASS with limited-test-set caveat — proceed to Phase 2 (123-sample pilot).

GLM model: /qiuyeqing/llama_prl/G-ARC/models/vlm/GLM-4.1V
Contact sheets: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1/inputs/contact_sheets/
Raw outputs: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/prompt_tuning_v1/heldout_cascade_eval_v1/raw_outputs/glm_v1_on_qwen_test/
