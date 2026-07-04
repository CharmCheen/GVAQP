#!/usr/bin/env bash
# Reproduce the post-replay diagnostic.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

python3 run_postdiagnostic.py

echo "Post-replay diagnostic complete. Outputs in ${SCRIPT_DIR}/"
