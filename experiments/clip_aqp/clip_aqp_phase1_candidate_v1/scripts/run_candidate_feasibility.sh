#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="${ROOT}/test_vlm/outputs/clip_aqp_phase1_candidate_v1"
mkdir -p "${OUT}/logs"

cd "${ROOT}"
{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] phase1.4 candidate feasibility start"
  python "${OUT}/scripts/00_prepare_candidate_subset.py"
  python "${OUT}/scripts/01_download_or_link_nexar_videos.py"
  python "${OUT}/scripts/10_extract_frames.py"
  python "${OUT}/scripts/20_generate_candidates.py"
  python "${OUT}/scripts/30_evaluate_candidates.py"
  python "${OUT}/scripts/40_certify_candidate_sets.py"
  python "${OUT}/scripts/50_generate_candidate_report.py"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] phase1.4 candidate feasibility complete"
} 2>&1 | tee "${OUT}/logs/run_candidate_feasibility.log"
