#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="$ROOT/test_vlm/outputs/clip_aqp_data_asset_audit_v1"
LOG="$OUT/logs/run_data_asset_audit.log"

mkdir -p "$OUT/logs" "$OUT/tables" "$OUT/reports" "$OUT/scripts" "$OUT/schema"

{
  echo "run_data_asset_audit.sh started at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "root: $ROOT"
  echo "output: $OUT"
  cd "$ROOT"
  python "$OUT/scripts/data_asset_audit.py"
  python -m py_compile "$OUT"/scripts/*.py
  echo "python -m py_compile passed" | tee "$OUT/logs/py_compile.log"
  echo "run_data_asset_audit.sh finished at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$LOG"
