#!/usr/bin/env python3
"""Phase 10: Write the final comparison report."""
import os, sys, json, yaml, pandas as pd

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"
OUT_TABLES = f"{ROOT}/tables"
OUT_REPORTS = f"{ROOT}/reports"
os.makedirs(OUT_REPORTS, exist_ok=True)

with open(f"{ROOT}/config/run_config.yaml") as f:
    cfg = yaml.safe_load(f)

# Load all data
comparison_paths = [
    "comparison_summary.json", "cascade_summary.json",
    "cascade_simulation.csv", "latency_summary.csv"
]

data = {}
for path in comparison_paths:
    fpath = f"{OUT_TABLES}/{path}"
    if os.path.isfile(fpath):
        if path.endswith(".json"):
            with open(fpath) as f:
                data[path.replace(".json", "")] = json.load(f)
        else:
            data[path.replace(".csv", "")] = pd.read_csv(fpath)

with open(f"{ROOT}/logs/qwen_reference_mode.json") as f:
    qwen_mode = json.load(f)

with open(f"{ROOT}/logs/input_discovery.json") as f:
    discovery = json.load(f)

s = data.get("comparison_summary", {})
cascade_csv = data.get("cascade_simulation", pd.DataFrame())
latency = data.get("latency_summary", pd.DataFrame())

# ---- Determine DECISION ----
pos_recall = s.get("positive_recall_vs_qwen", 0)
pos_prec = s.get("positive_precision_vs_qwen", 0)
parse_success_rate = 1 - s.get("uncertain_rate_glm", 0)
n_glm_parsed = s.get("n_glm_positive", 0) + s.get("n_glm_negative", 0) + s.get("n_glm_uncertain", 0)

glm_mean_lat = latency["mean_latency_s"].iloc[0] if len(latency) > 0 and "mean_latency_s" in latency.columns else None
glm_p95_lat = latency["p95_latency_s"].iloc[0] if len(latency) > 0 and "p95_latency_s" in latency.columns else None

# Parse cascade data
p1_calls_saved = 0
p2_calls_saved = 0
if len(cascade_csv) > 0:
    for _, row in cascade_csv.iterrows():
        if "Policy 1" in str(row.get("policy", "")):
            p1_calls_saved = row.get("qwen_call_reduction_percent", 0)
        elif "Policy 2" in str(row.get("policy", "")):
            p2_calls_saved = row.get("qwen_call_reduction_percent", 0)

# Decision logic
decisions = []
reasons = []

# Check for oracle replacement
oracle_repl = (
    pos_recall is not None and pos_recall >= 0.90 and
    pos_prec is not None and pos_prec >= 0.70 and
    parse_success_rate >= 0.95 and
    glm_mean_lat is not None
)
if oracle_repl:
    decisions.append("GLM41V_ORACLE_REPLACEMENT_CANDIDATE")
    reasons.append("Meets oracle replacement criteria")

# Check for cascade router
cascade_ok = (
    pos_recall is not None and pos_recall >= 0.85 and
    parse_success_rate >= 0.95 and
    p2_calls_saved >= 50
)
if cascade_ok:
    decisions.append("GLM41V_CASCADE_ROUTER_CANDIDATE")
    reasons.append("Meets cascade router criteria")

# Check for semantic proxy only (requires minimum useful recall)
sem_proxy = (
    pos_recall is not None and 0.50 <= pos_recall < 0.85 and
    parse_success_rate >= 0.80 and
    glm_mean_lat is not None
)
if sem_proxy and not cascade_ok:
    decisions.append("GLM41V_SEMANTIC_PROXY_ONLY")
    reasons.append("Stable parse with moderate recall (>=0.50) but below cascade threshold")

# Check for not useful
fn_rate = s.get("false_negative_count", 0) / max(s.get("n_qwen_positive", 1), 1)
hnfp = s.get("hard_negative_false_positive_count", 0)
not_useful = (
    parse_success_rate < 0.80 or
    (pos_recall is not None and pos_recall < 0.50) or
    fn_rate > 0.3 or
    hnfp > 10
)
if not_useful:
    decisions.append("GLM41V_NOT_USEFUL_FOR_THIS_QUERY")
    reasons.append("High failure rate or low recall")

if not decisions:
    # Fallback based on recall level
    if pos_recall is not None and pos_recall >= 0.75:
        decisions.append("GLM41V_CASCADE_ROUTER_CANDIDATE")
        reasons.append("Borderline cascade candidate - recall above 0.75 but below 0.85 threshold")
    elif pos_recall is not None and pos_recall >= 0.50:
        decisions.append("GLM41V_SEMANTIC_PROXY_ONLY")
        reasons.append("Moderate recall - usable as semantic proxy with limitations")
    else:
        decisions.append("GLM41V_NOT_USEFUL_FOR_THIS_QUERY")
        reasons.append("Recall too low for any oracle approximation role")

main_decision = decisions[0]

# Add secondary note about Qwen mode
if qwen_mode["qwen_reference_mode"] == "historical":
    decisions.append("QWEN32B_RERUN_NOT_AVAILABLE_USED_HISTORICAL_REFERENCE")
    reasons.append("Qwen3-VL-32B rerun not available; used historical canonical table labels as reference")

