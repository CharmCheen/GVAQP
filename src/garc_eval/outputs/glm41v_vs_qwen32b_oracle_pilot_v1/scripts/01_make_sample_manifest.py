#!/usr/bin/env python3
"""Phase 2: Construct smoke and paired sample manifests."""
import os, sys, yaml, pandas as pd, numpy as np

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"

with open(f"{ROOT}/config/run_config.yaml") as f:
    cfg = yaml.safe_load(f)
with open(f"{ROOT}/config/model_paths.yaml") as f:
    paths = yaml.safe_load(f)

SEED = cfg["random_seed"]
rng = np.random.default_rng(SEED)

canon = pd.read_csv(paths["canonical_table"])
print(f"Loaded {len(canon)} anchors from canonical table")

# Ensure boolean positive
canon["is_positive"] = canon["is_positive"].astype(bool)
canon["oracle_label"] = canon["oracle_label"].fillna(canon["label"])

# Determine best proxy score column
proxy_col = None
for col in ["score_fusion_geometry_motion", "score_fusion_yolo_motion", "object_count_mean", "score_yolo_count"]:
    if col in canon.columns and canon[col].notna().sum() > 0:
        proxy_col = col
        break
print(f"Using proxy column: {proxy_col}")

positives = canon[canon["is_positive"]].copy()
negatives = canon[~canon["is_positive"]].copy()
print(f"Positives: {len(positives)}, Negatives: {len(negatives)}")

# ---- Smoke manifest: 4 positives, 4 hard negatives, 4 random negatives ----
# Hard negatives: top proxy score among negatives
neg_sorted = negatives.sort_values(proxy_col, ascending=False)
hard_neg = neg_sorted.head(4)
# Avoid overlap with hard neg for random selection
remaining_neg = neg_sorted.iloc[4:]
random_neg = remaining_neg.sample(n=4, random_state=rng)

smoke_pos = positives.sample(n=min(4, len(positives)), random_state=rng)
smoke = pd.concat([smoke_pos, hard_neg, random_neg], ignore_index=True)
smoke["sample_type"] = ["reference_positive"] * len(smoke_pos) + ["hard_negative"] * 4 + ["random_negative"] * 4
print(f"Smoke manifest: {len(smoke)} samples ({smoke['is_positive'].sum()} reference positives)")

# ---- Paired manifest: all positives + hard negatives + random negatives ----
paired_pos = positives.copy()
paired_pos["sample_type"] = "reference_positive"

n_hard = min(40, len(negatives))
n_random = min(cfg["n_paired_target"] - len(paired_pos) - n_hard, len(negatives) - n_hard)
n_random = max(0, n_random)

neg_sorted_paired = negatives.sort_values(proxy_col, ascending=False)
paired_hard = neg_sorted_paired.head(n_hard).copy()
paired_hard["sample_type"] = "hard_negative"

remaining_neg_paired = neg_sorted_paired.iloc[n_hard:]
paired_random = remaining_neg_paired.sample(n=min(n_random, len(remaining_neg_paired)), random_state=rng).copy()
paired_random["sample_type"] = "random_negative"

paired = pd.concat([paired_pos, paired_hard, paired_random], ignore_index=True)
print(f"Paired manifest: {len(paired)} samples ({paired['is_positive'].sum()} reference positives)")

# ---- Build output columns ----
out_cols = [
    "anchor_id", "center_time_s", "start_time_s", "end_time_s",
    "oracle_label", "is_positive", "event_cluster_id", "is_singleton_cluster",
    "sample_type", proxy_col
]
rename_map = {proxy_col: "proxy_score"}
for score_col in ["object_count_mean"]:
    if score_col in canon.columns and score_col != proxy_col:
        out_cols.append(score_col)
        rename_map[score_col] = score_col

def build_output(df, out_path, label):
    df = df.copy()
    for c in out_cols:
        if c not in df.columns:
            df[c] = None
    out = df[out_cols].rename(columns=rename_map)
    out["source_table"] = paths["canonical_table"]
    out["random_seed"] = SEED
    out.to_csv(out_path, index=False)
    print(f"Wrote {label}: {out_path} ({len(out)} rows)")

os.makedirs(f"{ROOT}/inputs", exist_ok=True)
build_output(smoke, f"{ROOT}/inputs/sample_manifest_smoke.csv", "smoke")
build_output(paired, f"{ROOT}/inputs/sample_manifest_paired.csv", "paired")

# Print hard negative proxy scores for reference
print(f"\nSmoke hard negative proxy scores ({proxy_col}):")
for _, row in hard_neg.iterrows():
    print(f"  {row['anchor_id']}: proxy={row[proxy_col]:.4f}, cluster={row.get('event_cluster_id','?')}")
