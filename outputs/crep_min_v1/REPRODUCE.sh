#!/usr/bin/env bash
# CREP-Min v1 reproduction.
set -euo pipefail
PY=${PY:-/tmp/gvaqp_audit_venv/bin/python}
cd "$(dirname "$0")/../.."

echo "== engine fidelity anchor =="
"$PY" scripts/mab_cpu_gate/validate_engine.py

echo "== phase 3: counterexample suite =="
"$PY" scripts/crep_min/counterexamples.py

echo "== phase 4: certificates + partial intervals =="
"$PY" scripts/crep_min/phase4_certificates.py

echo "== phase 5: gate =="
"$PY" scripts/crep_min/phase5_gate.py

echo "== tests =="
"$PY" -m pytest tests/crep_min tests/mab_cpu_gate tests/eraea_cpu_novelty_gate -q

echo "== done =="
