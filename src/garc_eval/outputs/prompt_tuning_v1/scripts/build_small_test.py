#!/usr/bin/env python3
"""Build a small focused test set for fast prompt iteration."""
import pandas as pd

BASE = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/prompt_tuning_v1'
PRED_CSV = '/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1/tables/paired_predictions.csv'

df = pd.read_csv(PRED_CSV)
valid = df[df['qwen_parsed'] == True].copy()

# GLM focused test: 10 clearest false negatives + 5 negatives = 15 clips
glm_fn = valid[(valid['glm_label'] == 'negative') & (valid['qwen_label'] == 'positive') & (valid['is_positive'] == True)]
# Pick the most unambiguous positive cases (from our visual review)
glm_fn_pick = glm_fn[glm_fn['anchor_id'].isin([
    'center10_anchor_0161',  # pedestrian with umbrella - very clear
    'center10_anchor_0129',  # motorcycle crossing - very clear
    'center10_anchor_0175',  # pedestrian walking across - very clear
    'center10_anchor_0254',  # many pedestrians crossing - very clear
    'center10_anchor_0068',  # pedestrians at intersection
    'center10_anchor_0172',  # pedestrians crossing
    'center10_anchor_0183',  # pedestrians under overpass
    'center10_anchor_0246',  # pedestrians and cyclists
    'center10_anchor_0317',  # dark SUV at intersection
    'center10_anchor_0171',  # cyclist crossing
])]

# 5 negatives that GLM got right (should stay negative)
glm_neg = valid[(valid['glm_label'] == 'negative') & (valid['is_positive'] == False)].head(5)

glm_small = pd.concat([glm_fn_pick, glm_neg]).drop_duplicates(subset='anchor_id')
glm_small = glm_small[['anchor_id', 'is_positive', 'sample_type']].copy()
glm_small['ground_truth'] = glm_small['is_positive'].map({True: 'positive', False: 'negative'})
glm_small.to_csv(f'{BASE}/test_sets/glm_test_small.csv', index=False)
print(f'GLM small test: {len(glm_small)} clips')
print(glm_small[['anchor_id', 'ground_truth', 'sample_type']].to_string(index=False))
