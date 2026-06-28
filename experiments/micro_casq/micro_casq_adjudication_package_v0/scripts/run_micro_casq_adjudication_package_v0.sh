#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/qiuyeqing/llama_prl/G-ARC"
OUT_DIR="${ROOT_DIR}/test_vlm/outputs/micro_casq_adjudication_package_v0"
LOG_DIR="${OUT_DIR}/logs"
LOG_FILE="${LOG_DIR}/run_micro_casq_adjudication_package_v0.log"

mkdir -p "${LOG_DIR}"
exec > >(tee "${LOG_FILE}") 2>&1

cd "${ROOT_DIR}"

echo "[micro-casq-package-v0] start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
python "${OUT_DIR}/scripts/build_micro_casq_adjudication_package_v0.py" --build
python -m py_compile "${OUT_DIR}"/scripts/*.py 2>&1 | tee "${LOG_DIR}/py_compile.log"
python "${OUT_DIR}/scripts/build_micro_casq_adjudication_package_v0.py" --completion
echo "[micro-casq-package-v0] done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
