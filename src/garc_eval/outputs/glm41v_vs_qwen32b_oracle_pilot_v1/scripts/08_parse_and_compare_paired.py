#!/usr/bin/env python3
"""Phase 8: Parse and compare paired test results. Generate all analysis tables."""
import os, sys, yaml, json, re, pandas as pd, numpy as np

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"

with open(f"{ROOT}/config/model_paths.yaml") as f:
    paths = yaml.safe_load(f)
with open(f"{ROOT}/config/run_config.yaml") as f:
    cfg = yaml.safe_load(f)

GLM_SMOKE_DIR = f"{ROOT}/raw_outputs/glm41v/smoke"
GLM_PAIRED_DIR = f"{ROOT}/raw_outputs/glm41v/paired"
QEN_SMOKE_DIR = f"{ROOT}/raw_outputs/qwen32b/smoke"
QEN_PAIRED_DIR = f"{ROOT}/raw_outputs/qwen32b/paired"
MANIFEST_SMOKE = f"{ROOT}/inputs/sample_manifest_smoke.csv"
MANIFEST_PAIRED = f"{ROOT}/inputs/sample_manifest_paired.csv"
OUT_TABLES = f"{ROOT}/tables"
os.makedirs(OUT_TABLES, exist_ok=True)

with open(f"{ROOT}/logs/qwen_reference_mode.json") as f:
    qwen_mode = json.load(f)

canon = pd.read_csv(paths["canonical_table"])
canon["oracle_label"] = canon["oracle_label"].fillna(canon.get("label", ""))

def strip_think_tags(text):
    if not text:
        return text
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'</?answer>', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'<\|im_end\|>.*$', '', text, flags=re.DOTALL).strip()
    return text

def parse_json(text):
    if not text or not isinstance(text, str):
        return None, "empty"
    text = text.strip()
    text = strip_think_tags(text)
    try:
        return json.loads(text), "ok"
    except json.JSONDecodeError:
        pass
    # Find outermost JSON object: first { to last matching }
    stack = []
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if start == -1:
                start = i
            stack.append(i)
        elif ch == '}':
            if stack:
                stack.pop()
                if not stack and start >= 0:
                    try:
                        return json.loads(text[start:i+1]), "brace_matched"
                    except json.JSONDecodeError:
                        pass
    return None, "failed"

def load_model_outputs(out_dir, manifest_df):
    records = []
    for _, row in manifest_df.iterrows():
        aid = row["anchor_id"]
        json_path = f"{out_dir}/{aid}.json"
        if os.path.isfile(json_path):
            with open(json_path) as f:
                raw = json.load(f)
            parsed, ps = parse_json(raw.get("raw_output", ""))
            records.append({
                "anchor_id": aid,
                "parsed": parsed,
                "parse_status": ps,
                "raw_output": raw.get("raw_output", ""),
                "runtime_seconds": raw.get("runtime_seconds"),
                "peak_gpu_memory_gb": raw.get("peak_gpu_memory_gb"),
            })
        else:
            records.append({"anchor_id": aid, "parsed": None, "parse_status": "missing", "raw_output": ""})
    return pd.DataFrame(records)

def load_historical_reference(manifest_df):
    records = []
    for _, row in manifest_df.iterrows():
        aid = row["anchor_id"]
        match = canon[canon["anchor_id"] == aid]
        if len(match) > 0:
            ref = match.iloc[0]
            records.append({
                "anchor_id": aid,
                "reference_label": str(ref.get("oracle_label", ref.get("label", ""))).lower(),
                "reference_is_positive": bool(ref["is_positive"]),
            })
        else:
            records.append({"anchor_id": aid, "reference_label": "unknown", "reference_is_positive": None})
    return pd.DataFrame(records)

def load_qwen_results(manifest_df, mode):
    if mode == "paired_rerun":
        qwen_res = pd.read_csv(f"{ROOT}/tables/qwen32b_paired_results.csv")
        records = []
        for _, row in manifest_df.iterrows():
            aid = row["anchor_id"]
            qr = qwen_res[qwen_res["anchor_id"] == aid]
            if len(qr) > 0:
                qr = qr.iloc[0]
                if qr["parse_status"] == "raw_saved":
                    raw_path = f"{QEN_PAIRED_DIR}/{aid}.json"
                    if os.path.isfile(raw_path):
                        with open(raw_path) as f:
                            raw = json.load(f)
                        parsed, ps = parse_json(raw.get("raw_output", ""))
                        label = (parsed or {}).get("event_label", "").lower()
                        records.append({"anchor_id": aid, "qwen_label": label, "qwen_parsed": parsed is not None})
                    else:
                        records.append({"anchor_id": aid, "qwen_label": "unknown", "qwen_parsed": False})
                else:
                    records.append({"anchor_id": aid, "qwen_label": "unknown", "qwen_parsed": False})
            else:
                records.append({"anchor_id": aid, "qwen_label": "unknown", "qwen_parsed": False})
        return pd.DataFrame(records)
    else:
        ref_df = load_historical_reference(manifest_df)
        ref_df["qwen_label"] = ref_df["reference_label"]
        ref_df["qwen_parsed"] = True
        return ref_df

