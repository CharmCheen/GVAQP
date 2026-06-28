#!/usr/bin/env bash
set -euo pipefail

cd /qiuyeqing/llama_prl/G-ARC/test_vlm
source /qiuyeqing/llama_prl/G-ARC/env_garc.sh

python focused_validation_outputs/07_sampling_baseline_comparison/scripts/compare_sampling_baselines.py \
  --labels_csv /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv \
  --proxy_csv /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores_with_learned.csv \
  --event_metrics_csv /qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/03_event_conversion/event_level_metrics.csv \
  --out_dir /qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/07_sampling_baseline_comparison \
  --budget_fracs 0.05,0.10,0.15,0.20,0.25,0.30 \
  --gap_seconds 3 \
  --iou_threshold 0.3 \
  --seeds 100
