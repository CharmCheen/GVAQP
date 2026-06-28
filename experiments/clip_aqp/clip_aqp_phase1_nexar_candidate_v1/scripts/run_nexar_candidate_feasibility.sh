#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="$ROOT/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v1"
LOG="$OUT/logs/run_nexar_candidate_feasibility.log"

mkdir -p "$OUT/logs"
cd "$OUT"

{
  echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "root=$ROOT"
  echo "out=$OUT"
  echo "command=python -m py_compile scripts/*.py"
  python -m py_compile scripts/*.py
  echo "command=python scripts/nexar_candidate_feasibility.py"
  python scripts/nexar_candidate_feasibility.py
  echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$LOG"
