#!/usr/bin/env bash
PYTHONPATH=src pytest -q tests/psvr_runtime/test_deadline_guard.py tests/psvr_runtime/test_capability_isolation.py
python scripts/run_deadline_safety_validation.py profile --runs 20
python scripts/run_deadline_safety_validation.py short --runs 10
python scripts/run_deadline_safety_validation.py mid --runs 3
python scripts/run_deadline_safety_validation.py finalize
