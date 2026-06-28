#!/usr/bin/env python3
"""Phase 9: Cascade simulation. Estimate savings from GLM→Qwen cascade."""
import os, sys, json, yaml, pandas as pd, numpy as np

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"
OUT_TABLES = f"{ROOT}/tables"

with open(f"{ROOT}/config/run_config.yaml") as f:
    cfg = yaml.safe_load(f)

# Load comparison data
pred = pd.read_csv(f"{OUT_TABLES}/paired_predictions.csv")
print(f"Predictions loaded: {len(pred)} rows")

with open(f"{OUT_TABLES}/comparison_summary.json") as f:
    summ = json.load(f)

# Load latency info
lat_df = pd.read_csv(f"{OUT_TABLES}/latency_summary.csv")
glm_mean_lat = lat_df["mean_latency_s"].iloc[0] if len(lat_df) > 0 else None
glm_p50_lat = lat_df["p50_latency_s"].iloc[0] if len(lat_df) > 0 else None

# Qwen latency - estimate from the canonical table historical runs or use a factor
# Since Qwen wasn't rerun with the same prompt, use historical data or estimate
qwen_lat_estimate = glm_mean_lat * 8 if glm_mean_lat else 60  # rough: Qwen32B ~8x slower than GLM4.1V
# But we can try to get actual Qwen latency if available
qwen_res_path = f"{ROOT}/tables/qwen32b_paired_results.csv"
if os.path.isfile(qwen_res_path):
    qwen_df = pd.read_csv(qwen_res_path)
    if "runtime_seconds" in qwen_df.columns:
        qwen_lat = qwen_df["runtime_seconds"].dropna()
        if len(qwen_lat) > 0:
            qwen_lat_estimate = qwen_lat.mean()
print(f"GLM mean latency: {glm_mean_lat:.2f}s" if glm_mean_lat else "GLM latency: unknown")
print(f"Qwen estimated latency: {qwen_lat_estimate:.2f}s")

# Valid clips (both parsed)
valid = pred[pred["glm_label"].isin(["positive", "negative", "uncertain"]) &
            pred["qwen_label"].isin(["positive", "negative", "uncertain"])].copy()

n_total = len(valid)
n_qwen_pos = (valid["qwen_label"] == "positive").sum()
n_reference_pos = valid["is_positive"].sum()

# Load manifest for proxy scores
manifest_paired = pd.read_csv(f"{ROOT}/inputs/sample_manifest_paired.csv")
manifest_smoke = pd.read_csv(f"{ROOT}/inputs/sample_manifest_smoke.csv")
manifest_all = pd.concat([manifest_smoke, manifest_paired]).drop_duplicates(subset="anchor_id")
proxy_map = {}
for _, r in manifest_all.iterrows():
    for c in ["proxy_score", "object_count_mean", "score_fusion_geometry_motion"]:
        if c in manifest_all.columns and pd.notna(r.get(c)):
            proxy_map[r["anchor_id"]] = r[c]
            break
valid["proxy_score"] = valid["anchor_id"].map(proxy_map).fillna(0)

# Cluster-level data
cluster_info = None
if "event_cluster_id" in valid.columns:
    cluster_info = {}
    for cid in valid["event_cluster_id"].dropna().unique():
        cdf = valid[valid["event_cluster_id"] == cid]
        cluster_info[cid] = {
            "n_anchors": len(cdf),
            "has_qwen_pos": (cdf["qwen_label"] == "positive").any(),
            "has_glm_pos": (cdf["glm_label"] == "positive").any(),
        }

