#!/usr/bin/env bash
# Reproduce H7 calibration prep + long-event-only replay.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

python3 run_h7_long_event.py

echo "H7 calibration prep + long-event-only replay complete. Outputs in ${SCRIPT_DIR}/"
