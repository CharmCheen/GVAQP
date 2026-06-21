# Expanded VLM Oracle Human Audit Package

- Created at: 2026-06-15 UTC
- Source output dir: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded`
- Package dir: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/audit_package`
- Tarball: `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/roadclip_v2_audit_package.tar.gz`

## Contents

- clips in manifest: 135
- clip video files: 135
- VLM conservative positives included: 61
- VLM conservative negatives included: 74
- tar entries: 140
- tar size: 159M

## Sampling Reasons

| reason | rows |
|---|---:|
| all_conservative_positive | 61 |
| random_conservative_negative | 30 |
| top_count_high_score_negative | 20 |
| temporal_nms_naive_sample | 20 |
| proxy_then_expansion_count_sample | 20 |

Rows can have multiple sampling reasons, so counts sum above 135.

## VLM Event-Type Mix

| event_type | rows |
|---|---:|
| normal_following | 41 |
| crossing | 36 |
| dense_traffic_only | 30 |
| cut_in | 25 |
| none | 1 |
| roadside_static | 1 |
| ambiguous | 1 |

## Review Instructions

Open `audit_package/index.html` for video preview, or fill `audit_package/audit_manifest.csv` directly.

Fill these columns:

- `human_label`: `1` true ego-relevant risk/path conflict, `0` not ego-relevant risk, `-1` uncertain.
- `human_event_type`: concise event type such as `cut_in`, `crossing`, `normal_following`, `dense_traffic_only`, `roadside_static`, or `other`.
- `human_reason`: short explanation.
- `human_confidence`: `low`, `medium`, or `high`.
- `error_type`: optional; useful values include `false_positive`, `false_negative`, `ambiguous_prompt`, or `bad_scene`.

These labels are for auditing the VLM pseudo-oracle. They are not currently treated as full human ground truth for the whole benchmark.