def compute_policy(label_func, name):
    """Simulate a cascade policy.
    label_func(label) returns True if the clip should be sent to Qwen."""
    valid["needs_qwen"] = valid["glm_label"].apply(label_func)

    n_qwen_calls = valid["needs_qwen"].sum()
    qwen_calls_saved = n_total - n_qwen_calls
    qwen_call_reduction = 100 * (1 - n_qwen_calls / n_total) if n_total > 0 else 0

    # Final labels: use Qwen where available, GLM otherwise
    final_pos = valid.apply(
        lambda r: r["qwen_label"] == "positive" if r["needs_qwen"] else r["glm_label"] == "positive",
        axis=1
    )
    n_final_pos = final_pos.sum()

    # Positive recall vs Qwen reference
    qwen_pos_total = n_qwen_pos
    final_pos_on_qwen = ((final_pos) & (valid["qwen_label"] == "positive")).sum()
    pos_recall = final_pos_on_qwen / qwen_pos_total if qwen_pos_total > 0 else 1.0

    # Missed positives: Qwen positives that GLM missed AND were never sent to Qwen
    missed = valid[(valid["qwen_label"] == "positive") & ~valid["needs_qwen"] & (valid["glm_label"] != "positive")]
    n_missed = len(missed)

    # Missed clusters
    n_missed_clusters = 0
    missed_cluster_ids = []
    if cluster_info:
        for cid, ci in cluster_info.items():
            if ci["has_qwen_pos"]:
                cdf = valid[valid["event_cluster_id"] == cid]
                cdf_missed = cdf[(cdf["qwen_label"] == "positive") & ~cdf["needs_qwen"] & (cdf["glm_label"] != "positive")]
                if len(cdf_missed) > 0 and not (cdf["needs_qwen"] & (cdf["qwen_label"] == "positive")).any():
                    n_missed_clusters += 1
                    missed_cluster_ids.append(str(cid))

    # Estimated total latency
    glm_time = n_total * glm_mean_lat if glm_mean_lat else 0
    qwen_time = n_qwen_calls * qwen_lat_estimate
    est_total_latency = glm_time + qwen_time
    est_latency_per_clip = est_total_latency / n_total if n_total > 0 else 0

    result = {
        "policy": name,
        "total_clips": n_total,
        "qwen_calls_required": int(n_qwen_calls),
        "qwen_calls_saved": int(qwen_calls_saved),
        "qwen_call_reduction_percent": round(qwen_call_reduction, 1),
        "n_qwen_reference_positives": int(n_qwen_pos),
        "final_positive_count": int(n_final_pos),
        "final_positive_recall": round(pos_recall, 4),
        "missed_positive_count": n_missed,
        "missed_cluster_count": n_missed_clusters,
        "missed_cluster_ids": missed_cluster_ids,
        "estimated_glm_latency_s": round(glm_time, 1),
        "estimated_qwen_latency_s": round(qwen_time, 1),
        "estimated_total_latency_s": round(est_total_latency, 1),
        "estimated_latency_per_clip_s": round(est_latency_per_clip, 2),
    }
    return result

# Policy 1: Send GLM positive only to Qwen
p1 = compute_policy(lambda lbl: lbl == "positive", "Policy 1: GLM positive → Qwen")

# Policy 2: Send GLM positive + uncertain to Qwen
p2 = compute_policy(lambda lbl: lbl in ("positive", "uncertain"), "Policy 2: GLM positive+uncertain → Qwen")

# Policy 3: Send GLM positive + uncertain + top-k GLM-negative by proxy to Qwen
# Top-k = number of GLM negatives equal to number of GLM positives (double-check portion)
n_glm_pos = (valid["glm_label"] == "positive").sum()
# Use proxy score from manifest if available
proxy_col = None
for c in ["proxy_score", "object_count_mean", "score_fusion_geometry_motion"]:
    if c in valid.columns:
        proxy_col = c
        break

def policy3_func(lbl):
    if lbl in ("positive", "uncertain"):
        return True
    return False  # will override below

