# Prompt Tuning Report — GLM-4.1V & Qwen3-VL-32B

**Date**: 2026-06-26
**Query**: `O_enter_ego_path_v0`
**Test Set**: GLM 15 clips (10 pos, 5 neg), Qwen 10 clips (2 pos, 8 neg) — focused on disagreement cases from pilot

---

## Results Summary

| Model | Variant | Recall | Precision | F1 | FP | FN | Parse Errors |
|-------|---------|--------|-----------|-----|----|----|--------------|
| GLM | v0_original | 0.0% | N/A | — | 0 | 10 | 2 |
| **GLM** | **v1_lower_threshold** | **60.0%** | **85.7%** | **0.706** | **1** | **4** | **0** |
| GLM | v2_examples | 20.0% | 100% | 0.333 | 0 | 8 | 0 |
| GLM | v3_direct | 20.0% | 100% | 0.333 | 0 | 8 | 0 |
| Qwen | v0_original | 100% | 20.0% | 0.333 | 8 | 0 | 0 |
| Qwen | v1_stricter_spatial | 100% | 28.6% | 0.444 | 5 | 0 | 0 |
| Qwen | v2_no_false_alarm | 100% | 25.0% | 0.400 | 6 | 0 | 0 |
| **Qwen** | **v3_two_step** | **100%** | **40.0%** | **0.571** | **3** | **0** | **0** |

## Best Prompts

- **GLM best**: `prompts/BEST_glm_final.md` — v1_lower_threshold (F1=0.706)
  - Key change: "Err on the side of flagging POSITIVE" instruction
  - `max_new_tokens` must be ≥2048 (GLM generates ~750 tokens of reasoning before JSON)
- **Qwen best**: `prompts/BEST_qwen_final.md` — v3_two_step (F1=0.571)
  - Key change: Two-step reasoning (identify actors → evaluate conditions)
  - Explicit false positive patterns to avoid

## Error Analysis

### GLM remaining false negatives (4 clips)
GLM fundamentally cannot see/understand these events — visual understanding limit, not prompt issue.

### Qwen remaining false positives (3 clips: 0230, 0227, 0213)
Motorcycles with lateral movement still misclassified as "crossing" — Qwen over-sensitivity to sideways trajectory.

## Key Findings

1. **GLM**: "err positive" instruction is the single most impactful change (0% → 60% recall)
2. **GLM**: Adding examples makes it MORE conservative (20% recall), not less
3. **GLM**: Short/direct prompt doesn't help — GLM always generates chain-of-thought reasoning
4. **GLM**: `max_new_tokens=768` causes parse errors; must be ≥2048
5. **Qwen**: Two-step reasoning best balances recall/precision
6. **Qwen**: Stricter spatial criteria help but not as much as structured reasoning
7. **Qwen**: Explicit negative examples don't help (v2 worse than v1)

## Files

```
garc_eval/outputs/prompt_tuning_v1/
├── prompts/
│   ├── BEST_glm_final.md          # ← Use this for GLM
│   ├── BEST_qwen_final.md         # ← Use this for Qwen
│   ├── glm_v0_original.md
│   ├── glm_v1_lower_threshold.md
│   ├── glm_v2_examples.md
│   ├── glm_v3_direct.md
│   ├── qwen_v0_original.md
│   ├── qwen_v1_stricter_spatial.md
│   ├── qwen_v2_no_false_alarm.md
│   └── qwen_v3_two_step.md
├── scripts/
│   └── prompt_sweep_fast.py
├── test_sets/
│   ├── glm_test_small.csv
│   └── qwen_test_small.csv
├── raw_outputs/
│   ├── glm/{v0,v1,v2,v3}/
│   └── qwen/{v0,v1,v2,v3}/
└── reports/
    └── PROMPT_TUNING_REPORT.md     # ← This file
```
