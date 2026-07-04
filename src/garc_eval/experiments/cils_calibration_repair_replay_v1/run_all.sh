#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."
python src/garc_eval/experiments/cils_calibration_repair_replay_v1/replay.py
