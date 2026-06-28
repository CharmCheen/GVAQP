#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="${ROOT}/test_vlm/outputs/clip_aqp_phase1_nexar_200_disentangle_v1"
mkdir -p "${OUT}/logs"

cd "${ROOT}"
{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] smoke run"
  python "${OUT}/scripts/10_run_nexar_200_disentangle.py" --smoke
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] full run"
  python "${OUT}/scripts/10_run_nexar_200_disentangle.py"
} 2>&1 | tee "${OUT}/logs/run_nexar_200_disentangle.log"
