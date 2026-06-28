#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="$ROOT/test_vlm/outputs/clip_aqp_phase0_v1/power_v1"
cd "$OUT"

{
  echo "Phase 0.6 power run started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python scripts/00_load_repair_outputs.py
  python scripts/10_fit_empirical_block_model.py
  python scripts/20_power_scaling_simulation.py
  python scripts/30_compare_bounds_and_sampling.py
  python scripts/40_generate_power_report.py
  echo "Phase 0.6 power run completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$OUT/logs/run_power_v1.log"
