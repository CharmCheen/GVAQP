#!/usr/bin/env python3
"""Build test sets for prompt tuning: GLM (missed cases) and Qwen (false positive cases)."""
import pandas as pd, json, os

BASE = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/prompt_tuning_v1'
PRED_CSV = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1/tables/paired_predictions.csv'

df = pd.read_csv(PRED_CSV)
valid = df[df['qwen_parsed'] == True].copy()

# === GLM test set: cases where GLM missed (said negative, should be positive) ===
# 36 false negatives + 3 true positives (calibration)
glm_fn = valid[(valid['glm_label'] == 'negative') & (valid['qwen_label'] == 'positive')]
glm_tp = valid[(valid['glm_label'] == 'positive') & (valid['qwen_label'] == 'positive') & (valid['is_positive'] == True)]

glm_test = pd.concat([glm_fn, glm_tp]).drop_duplicates(subset='anchor_id')
glm_test = glm_test[['anchor_id', 'is_positive', 'sample_type', 'event_cluster_id']].copy()
glm_test['ground_truth'] = glm_test['is_positive'].map({True: 'positive', False: 'negative'})
glm_test.to_csv(f'{BASE}/test_sets/glm_test_set.csv', index=False)
print(f'GLM test set: {len(glm_test)} clips ({glm_test["ground_truth"].value_counts().to_dict()})')

# === Qwen test set: hard negative false positives + some true positives for balance ===
# 17 hard negative FPs + 10 reference positives (calibration)
qwen_fp = valid[(valid['qwen_label'] == 'positive') & (valid['is_positive'] == False)]
qwen_tp = valid[(valid['glm_label'] == 'positive') & (valid['qwen_label'] == 'positive') & (valid['is_positive'] == True)]
# Add some random negatives that Qwen correctly flagged
qwen_tn_sample = valid[(valid['qwen_label'] == 'negative') & (valid['is_positive'] == False)].sample(n=10, random_state=20260627)

qwen_test = pd.concat([qwen_fp, qwen_tp, qwen_tn_sample]).drop_duplicates(subset='anchor_id')
qwen_test = qwen_test[['anchor_id', 'is_positive', 'sample_type', 'event_cluster_id']].copy()
qwen_test['ground_truth'] = qwen_test['is_positive'].map({True: 'positive', False: 'negative'})
qwen_test.to_csv(f'{BASE}/test_sets/qwen_test_set.csv', index=False)
print(f'Qwen test set: {len(qwen_test)} clips ({qwen_test["ground_truth"].value_counts().to_dict()})')

# Print the anchor IDs for reference
print('\nGLM test anchors:')
for _, r in glm_test.iterrows():
    print(f'  {r["anchor_id"]} gt={r["ground_truth"]} type={r["sample_type"]}')
print('\nQwen test anchors:')
for _, r in qwen_test.iterrows():
    print(f'  {r["anchor_id"]} gt={r["ground_truth"]} type={r["sample_type"]}')
