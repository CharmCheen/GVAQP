#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="$ROOT/test_vlm/outputs/clip_aqp_phase1_data_v1"
LOG="$OUT/logs/run_phase1_data_audit.log"

mkdir -p "$OUT/logs"
{
  echo "Phase 1 data audit started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cd "$OUT"
  python scripts/00_create_phase1_data_dirs.py
  python scripts/20_build_micro_casq_template.py
  python scripts/01_validate_casq_schema.py
  python scripts/10_convert_dota_to_casq.py
  python scripts/11_convert_dada_to_casq.py
  python scripts/12_convert_nexar_to_casq.py
  echo "Phase 1 data audit completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$LOG"
