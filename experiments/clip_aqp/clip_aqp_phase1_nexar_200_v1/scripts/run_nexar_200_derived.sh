#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="$ROOT/test_vlm/outputs/clip_aqp_phase1_nexar_200_v1"
LOG="$OUT/logs/run_nexar_200_derived.log"

mkdir -p "$OUT/logs"
{
  echo "Nexar-200 derived run started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  cd "$OUT"
  python scripts/00_build_nexar_200_manifest.py
  python scripts/10_convert_nexar_200_to_casq.py
  python scripts/20_validate_nexar_200_casq.py
  python scripts/30_supg_stitch_nexar_200.py
  python scripts/40_block_audit_nexar_200.py
  python scripts/50_generate_nexar_200_report.py
  echo "Nexar-200 derived run completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$LOG"