# Load manifests
smoke_manifest = pd.read_csv(MANIFEST_SMOKE)
paired_manifest = pd.read_csv(MANIFEST_PAIRED)
all_manifest = pd.concat([smoke_manifest, paired_manifest]).drop_duplicates(subset="anchor_id")

# Load GLM outputs
print("Loading GLM outputs...")
glm_smoke = load_model_outputs(GLM_SMOKE_DIR, smoke_manifest)
glm_paired = load_model_outputs(GLM_PAIRED_DIR, paired_manifest)
glm_all = load_model_outputs(GLM_SMOKE_DIR, all_manifest)
glm_all2 = load_model_outputs(GLM_PAIRED_DIR, all_manifest)
glm_all = pd.concat([glm_smoke, glm_paired]).drop_duplicates(subset="anchor_id", keep="first")

# Load Qwen labels
print("Loading Qwen labels...")
qwen_labels = load_qwen_results(all_manifest, qwen_mode["qwen_reference_mode"])

# Build combined table
combined = all_manifest.merge(glm_all[["anchor_id", "parsed", "parse_status", "runtime_seconds", "peak_gpu_memory_gb"]], on="anchor_id", how="left")
combined = combined.merge(qwen_labels[["anchor_id", "qwen_label", "qwen_parsed"]], on="anchor_id", how="left")

combined["glm_label"] = combined["parsed"].apply(
    lambda x: (x or {}).get("event_label", "").lower() if isinstance(x, dict) else "")
combined["glm_ego_relevant"] = combined["parsed"].apply(
    lambda x: str((x or {}).get("ego_relevant", "")) if isinstance(x, dict) else "")
combined["glm_actor_type"] = combined["parsed"].apply(
    lambda x: str((x or {}).get("primary_actor_type", "")) if isinstance(x, dict) else "")
combined["glm_interaction"] = combined["parsed"].apply(
    lambda x: str((x or {}).get("interaction_type", "")) if isinstance(x, dict) else "")
combined["glm_confidence"] = combined["parsed"].apply(
    lambda x: float((x or {}).get("confidence", 0)) if isinstance(x, dict) and isinstance((x or {}).get("confidence"), (int, float)) else None)
combined["glm_failure_reason"] = combined["parsed"].apply(
    lambda x: str((x or {}).get("failure_reason", "")) if isinstance(x, dict) else "")

combined["glm_valid"] = combined["glm_label"].isin(["positive", "negative", "uncertain"])
combined["qwen_valid"] = combined["qwen_label"].isin(["positive", "negative", "uncertain"])

# Save predictions table
pred_cols = ["anchor_id", "sample_type", "is_positive", "event_cluster_id", "is_singleton_cluster",
             "glm_label", "glm_parse_status", "glm_confidence", "glm_actor_type", "glm_interaction",
             "glm_ego_relevant", "glm_failure_reason",
             "qwen_label", "qwen_parsed",
             "runtime_seconds", "peak_gpu_memory_gb"]
existing_pred_cols = [c for c in pred_cols if c in combined.columns]
combined[existing_pred_cols].to_csv(f"{OUT_TABLES}/paired_predictions.csv", index=False)
print(f"Predictions saved: {len(combined)} rows")

# ---- Metrics ----
valid = combined[combined["glm_valid"] & combined["qwen_valid"]]
n_valid = len(valid)
print(f"\nValid (both parsed): {n_valid}/{len(combined)}")

# Clip-level metrics
n_ref_pos = combined["is_positive"].sum()
n_qwen_pos = (combined["qwen_label"] == "positive").sum()
n_glm_pos = (combined["glm_label"] == "positive").sum()
n_glm_neg = (combined["glm_label"] == "negative").sum()
n_glm_uncertain = (combined["glm_label"] == "uncertain").sum()

