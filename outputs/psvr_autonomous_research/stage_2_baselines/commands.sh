#!/usr/bin/env bash
PYTHONPATH=src pytest -q tests/psvr_runtime
python scripts/run_psvr_core_pilot.py baselines --runs 3
python scripts/run_psvr_core_pilot.py coverage-debt --runs 3
python scripts/run_psvr_core_pilot.py finalize
