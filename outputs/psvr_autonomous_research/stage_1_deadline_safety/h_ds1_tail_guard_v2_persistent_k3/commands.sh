#!/usr/bin/env bash
PYTHONPATH=src pytest -q tests/psvr_runtime
python scripts/run_deadline_safety_validation.py pilot --runs 1
python scripts/run_deadline_safety_validation.py profile --runs 20
python scripts/run_deadline_safety_validation.py short --runs 10
python scripts/run_deadline_safety_validation.py mid --runs 3
python scripts/run_deadline_safety_validation.py finalize
