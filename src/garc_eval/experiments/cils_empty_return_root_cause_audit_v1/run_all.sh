#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."
python src/garc_eval/experiments/cils_empty_return_root_cause_audit_v1/audit.py
