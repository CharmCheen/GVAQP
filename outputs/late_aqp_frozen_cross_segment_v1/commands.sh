#!/usr/bin/env bash
# Reproducible commands for late_aqp_frozen_cross_segment_v1
set -euo pipefail

ROOT=/qiuyeqing/llama_prl/G-ARC
OUT=$ROOT/outputs/late_aqp_frozen_cross_segment_v1

cd "$ROOT"

# 1. Run the frozen cross-segment replay with repair-trace logging.
python3 "$OUT/run_frozen_cross_segment.py"

# 2. Generate human-readable reports from the raw CSVs.
python3 "$OUT/generate_reports.py"

# 3. Secondary analysis (does not re-run experiments).
python3 "$OUT/secondary_analysis.py"

# 4. (Optional) Inspect the final summary.
cat "$OUT/FINAL_REPORT.md"
