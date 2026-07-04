#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."
python src/garc_eval/experiments/clean_interval_aqp_code_audit_v1/audit.py
