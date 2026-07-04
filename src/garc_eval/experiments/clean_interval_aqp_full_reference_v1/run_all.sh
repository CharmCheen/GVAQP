#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
EXP_DIR="$ROOT_DIR/src/garc_eval/experiments/clean_interval_aqp_full_reference_v1"
OUT_DIR="$ROOT_DIR/src/garc_eval/outputs/clean_interval_aqp_full_reference_v1"

mkdir -p "$OUT_DIR/logs"

{
  echo "run_all_start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "root_dir=$ROOT_DIR"
  echo "exp_dir=$EXP_DIR"
  echo "out_dir=$OUT_DIR"
  echo "command=bash src/garc_eval/experiments/clean_interval_aqp_full_reference_v1/run_all.sh"
} > "$OUT_DIR/logs/run_all_command.txt"

for stage in stage0 stage1 stage2 stage3 stage4 stage5 stage6 stage7 stage8 stage9 stage10; do
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] running $stage"
  python "$EXP_DIR/pipeline.py" "$stage" 2>&1 | tee "$OUT_DIR/logs/${stage}.log"
done

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] complete"
