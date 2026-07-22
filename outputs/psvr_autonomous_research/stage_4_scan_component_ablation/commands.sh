#!/usr/bin/env bash
PYTHONPATH=src pytest -q tests/psvr_runtime
PYTHONPATH=src python scripts/verify_psvr_hscan1a.py
python scripts/run_psvr_hscan1a.py smoke
PYTHONPATH=src python scripts/verify_psvr_hscan1a.py
python scripts/run_psvr_hscan1a.py matrix
python scripts/evaluate_psvr_hscan1a.py
