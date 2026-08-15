#!/usr/bin/env bash
# CPU-only MAB gate reproduction script.
# Run from the repository root with the audit venv:
#   uv venv /tmp/gvaqp_audit_venv --python 3.11
#   uv pip install --python /tmp/gvaqp_audit_venv/bin/python numpy pyarrow pandas pytest scipy scikit-learn
set -euo pipefail
PY=${PY:-/tmp/gvaqp_audit_venv/bin/python}
cd "$(dirname "$0")/.."

echo "== validation (engine fidelity vs frozen P2 manifest) =="
"$PY" scripts/mab_cpu_gate/validate_engine.py

echo "== phase 0: asset audit =="
"$PY" scripts/mab_cpu_gate/phase0_assets.py

echo "== phase 1: granularity phase diagram =="
"$PY" scripts/mab_cpu_gate/phase1_granularity.py

echo "== phase 2: full-information action-value table =="
"$PY" scripts/mab_cpu_gate/phase2_action_table.py

echo "== phase 3: MAB gate metrics =="
"$PY" scripts/mab_cpu_gate/phase3_gate_metrics.py

echo "== phase 4: MAB-v0 (runs only if gates pass) =="
"$PY" scripts/mab_cpu_gate/phase4_mab_v0.py

echo "== tests =="
"$PY" -m pytest tests/mab_cpu_gate -q

echo "== finalize =="
"$PY" scripts/mab_cpu_gate/finalize_report.py
