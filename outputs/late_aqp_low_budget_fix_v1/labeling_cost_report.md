# Labeling Cost Report

This report records the one-time VLM oracle calls used to generate new labels.
These calls are **not** counted toward any method's oracle budget.

| Video | Anchors labeled | Positive anchors | Stitched events |
|-------|-----------------|------------------|-----------------|
| realcartest_5k | 21 | 11 | 3 |

**Total VLM inference calls: 21**

Model: `/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct`
Prompt: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_6_clip_construction_sensitivity_v1/prompts/o_enter_ego_path_v0_v13_6_prompt.txt`
Outputs: `/qiuyeqing/llama_prl/G-ARC/outputs/late_aqp_low_budget_fix_v1/new_labels`
