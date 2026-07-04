#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
EXP_DIR="$ROOT_DIR/src/garc_eval/experiments/clean_interval_aqp_full_reference_v2_label_aligned"
OUT_DIR="$ROOT_DIR/src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned"

mkdir -p "$OUT_DIR/logs"

{
  echo "run_all_start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "root_dir=$ROOT_DIR"
  echo "exp_dir=$EXP_DIR"
  echo "out_dir=$OUT_DIR"
  echo "command=bash src/garc_eval/experiments/clean_interval_aqp_full_reference_v2_label_aligned/run_all.sh"
} > "$OUT_DIR/logs/run_all_command.txt"

python "$EXP_DIR/pipeline.py" all 2>&1 | tee "$OUT_DIR/logs/run_all.log"