# Agreement
agree = (valid["glm_label"] == valid["qwen_label"]).sum()
agree_rate = agree / n_valid if n_valid > 0 else 0

# Positive recall vs Qwen
qwen_pos_set = valid[valid["qwen_label"] == "positive"]
glm_pos_on_qwen = (qwen_pos_set["glm_label"] == "positive").sum()
qwen_precision_denom = len(qwen_pos_set)
pos_recall_vs_qwen = glm_pos_on_qwen / qwen_precision_denom if qwen_precision_denom > 0 else None

# Positive precision vs Qwen
glm_pos_set = valid[valid["glm_label"] == "positive"]
qwen_pos_on_glm = (glm_pos_set["qwen_label"] == "positive").sum()
pos_precision_vs_qwen = qwen_pos_on_glm / len(glm_pos_set) if len(glm_pos_set) > 0 else None

# False negatives (GLM says negative, Qwen says positive)
fn = valid[(valid["glm_label"] == "negative") & (valid["qwen_label"] == "positive")]
fn_count = len(fn)

# False positives (GLM says positive, Qwen says negative)
fp = valid[(valid["glm_label"] == "positive") & (valid["qwen_label"] == "negative")]
fp_count = len(fp)

# Hard negative false positives (GLM says positive on known hard negatives)
hard_neg_fp = valid[(valid["glm_label"] == "positive") & (valid["qwen_label"] == "negative") & (valid["sample_type"] == "hard_negative")]
hnfp_count = len(hard_neg_fp)

# Uncertain rate
uncertain_rate = n_glm_uncertain / n_valid if n_valid > 0 else 0

print(f"\n--- Clip-level Metrics ---")
print(f"n_samples: {len(combined)}")
print(f"n_valid (both parsed): {n_valid}")
print(f"n_reference_positive: {int(n_ref_pos)}")
print(f"Qwen positives: {n_qwen_pos}")
print(f"GLM positives: {n_glm_pos}, negatives: {n_glm_neg}, uncertain: {n_glm_uncertain}")
print(f"Agreement with Qwen: {agree}/{n_valid} ({100*agree_rate:.1f}%)")
print(f"Positive recall vs Qwen: {glm_pos_on_qwen}/{qwen_precision_denom} ({100*pos_recall_vs_qwen:.1f}%)" if pos_recall_vs_qwen is not None else "N/A")
print(f"Positive precision vs Qwen: {qwen_pos_on_glm}/{len(glm_pos_set)} ({100*pos_precision_vs_qwen:.1f}%)" if pos_precision_vs_qwen is not None else "N/A")
print(f"False negatives (GLM neg, Qwen pos): {fn_count}")
print(f"False positives (GLM pos, Qwen neg): {fp_count}")
print(f"Hard negative false positives: {hnfp_count}")
print(f"GLM uncertain rate: {100*uncertain_rate:.1f}%")

# Cluster-level metrics
if "event_cluster_id" in combined.columns:
    qwen_pos_clusters = combined[combined["qwen_label"] == "positive"]["event_cluster_id"].dropna().unique()
    glm_pos_clusters = combined[combined["glm_label"] == "positive"]["event_cluster_id"].dropna().unique()
    ref_pos_clusters = combined[combined["is_positive"] == True]["event_cluster_id"].dropna().unique()
    missed_clusters = set(qwen_pos_clusters) - set(glm_pos_clusters)
    cluster_recall = len(set(glm_pos_clusters) & set(qwen_pos_clusters)) / len(qwen_pos_clusters) if len(qwen_pos_clusters) > 0 else None

    # Singleton clusters
    singleton_info = combined[combined["is_singleton_cluster"] == True]
    qwen_singleton_pos = singleton_info[singleton_info["qwen_label"] == "positive"]
    glm_singleton_pos = singleton_info[singleton_info["glm_label"] == "positive"]
    missed_singletons = set(qwen_singleton_pos["anchor_id"]) - set(glm_singleton_pos["anchor_id"])

    print(f"\n--- Cluster-level Metrics ---")
    print(f"Qwen positive clusters: {len(qwen_pos_clusters)}")
    print(f"GLM positive clusters: {len(glm_pos_clusters)}")
    print(f"Cluster recall vs Qwen: {cluster_recall}" if cluster_recall is not None else "N/A")
    print(f"Missed positive clusters: {len(missed_clusters)}")
    print(f"  Missed cluster IDs: {sorted(missed_clusters)}")
    print(f"Missed singleton clusters: {len(missed_singletons)}")

