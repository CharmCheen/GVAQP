#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="$ROOT/test_vlm/outputs/clip_aqp_phase1_nexar_small_v1"
LOG="$OUT/logs/run_nexar_small_ingestion.log"

mkdir -p "$OUT/logs"
{
  echo "Nexar small ingestion started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cd "$OUT"
  python scripts/00_prepare_nexar_small_subset.py
  python scripts/10_convert_nexar_small_to_casq.py
  python scripts/20_validate_nexar_small_casq.py
  python scripts/30_generate_nexar_small_report.py
  echo "Nexar small ingestion completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$LOG"
