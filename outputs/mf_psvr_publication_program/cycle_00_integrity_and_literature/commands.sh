#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH=src pytest -q
python scripts/audit_mf_psvr_publication_program.py
