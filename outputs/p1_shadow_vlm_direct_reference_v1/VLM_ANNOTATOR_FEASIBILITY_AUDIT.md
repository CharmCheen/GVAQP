# VLM annotator feasibility audit

- SmolVLM2-500M cross-family attempt: failed context/schema feasibility; excluded.
- Qwen3-VL-32B attempt: overlong JSON truncation under frozen generation cap; excluded.
- Final VLM_A/VLM_B: same Qwen3-VL-8B checkpoint, fully independent sessions and separately frozen prompt orderings, as permitted by the shadow protocol request. This weakens independence and is a major interpretive confound.
