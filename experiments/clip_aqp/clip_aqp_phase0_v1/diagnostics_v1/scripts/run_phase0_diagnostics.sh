#!/usr/bin/env bash
set -euo pipefail

ROOT="/qiuyeqing/llama_prl/G-ARC"
DIAG="$ROOT/test_vlm/outputs/clip_aqp_phase0_v1/diagnostics_v1"
cd "$DIAG"

{
  echo "Phase 0 diagnostics started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python scripts/d10_sample_size_accounting.py
  python scripts/d20_bound_decomposition.py
  python scripts/d30_oracle_stability_detail.py
  python scripts/d40_generate_diagnostic_report.py
  echo "Phase 0 diagnostics completed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$DIAG/logs/run_phase0_diagnostics.log"
