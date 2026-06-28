#!/bin/bash
# Materialize proxy and oracle scores for real video frames.
# Run this ONCE per video. Results are cached as parquet files.
#
# Usage:
#   bash garc_eval/scripts/run_server_materialization.sh

set -euo pipefail

# === Configure these paths ===
export GARC_HOME="/path/to/project"
export GARC_MODEL_DIR="${GARC_HOME}/models"
export GARC_DATA_DIR="${GARC_HOME}/data"
export GARC_OUTPUT_DIR="${GARC_HOME}/garc_eval/outputs"

PYTHON="${GARC_HOME}/../conda_envs/supg/python.exe"  # adjust for server
CONFIG="garc_eval/configs/real_frame_yolo.example.yaml"

# === Step 1: Extract frames ===
echo "=== Step 1: Extracting frames ==="
${PYTHON} -m garc_eval.datasets.extract_video_frames \
    --video "${GARC_DATA_DIR}/videos/sample.mp4" \
    --video-id sample \
    --outdir "${GARC_DATA_DIR}/frames/sample" \
    --frame-table "${GARC_OUTPUT_DIR}/real_frames/frame_metadata.parquet" \
    --sample-fps 1.0

# === Step 2: Materialize scores ===
echo "=== Step 2: Materializing proxy/oracle scores ==="
${PYTHON} -m garc_eval.experiments.materialize_frame_scores \
    --config ${CONFIG}

# === Optional: Use GT labels instead of oracle model ===
# ${PYTHON} -m garc_eval.experiments.materialize_frame_scores \
#     --config ${CONFIG} \
#     --skip-oracle

# === Optional: Reuse existing scores ===
# ${PYTHON} -m garc_eval.experiments.materialize_frame_scores \
#     --config ${CONFIG} \
#     --skip-proxy --use-existing-proxy "${GARC_OUTPUT_DIR}/real_frames/proxy_scores.parquet" \
#     --skip-oracle --use-existing-oracle "${GARC_OUTPUT_DIR}/real_frames/oracle_scores.parquet"

echo "=== Done. Output in ${GARC_OUTPUT_DIR}/real_frames/ ==="
