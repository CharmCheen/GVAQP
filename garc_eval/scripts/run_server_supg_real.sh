#!/bin/bash
# Run SUPG experiments on real frame-level data.
# Requires supg_source.csv from materialization step.
#
# Usage:
#   bash garc_eval/scripts/run_server_supg_real.sh

set -euo pipefail

# === Configure these paths ===
export GARC_HOME="/path/to/project"
export GARC_OUTPUT_DIR="${GARC_HOME}/garc_eval/outputs"

PYTHON="${GARC_HOME}/../conda_envs/supg/python.exe"  # adjust for server
SOURCE_CSV="${GARC_OUTPUT_DIR}/real_frames/supg_source.csv"
OUTDIR="${GARC_OUTPUT_DIR}/real_frames/supg_results"

# === Run experiments ===
echo "=== Running SUPG on real frames ==="
${PYTHON} -m garc_eval.experiments.run_supg_real_frames \
    --source-csv ${SOURCE_CSV} \
    --budget 10000 \
    --gamma 0.9 \
    --delta 0.05 \
    --trials 100 \
    --outdir ${OUTDIR}

echo "=== Done. Results in ${OUTDIR} ==="
echo "  summary.csv, summary.md, per_trial_results.csv"
echo "  boxplot_rt_recall.png, boxplot_pt_precision.png"
