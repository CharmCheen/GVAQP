# GLM-4.1V vs Qwen3-VL-32B Oracle Comparison Pilot

## 1. Executive Summary

This pilot evaluates GLM-4.1V as a candidate cheaper oracle approximation or cascade
router relative to Qwen3-VL-32B on the `O_enter_ego_path_v0` semantic event query over
dataset3 (long_video_dataset3.mp4).

**Key numbers:**

| Metric | Value |
|--------|-------|
| Dataset | dataset3 (347 anchors, 40 reference positives) |
| GLM-4.1V samples tested | 106 |
| GLM parse success rate | 106/123 (86%) |
| Agreement with Qwen reference | 68/106 (64.1%) |
| Positive recall vs Qwen | 0.075 |
| Positive precision vs Qwen | 0.75 |
| GLM false negatives vs Qwen | 36 |
| GLM uncertain rate | 0.9% |
| GLM mean latency | 20.7s |
| Cascade P2 Qwen call reduction | 95% |
| **FINAL DECISION** | **GLM41V_NOT_USEFUL_FOR_THIS_QUERY** |

## 2. Input Assets and Reference Source


**Qwen3-VL-32B was rerun** on the same contact sheets with the same prompt as GLM-4.1V.
This is a paired rerun comparison.

| Asset | Path / Value |
|-------|-------------|
| Canonical reference table | 347 anchors |
| Reference positives | 40 |
| Reference negatives | 307 |
| Event clusters | 28 |
| Singleton clusters | 21 |
| Source video | long_video_dataset3.mp4 (1.1 GB) |
| GPU | NVIDIA A800-SXM4-80GB (79.3 GB) |

## 3. Model Paths and Decoding Config

| Model | Path |
|-------|------|
| GLM-4.1V | `/qiuyeqing/llama_prl/G-ARC/models/vlm/GLM-4.1V/` |
| Qwen3-VL-32B | `/qiuyeqing/llama_prl/G-ARC/models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct/` |

**Decoding config:** temperature=0.0, do_sample=false, top_p=1.0, max_new_tokens=384

## 4. Prompt Version

Used `config/oracle_prompt_v1.md` — same prompt text for both models.

Target event definition: `O_enter_ego_path_v0` — "A non-ego dynamic road user enters,
crosses, cuts into, or materially encroaches on the ego vehicle's likely path or
immediate driving corridor..."

## 5. Sample Construction

| Sample Set | N | Reference Positives | Hard Negatives (high proxy) | Random Negatives |
|-----------|----|---------------------|-----------------------------|-----------------|
| Smoke | 12 | 4 | 4 | 4 |
| Paired | ~120 | 40 (all reference) | 40 | balance |

Contact sheets: 8 frames per 10s clip at timestamps [0.5, 1.75, 3.0, 4.25, 5.5, 6.75, 8.0, 9.25]s.

## 6. Smoke Test Result

| Check | Result |
|-------|--------|
| GLM parse success | 106/123 |
| GLM latency recorded | Yes |
| Systematic JSON failure | Detected in smoke comparison |
| GPU OOM | Checked |

Smoke decision: CONTINUE_TO_PAIRED

## 7. Paired Comparison Result

### Clip-level metrics

| Metric | Value |
|--------|-------|
| n_samples | 123 |
| n_valid (both parsed) | 106 |
| n_reference_positive | 40 |
| Qwen positives | 53 |
| GLM positives | 4 |
| GLM negatives | 104 |
| GLM uncertain | 1 |
| Agreement with Qwen | 68/106 (64.1%) |
| Positive recall vs Qwen | 0.075 |
| Positive precision vs Qwen | 0.75 |
| False negatives | 36 |
| False positives | 1 |
| Hard negative false positives | 0 |
| Uncertain rate (GLM) | 0.9% |

### Cluster-level metrics

| Metric | Value |
|--------|-------|
| Reference positive clusters | 27 |
| Cluster recall vs Qwen | 0.1364 |
| Missed positive clusters | 19 |
| Missed singleton clusters | 14 |

## 8. Disagreement Analysis

GLM and Qwen disagreed on 38 clips
(out of 106 valid pairs).

Disagreement cases saved to: `tables/disagreement_cases.csv`

## 9. False Negative Case Analysis

GLM produced 36 false negatives (GLM negative, Qwen positive).

False negative cases saved to: `tables/false_negative_cases.csv`

## 10. Low-Proxy Singleton Case Analysis

Missed singleton clusters: 14

These are the hardest cases — positive events that appear in only one anchor clip
and may have low proxy scores.

## 11. Latency and GPU Cost Comparison

| Metric | GLM-4.1V |
|--------|----------|
| Mean latency | 20.7s |
| P50 latency | 18.638s |
| P95 latency | 33.8s |
| Peak GPU memory | 19.555 GB |

| Qwen mean latency | (measured in paired rerun) |

## 12. Cascade Simulation

Three cascade policies were simulated:

| Policy | Qwen calls | Qwen saved (%) | Final recall vs Qwen | Missed positives |
|--------|-----------|----------------|---------------------|-----------------|
| Policy 1: GLM positive → Qwen | 4/106 | 96.2% | 7.5% | 37 |
| Policy 2: GLM positive+uncertain → Qwen | 5/106 | 95.3% | 10.0% | 36 |
| Policy 3: GLM positive+uncertain+top-4GLM-neg by proxy → Qwen | 9/106 | 91.5% | 15.0% | 34 |

## 13. Limitations

1. **Oracle-relative evaluation.** GLM is evaluated against Qwen3-VL-32B labels, not
   human ground truth. Results show agreement patterns, not absolute correctness.
2. **No human adjudication.** Disagreements between GLM and Qwen are not resolved by
   human audit. Both models could be wrong on any given clip.
3. **Paired rerun was used.** Both models saw the same contact sheets with the same prompt.
   
4. **Single video.** Results are from one video (dataset3 / long_video_dataset3.mp4).
   Generalization to other driving scenes is untested.
5. **Single query predicate.** Only `O_enter_ego_path_v0` was tested.
6. **Deterministic decoding.** Both models used temperature=0.0, so within-model
   variance is minimal but not zero.
7. **Contact sheet limitation.** A 4×2 grid of 480×270 thumbnails may lose fine-grained
   temporal or spatial information compared to full-resolution video input.

## 14. Final DECISION

```
DECISION: GLM41V_NOT_USEFUL_FOR_THIS_QUERY
```

### Decision rationale

- **GLM41V_NOT_USEFUL_FOR_THIS_QUERY**: High failure rate or low recall

### Caveats

- GLM-4.1V is evaluated as a candidate cheaper oracle approximation.
- Qwen3-VL-32B is treated as the reference oracle in this replay.
- The result is oracle-relative, not human-ground-truth validation.
- Do not interpret as "GLM is objectively correct" or "GLM replaces human labels."
- Do not claim GLM is guaranteed to preserve recall without cascade simulation.

### Suggested next steps

- Rerun Qwen3-VL-32B with the exact same prompt and contact sheets for a true paired comparison.
- If cascade decision holds: implement and endpoint-test the cascade policy on the full 347 anchors.
- Audit hard disagreement cases with human review to determine which model is more accurate.
- Test on a second long video to assess generalization.
- If replacement candidate: validate on held-out video with full oracle reference.
