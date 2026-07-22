#!/usr/bin/env bash
PYTHONPATH=src pytest -q tests/psvr_runtime
PYTHONPATH=src python scripts/verify_psvr_hscan1b.py
python scripts/run_psvr_hscan1b.py tie
python scripts/evaluate_psvr_hscan1b.py tie
python scripts/run_psvr_hscan1b.py factorial
python scripts/evaluate_psvr_hscan1b.py factorial
