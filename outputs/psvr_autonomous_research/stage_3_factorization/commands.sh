#!/usr/bin/env bash
PYTHONPATH=src pytest -q tests/psvr_runtime
python scripts/analyze_psvr_stage3_attribution.py
python scripts/run_psvr_stage3_factorization.py smoke
python scripts/run_psvr_stage3_factorization.py matrix
python scripts/run_psvr_stage3_factorization.py finalize
