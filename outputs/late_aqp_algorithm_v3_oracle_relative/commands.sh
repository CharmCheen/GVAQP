#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/outputs/late_aqp_algorithm_v3_oracle_relative"

echo "Running LATE-AQP algorithm v3 oracle-relative analysis..."
python3 "$OUT/run_algorithm_v3.py"

echo "Done. Outputs in $OUT"
