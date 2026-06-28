#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="${ROOT}/test_vlm/outputs/clip_aqp_phase1_local_candidate_smoke_v1"
mkdir -p "${OUT}/logs"

cd "${ROOT}"
{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] local candidate smoke start"
  python "${OUT}/scripts/00_inventory_local_assets.py"
  python "${OUT}/scripts/10_build_local_smoke_dataset.py"
  python "${OUT}/scripts/20_extract_local_frames.py"
  python "${OUT}/scripts/30_generate_local_candidates.py"
  python "${OUT}/scripts/40_evaluate_local_candidates.py"
  python "${OUT}/scripts/50_generate_local_report.py"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] local candidate smoke complete"
} 2>&1 | tee "${OUT}/logs/run_local_candidate_smoke.log"
