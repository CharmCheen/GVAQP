#!/usr/bin/env bash
set -euo pipefail

cd /qiuyeqing/llama_prl/G-ARC/test_vlm

CONFIG="${CONFIG:-experiments/roadclip_budget_v2/config.yaml}"
MODE="${1:-full}"

echo "[roadclip_budget_v2] mode=${MODE}"
echo "[roadclip_budget_v2] config=${CONFIG}"

python experiments/roadclip_budget_v2/00_inventory_videos.py --config "${CONFIG}"

if [[ "${MODE}" == "smoke" ]]; then
  python experiments/roadclip_budget_v2/01_filter_road_segments.py --config "${CONFIG}" --limit 5 --smoke-only
  python experiments/roadclip_budget_v2/02_make_road_clips.py --config "${CONFIG}"
  python experiments/roadclip_budget_v2/03_run_proxy_scoring.py --config "${CONFIG}"
  python experiments/roadclip_budget_v2/04_run_conservative_vlm.py --config "${CONFIG}" --limit 10 --smoke-only
  python experiments/roadclip_budget_v2/05_run_budget_simulation.py --config "${CONFIG}"
  python experiments/roadclip_budget_v2/06_make_audit_package.py --config "${CONFIG}"
  python experiments/roadclip_budget_v2/07_final_acceleration_report.py --config "${CONFIG}"
  exit 0
fi

python experiments/roadclip_budget_v2/01_filter_road_segments.py --config "${CONFIG}" --limit 5 --smoke-only
python experiments/roadclip_budget_v2/01_filter_road_segments.py --config "${CONFIG}"

python experiments/roadclip_budget_v2/02_make_road_clips.py --config "${CONFIG}"
python experiments/roadclip_budget_v2/03_run_proxy_scoring.py --config "${CONFIG}"

python experiments/roadclip_budget_v2/04_run_conservative_vlm.py --config "${CONFIG}" --limit 10 --smoke-only
python experiments/roadclip_budget_v2/04_run_conservative_vlm.py --config "${CONFIG}"

python experiments/roadclip_budget_v2/05_run_budget_simulation.py --config "${CONFIG}"
python experiments/roadclip_budget_v2/06_make_audit_package.py --config "${CONFIG}"
python experiments/roadclip_budget_v2/07_final_acceleration_report.py --config "${CONFIG}"
