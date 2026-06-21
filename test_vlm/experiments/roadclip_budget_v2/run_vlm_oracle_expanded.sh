#!/usr/bin/env bash
set -euo pipefail

cd /qiuyeqing/llama_prl/G-ARC/test_vlm

CONFIG="${1:-experiments/roadclip_budget_v2/config_vlm_oracle_expanded.yaml}"
OUT_DIR="/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded"
BASE_OUT="/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2"

mkdir -p "${OUT_DIR}"

if [[ ! -f "${OUT_DIR}/road_segments.csv" ]]; then
  cp "${BASE_OUT}/road_segments.csv" "${OUT_DIR}/road_segments.csv"
fi

if [[ ! -f "${OUT_DIR}/video_inventory.csv" && -f "${BASE_OUT}/video_inventory.csv" ]]; then
  cp "${BASE_OUT}/video_inventory.csv" "${OUT_DIR}/video_inventory.csv"
fi

python experiments/roadclip_budget_v2/02_make_road_clips.py --config "${CONFIG}"
python experiments/roadclip_budget_v2/03_run_proxy_scoring.py --config "${CONFIG}"
python experiments/roadclip_budget_v2/04_run_conservative_vlm.py --config "${CONFIG}" --limit 10 --smoke-only
python experiments/roadclip_budget_v2/04_run_conservative_vlm.py --config "${CONFIG}"
python experiments/roadclip_budget_v2/09_vlm_oracle_acceleration_benchmark.py --config "${CONFIG}"
