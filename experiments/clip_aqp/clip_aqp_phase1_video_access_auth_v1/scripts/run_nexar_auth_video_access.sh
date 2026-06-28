#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="${ROOT}/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1"
mkdir -p "${OUT}/logs"

cd "${ROOT}"
{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Nexar authenticated video access smoke start"
  python "${OUT}/scripts/00_build_auth_smoke_manifest.py"
  python "${OUT}/scripts/10_download_verify_auth_smoke.py"
  python "${OUT}/scripts/20_frame_smoke.py"
  python "${OUT}/scripts/30_generate_auth_video_report.py"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Nexar authenticated video access smoke complete"
} 2>&1 | tee "${OUT}/logs/run_nexar_auth_video_access.log"
