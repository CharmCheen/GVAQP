#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/qiuyeqing/llama_prl/G-ARC"
OUT_DIR="${ROOT_DIR}/test_vlm/outputs/micro_casq_32b_oracle_v0"
LOG_DIR="${OUT_DIR}/logs"
LOG_FILE="${LOG_DIR}/run_micro_casq_32b_oracle_v0.log"

mkdir -p "${LOG_DIR}"
exec > >(tee -a "${LOG_FILE}") 2>&1

cd "${ROOT_DIR}"

echo "[micro-casq-32b-oracle-v0] start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python "${OUT_DIR}/scripts/check_32b_gpu_device.py"
python "${OUT_DIR}/scripts/build_micro_casq_32b_oracle_v0.py" --run
python -m py_compile "${OUT_DIR}"/scripts/*.py 2>&1 | tee "${LOG_DIR}/py_compile.log"
python "${OUT_DIR}/scripts/build_micro_casq_32b_oracle_v0.py" --completion
echo "[micro-casq-32b-oracle-v0] done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
