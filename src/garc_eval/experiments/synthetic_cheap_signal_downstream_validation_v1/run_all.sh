#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

python src/garc_eval/experiments/synthetic_cheap_signal_downstream_validation_v1/run_experiment.py
pytest -q src/garc_eval/tests/test_craq_lite_metrics.py src/garc_eval/tests/test_synthetic_cheap_signal_downstream_validation.py