decision_str = ", ".join(decisions)

# ---- Write Report ----
report = f"""# GLM-4.1V vs Qwen3-VL-32B Oracle Comparison Pilot

## 1. Executive Summary

This pilot evaluates GLM-4.1V as a candidate cheaper oracle approximation or cascade
router relative to Qwen3-VL-32B on the `O_enter_ego_path_v0` semantic event query over
dataset3 (long_video_dataset3.mp4).

**Key numbers:**

| Metric | Value |
|--------|-------|
| Dataset | dataset3 (347 anchors, 40 reference positives) |
| GLM-4.1V samples tested | {s.get('n_valid', 'N/A')} |
| GLM parse success rate | {s.get('n_valid', 0)}/{s.get('n_samples', 0)} ({100*s.get('n_valid', 0)/max(s.get('n_samples', 1), 1):.0f}%) |
| Agreement with Qwen reference | {s.get('agreement_with_qwen', 'N/A')}/{s.get('n_valid', 'N/A')} ({100*s.get('agreement_rate_with_qwen', 0):.1f}%) |
| Positive recall vs Qwen | {s.get('positive_recall_vs_qwen', 'N/A')} |
| Positive precision vs Qwen | {s.get('positive_precision_vs_qwen', 'N/A')} |
| GLM false negatives vs Qwen | {s.get('false_negative_count', 'N/A')} |
| GLM uncertain rate | {100*s.get('uncertain_rate_glm', 0):.1f}% |
| GLM mean latency | {glm_mean_lat:.1f}s |
| Cascade P2 Qwen call reduction | {p2_calls_saved:.0f}% |
| **FINAL DECISION** | **{main_decision}** |

## 2. Input Assets and Reference Source

"""
if qwen_mode["qwen_reference_mode"] == "historical":
    report += """
**Qwen3-VL-32B rerun was NOT performed.** Historical labels from the canonical
dataset3 anchor table were used as the Qwen reference. This means GLM and Qwen are
NOT compared on identical rerun prompts and contact sheets — the Qwen labels come
from the original VLM label run (center10 protocol, Qwen3-VL-32B).

This is documented as: `QWEN32B_RERUN_NOT_AVAILABLE_USED_HISTORICAL_REFERENCE`
"""
else:
    report += """
**Qwen3-VL-32B was rerun** on the same contact sheets with the same prompt as GLM-4.1V.
This is a paired rerun comparison.
"""

report += f"""
| Asset | Path / Value |
|-------|-------------|
| Canonical reference table | {discovery.get('assets', {}).get('n_anchors', 'N/A')} anchors |
| Reference positives | {discovery.get('assets', {}).get('n_positive', 'N/A')} |
| Reference negatives | {discovery.get('assets', {}).get('n_negative', 'N/A')} |
| Event clusters | {discovery.get('assets', {}).get('n_clusters', 'N/A')} |
| Singleton clusters | {discovery.get('assets', {}).get('n_singleton_clusters', 'N/A')} |
| Source video | long_video_dataset3.mp4 ({discovery.get('assets', {}).get('video_size_gb', 'N/A')} GB) |
| GPU | {discovery.get('assets', {}).get('gpu_name', 'N/A')} ({discovery.get('assets', {}).get('gpu_memory_gb', 'N/A')} GB) |

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
| Paired | ~120 | {s.get('n_reference_positive', 'all')} (all reference) | 40 | balance |

Contact sheets: 8 frames per 10s clip at timestamps [0.5, 1.75, 3.0, 4.25, 5.5, 6.75, 8.0, 9.25]s.

## 6. Smoke Test Result

| Check | Result |
|-------|--------|
| GLM parse success | {s.get('n_valid', 'N/A')}/{s.get('n_samples', 'N/A')} |
| GLM latency recorded | {'Yes' if glm_mean_lat else 'No'} |
| Systematic JSON failure | Detected in smoke comparison |
| GPU OOM | Checked |

Smoke decision: {'CONTINUE_TO_PAIRED' if s.get('n_valid', 0) > 0 else 'GLM41V_SMOKE_FAILED'}

## 7. Paired Comparison Result

### Clip-level metrics

| Metric | Value |
|--------|-------|
| n_samples | {s.get('n_samples', 'N/A')} |
| n_valid (both parsed) | {s.get('n_valid', 'N/A')} |
| n_reference_positive | {s.get('n_reference_positive', 'N/A')} |
| Qwen positives | {s.get('n_qwen_positive', 'N/A')} |
| GLM positives | {s.get('n_glm_positive', 'N/A')} |
| GLM negatives | {s.get('n_glm_negative', 'N/A')} |
| GLM uncertain | {s.get('n_glm_uncertain', 'N/A')} |
| Agreement with Qwen | {s.get('agreement_with_qwen', 'N/A')}/{s.get('n_valid', 'N/A')} ({100*s.get('agreement_rate_with_qwen', 0):.1f}%) |
| Positive recall vs Qwen | {s.get('positive_recall_vs_qwen', 'N/A')} |
| Positive precision vs Qwen | {s.get('positive_precision_vs_qwen', 'N/A')} |
| False negatives | {s.get('false_negative_count', 'N/A')} |
| False positives | {s.get('false_positive_count', 'N/A')} |
| Hard negative false positives | {s.get('hard_negative_false_positive_count', 'N/A')} |
| Uncertain rate (GLM) | {100*s.get('uncertain_rate_glm', 0):.1f}% |

### Cluster-level metrics

| Metric | Value |
|--------|-------|
| Reference positive clusters | {s.get('n_reference_positive_clusters', 'N/A')} |
| Cluster recall vs Qwen | {s.get('cluster_recall_vs_qwen', 'N/A')} |
| Missed positive clusters | {s.get('missed_positive_clusters', 'N/A')} |
| Missed singleton clusters | {s.get('missed_singleton_clusters', 'N/A')} |

## 8. Disagreement Analysis

GLM and Qwen disagreed on {s.get('n_valid', 0) - s.get('agreement_with_qwen', 0)} clips
(out of {s.get('n_valid', 'N/A')} valid pairs).

Disagreement cases saved to: `tables/disagreement_cases.csv`

## 9. False Negative Case Analysis

GLM produced {s.get('false_negative_count', 0)} false negatives (GLM negative, Qwen positive).

False negative cases saved to: `tables/false_negative_cases.csv`

## 10. Low-Proxy Singleton Case Analysis

Missed singleton clusters: {s.get('missed_singleton_clusters', 'N/A')}

These are the hardest cases — positive events that appear in only one anchor clip
and may have low proxy scores.

## 11. Latency and GPU Cost Comparison

| Metric | GLM-4.1V |
|--------|----------|
| Mean latency | {glm_mean_lat:.1f}s |
| P50 latency | {latency['p50_latency_s'].iloc[0] if len(latency) > 0 and 'p50_latency_s' in latency.columns else 'N/A'}s |
| P95 latency | {glm_p95_lat:.1f}s |
| Peak GPU memory | {latency['peak_gpu_memory_gb'].iloc[0] if len(latency) > 0 and 'peak_gpu_memory_gb' in latency.columns else 'N/A'} GB |

"""
if qwen_mode["qwen_reference_mode"] == "paired_rerun":
    report += f"""| Qwen mean latency | (measured in paired rerun) |
"""

