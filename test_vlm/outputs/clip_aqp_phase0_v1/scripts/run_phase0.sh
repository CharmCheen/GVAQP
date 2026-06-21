#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
OUT="$ROOT/test_vlm/outputs/clip_aqp_phase0_v1"
cd "$OUT"

{
  echo "Phase 0 run started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python scripts/00_audit_existing_data.py
  python scripts/01_build_phase0_table.py
  python scripts/10_supg_stitch_simulation.py
  python scripts/20_block_audit_simulation.py --mode no_repair
  python scripts/20_block_audit_simulation.py --mode repair_fresh_cert
  python scripts/30_oracle_stability_audit.py
  python scripts/40_generate_report.py
  echo "Phase 0 run completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$OUT/logs/run_phase0.log"
