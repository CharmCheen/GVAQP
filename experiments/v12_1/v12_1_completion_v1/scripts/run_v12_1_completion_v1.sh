#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/qiuyeqing/llama_prl/G-ARC"
OUT_DIR="${ROOT_DIR}/test_vlm/outputs/v12_1_completion_v1"
LOG_DIR="${OUT_DIR}/logs"
LOG_FILE="${LOG_DIR}/run_v12_1_completion_v1.log"

mkdir -p "${LOG_DIR}"
exec > >(tee -a "${LOG_FILE}") 2>&1

cd "${ROOT_DIR}"

MODE="${1:-run}"

echo "[v12_1_completion_v1] start mode=${MODE} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ "${MODE}" == "run" ]]; then
  python "${OUT_DIR}/scripts/v12_1_completion_v1.py" --run
elif [[ "${MODE}" == "postprocess" ]]; then
  python "${OUT_DIR}/scripts/v12_1_completion_v1.py" --postprocess
else
  echo "Unknown mode: ${MODE}" >&2
  exit 2
fi
python -m py_compile "${OUT_DIR}"/scripts/*.py 2>&1 | tee "${LOG_DIR}/py_compile.log"
python "${OUT_DIR}/scripts/v12_1_completion_v1.py" --audit
echo "[v12_1_completion_v1] done mode=${MODE} $(date -u +%Y-%m-%dT%H:%M:%SZ)"