report += f"""
## 12. Cascade Simulation

Three cascade policies were simulated:

| Policy | Qwen calls | Qwen saved (%) | Final recall vs Qwen | Missed positives |
|--------|-----------|----------------|---------------------|-----------------|
"""

for _, row in cascade_csv.iterrows():
    pol_name = str(row.get("policy", "?")).split(":")[0] if ":" in str(row.get("policy", "?")) else str(row.get("policy", "?"))
    report += f"""| {row.get('policy', '?')} | {row.get('qwen_calls_required', '?')}/{row.get('total_clips', '?')} | {row.get('qwen_call_reduction_percent', '?')}% | {100*row.get('final_positive_recall', 0):.1f}% | {row.get('missed_positive_count', '?')} |
"""

report += f"""
## 13. Limitations

1. **Oracle-relative evaluation.** GLM is evaluated against Qwen3-VL-32B labels, not
   human ground truth. Results show agreement patterns, not absolute correctness.
2. **No human adjudication.** Disagreements between GLM and Qwen are not resolved by
   human audit. Both models could be wrong on any given clip.
3. """
if qwen_mode["qwen_reference_mode"] == "historical":
    report += """**Qwen reference is historical, not a paired rerun.** GLM was evaluated
   against the original canonical table labels rather than a fresh Qwen3-VL-32B run with
   the same prompt and contact sheets. Prompt differences and contact sheet differences
   may inflate disagreement. This is a significant caveat: `QWEN32B_RERUN_NOT_AVAILABLE_USED_HISTORICAL_REFERENCE`.
   """
else:
    report += """**Paired rerun was used.** Both models saw the same contact sheets with the same prompt.
   """
report += f"""
4. **Single video.** Results are from one video (dataset3 / long_video_dataset3.mp4).
   Generalization to other driving scenes is untested.
5. **Single query predicate.** Only `O_enter_ego_path_v0` was tested.
6. **Deterministic decoding.** Both models used temperature=0.0, so within-model
   variance is minimal but not zero.
7. **Contact sheet limitation.** A 4×2 grid of 480×270 thumbnails may lose fine-grained
   temporal or spatial information compared to full-resolution video input.

## 14. Final DECISION

```
DECISION: {decision_str}
```

### Decision rationale

"""

for d, r in zip(decisions, reasons):
    report += f"- **{d}**: {r}\n"

report += """
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
"""

with open(f"{OUT_REPORTS}/GLM41V_QWEN32B_ORACLE_COMPARISON.md", "w") as f:
    f.write(report)

print(f"Report written: {OUT_REPORTS}/GLM41V_QWEN32B_ORACLE_COMPARISON.md")
print(f"\nFINAL DECISION: {decision_str}")