# Bias analysis
glm_pos_rate = n_glm_pos / n_valid if n_valid > 0 else 0
qwen_pos_rate = n_qwen_pos / n_valid if n_valid > 0 else 0
glm_more_conservative = glm_pos_rate < qwen_pos_rate
print(f"\n--- Bias Analysis ---")
print(f"GLM positive rate: {100*glm_pos_rate:.1f}%")
print(f"Qwen positive rate: {100*qwen_pos_rate:.1f}%")
if glm_more_conservative:
    print(f"GLM is more conservative (fewer positives) than Qwen")
else:
    print(f"GLM is more aggressive (more positives) than Qwen")

# Actor type confusion
if "glm_actor_type" in valid.columns and "involved_object" in valid.columns:
    actor_agree = valid[valid["qwen_label"] == "positive"]
    if len(actor_agree) > 0:
        print(f"\nActor type on Qwen positives:")
        for _, r in actor_agree.iterrows():
            print(f"  {r['anchor_id']}: Qwen_involved={r.get('involved_object','?')}, GLM_actor={r['glm_actor_type']}")

# Latency
latency = combined["runtime_seconds"].dropna()
if len(latency) > 0:
    lat_summary = {
        "mean_latency_s": round(latency.mean(), 3),
        "p50_latency_s": round(latency.median(), 3),
        "p95_latency_s": round(latency.quantile(0.95), 3),
        "min_latency_s": round(latency.min(), 3),
        "max_latency_s": round(latency.max(), 3),
        "peak_gpu_memory_gb": round(combined["peak_gpu_memory_gb"].dropna().max(), 3),
        "n_samples_with_latency": len(latency),
    }
    pd.DataFrame([lat_summary]).to_csv(f"{OUT_TABLES}/latency_summary.csv", index=False)
    print(f"\n--- Latency Summary ---")
    print(f"Mean: {lat_summary['mean_latency_s']:.1f}s, P50: {lat_summary['p50_latency_s']:.1f}s, P95: {lat_summary['p95_latency_s']:.1f}s")

# Save disagreement cases
disagreement = valid[valid["glm_label"] != valid["qwen_label"]]
disagreement.to_csv(f"{OUT_TABLES}/disagreement_cases.csv", index=False)
print(f"\nDisagreement cases: {len(disagreement)}")

# Save false negative cases
fn.to_csv(f"{OUT_TABLES}/false_negative_cases.csv", index=False)
print(f"False negative cases: {len(fn)}")

# Save hard negative false positive cases
hard_neg_fp.to_csv(f"{OUT_TABLES}/hard_negative_false_positive_cases.csv", index=False)
print(f"Hard negative FP cases: {len(hard_neg_fp)}")

# Summary dictionary
summary = {
    "n_samples": len(combined),
    "n_valid": n_valid,
    "n_reference_positive": int(n_ref_pos),
    "n_qwen_positive": int(n_qwen_pos),
    "n_glm_positive": int(n_glm_pos),
    "n_glm_negative": int(n_glm_neg),
    "n_glm_uncertain": int(n_glm_uncertain),
    "agreement_with_qwen": int(agree),
    "agreement_rate_with_qwen": round(agree_rate, 4),
    "positive_recall_vs_qwen": round(pos_recall_vs_qwen, 4) if pos_recall_vs_qwen is not None else None,
    "positive_precision_vs_qwen": round(pos_precision_vs_qwen, 4) if pos_precision_vs_qwen is not None else None,
    "false_negative_count": fn_count,
    "false_positive_count": fp_count,
    "hard_negative_false_positive_count": hnfp_count,
    "uncertain_rate_glm": round(uncertain_rate, 4),
    "n_reference_positive_clusters": len(ref_pos_clusters) if "event_cluster_id" in combined.columns else None,
    "cluster_recall_vs_qwen": round(cluster_recall, 4) if "event_cluster_id" in combined.columns and cluster_recall is not None else None,
    "missed_positive_clusters": len(missed_clusters) if "event_cluster_id" in combined.columns else None,
    "missed_singleton_clusters": len(missed_singletons) if "is_singleton_cluster" in combined.columns else None,
    "glm_positive_rate": round(glm_pos_rate, 4),
    "qwen_positive_rate": round(qwen_pos_rate, 4),
    "glm_more_conservative": bool(glm_more_conservative),
    "qwen_reference_mode": qwen_mode["qwen_reference_mode"],
}

with open(f"{OUT_TABLES}/comparison_summary.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)

print(f"\n{'='*60}")
print("Paired comparison complete.")
print(f"{'='*60}")
