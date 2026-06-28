#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="${ROOT}/test_vlm/outputs/clip_aqp_phase1_video_access_v1"
mkdir -p "${OUT}/logs"

cd "${ROOT}"
{
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Nexar video access audit start"
  python "${OUT}/scripts/00_local_file_audit.py"
  python "${OUT}/scripts/10_remote_access_audit.py"
  python "${OUT}/scripts/20_download_smoke_videos.py"
  python "${OUT}/scripts/30_generate_video_access_report.py"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Nexar video access audit complete"
} 2>&1 | tee "${OUT}/logs/run_video_access_audit.log"
