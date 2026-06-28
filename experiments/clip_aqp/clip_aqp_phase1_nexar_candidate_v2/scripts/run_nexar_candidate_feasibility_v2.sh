#!/usr/bin/env bash
set -euo pipefail

cd /qiuyeqing/llama_prl/G-ARC
source env_garc.sh

python test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/scripts/nexar_candidate_feasibility_v2.py --mode "${1:-full}" 2>&1 | tee test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/logs/run_nexar_candidate_feasibility_v2.log
