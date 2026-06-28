#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
REPAIR="$ROOT/test_vlm/outputs/clip_aqp_phase0_v1/repair_v1"
cd "$REPAIR"

{
  echo "Phase 0 repair started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python scripts/r10_fix_bound_formula.py
  python scripts/r20_block_audit_no_repair_v2.py
  python scripts/r40_identify_certification_oracle.py
  python scripts/r50_generate_report_v2.py
  python scripts/r60_git_hygiene_snapshot.py
  echo "Phase 0 repair completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$REPAIR/logs/run_phase0_repair.log"
