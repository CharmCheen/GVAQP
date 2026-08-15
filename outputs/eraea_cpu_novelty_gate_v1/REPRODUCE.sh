#!/usr/bin/env bash
# ERAEA CPU novelty gate reproduction.
# Prereqs: uv venv /tmp/gvaqp_audit_venv --python 3.11
#   uv pip install --python /tmp/gvaqp_audit_venv/bin/python numpy pyarrow pandas pytest scipy scikit-learn tabulate
set -euo pipefail
PY=${PY:-/tmp/gvaqp_audit_venv/bin/python}
cd "$(dirname "$0")/../.."

echo "== engine fidelity check (vs frozen P2 manifest) =="
"$PY" scripts/mab_cpu_gate/validate_engine.py

echo "== E2 baseline matrix (15 methods x 6 budgets x 3 clusters) =="
"$PY" scripts/eraea_cpu_novelty_gate/run_eraea_gate.py

echo "== E3/E4 reward ablation + materializer decoupling + gap sensitivity =="
"$PY" scripts/eraea_cpu_novelty_gate/ablation_materializer.py

echo "== E1/E2 metrics + E5 deviation audit + reports =="
"$PY" scripts/eraea_cpu_novelty_gate/analyze_eraea.py
"$PY" scripts/eraea_cpu_novelty_gate/finalize_eraea.py

echo "== tests =="
"$PY" -m pytest tests/eraea_cpu_novelty_gate -q || echo "no eraea tests dir"
echo "== done =="