# For policy 3, override top-k negatives
valid_p3 = valid.copy()
if proxy_col and n_glm_pos > 0:
    neg_sorted = valid_p3[valid_p3["glm_label"] == "negative"].sort_values(proxy_col, ascending=False)
    top_k = neg_sorted.head(n_glm_pos)
    valid_p3["needs_qwen"] = valid_p3["glm_label"].isin(["positive", "uncertain"])
    valid_p3.loc[valid_p3["anchor_id"].isin(top_k["anchor_id"]), "needs_qwen"] = True
    n_qwen_p3 = valid_p3["needs_qwen"].sum()
    qwen_saved_p3 = n_total - n_qwen_p3
    qwen_red_p3 = 100 * (1 - n_qwen_p3 / n_total) if n_total > 0 else 0
    final_pos_p3 = valid_p3.apply(
        lambda r: r["qwen_label"] == "positive" if r["needs_qwen"] else r["glm_label"] == "positive", axis=1
    )
    n_final_p3 = final_pos_p3.sum()
    final_pos_on_qwen_p3 = ((final_pos_p3) & (valid_p3["qwen_label"] == "positive")).sum()
    pos_recall_p3 = final_pos_on_qwen_p3 / n_qwen_pos if n_qwen_pos > 0 else 1.0
    missed_p3 = valid_p3[(valid_p3["qwen_label"] == "positive") & ~valid_p3["needs_qwen"] & (valid_p3["glm_label"] != "positive")]
    n_missed_p3 = len(missed_p3)

    p3 = {
        "policy": f"Policy 3: GLM positive+uncertain+top-{n_glm_pos}GLM-neg by proxy → Qwen",
        "total_clips": n_total,
        "qwen_calls_required": int(n_qwen_p3),
        "qwen_calls_saved": int(qwen_saved_p3),
        "qwen_call_reduction_percent": round(qwen_red_p3, 1),
        "n_qwen_reference_positives": int(n_qwen_pos),
        "final_positive_count": int(n_final_p3),
        "final_positive_recall": round(pos_recall_p3, 4),
        "missed_positive_count": n_missed_p3,
        "missed_cluster_count": 0,
        "missed_cluster_ids": [],
        "estimated_glm_latency_s": round(n_total * glm_mean_lat, 1) if glm_mean_lat else 0,
        "estimated_qwen_latency_s": round(n_qwen_p3 * qwen_lat_estimate, 1),
        "estimated_total_latency_s": round(n_total * glm_mean_lat + n_qwen_p3 * qwen_lat_estimate, 1) if glm_mean_lat else 0,
        "estimated_latency_per_clip_s": round((n_total * glm_mean_lat + n_qwen_p3 * qwen_lat_estimate) / n_total, 2) if glm_mean_lat else 0,
    }
else:
    p3 = {"policy": "Policy 3: NOT APPLICABLE (no proxy column or no GLM positives)"}

policies = [p1, p2]
if isinstance(p3, dict) and "Policy 3" in str(p3.get("policy", "")):
    policies.append(p3)
pol_df = pd.DataFrame(policies)
pol_df.to_csv(f"{OUT_TABLES}/cascade_simulation.csv", index=False)

print(f"\n{'='*60}")
print("Cascade Simulation Results")
print(f"{'='*60}")
for p in policies:
    if not isinstance(p, dict):
        continue
    print(f"\n{p.get('policy', '?' )}:")
    print(f"  Qwen calls: {p.get('qwen_calls_required', 0)}/{p.get('total_clips', 0)} ({100-p.get('qwen_call_reduction_percent', 0):.1f}%)")
    print(f"  Qwen calls saved: {p.get('qwen_calls_saved', 0)} ({p.get('qwen_call_reduction_percent', 0):.1f}%)")
    print(f"  Final positive recall vs Qwen: {100*p.get('final_positive_recall', 0):.1f}%")
    print(f"  Missed positives: {p.get('missed_positive_count', 0)}")
    print(f"  Estimated total latency: {p.get('estimated_total_latency_s', 0):.0f}s")

# Save summary
cascade_summary = {
    "n_total_clips": n_total,
    "n_qwen_reference_positives": int(n_qwen_pos),
    "glm_mean_latency_s": glm_mean_lat,
    "qwen_mean_latency_s": qwen_lat_estimate,
    "policies": policies,
}
with open(f"{OUT_TABLES}/cascade_summary.json", "w") as f:
    json.dump(cascade_summary, f, indent=2, default=str)

print(f"\nCascade simulation complete.")
