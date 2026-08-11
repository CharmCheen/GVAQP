#!/usr/bin/env bash
# Execution-only V10-MS resource allocator.  It never reads semantic outputs.
set -euo pipefail

ROOT=/root/charm/GVAQP
OUT="$ROOT/outputs/v10_multiseal_reference_v1"
PY="$ROOT/.venv-v7-oracle/bin/python"
POLL_SECONDS="${V10MS_POLL_SECONDS:-180}"
MIN_FREE_MIB="${V10MS_MIN_FREE_MIB:-60000}"
MAX_USED_MIB="${V10MS_MAX_USED_MIB:-16}"
LOG="$OUT/ANY_TWO_A100_WAIT.log"

find_pair() {
  MIN_FREE_MIB="$MIN_FREE_MIB" MAX_USED_MIB="$MAX_USED_MIB" "$PY" - <<'PY'
import csv
import io
import os
import subprocess

gpu_text = subprocess.check_output([
    "nvidia-smi",
    "--query-gpu=index,uuid,name,memory.free,memory.used,utilization.gpu",
    "--format=csv,noheader,nounits",
], text=True)
app_text = subprocess.check_output([
    "nvidia-smi",
    "--query-compute-apps=gpu_uuid,pid,used_memory",
    "--format=csv,noheader,nounits",
], text=True)
busy = {row[0].strip() for row in csv.reader(io.StringIO(app_text)) if row and row[0].strip()}
eligible = []
for row in csv.reader(io.StringIO(gpu_text)):
    index, uuid, name, free_mib, used_mib, util = [value.strip() for value in row]
    if (
        name == "NVIDIA A100-SXM4-80GB"
        and uuid not in busy
        and int(free_mib) >= int(os.environ["MIN_FREE_MIB"])
        and int(used_mib) <= int(os.environ["MAX_USED_MIB"])
        and int(util) <= 5
    ):
        eligible.append(int(index))
if len(eligible) >= 2:
    print(f"{eligible[0]},{eligible[1]}")
PY
}

if [[ -e "$OUT/MULTI_SEAL_PROTOCOL.json" ]]; then
  echo "$(date -u +%FT%TZ) active V10-MS root exists; refusing to overwrite immutable protocol" >> "$LOG"
  exit 2
fi

while true; do
  PAIR="$(find_pair || true)"
  if [[ -z "$PAIR" ]]; then
    echo "$(date -u +%FT%TZ) WAIT_FOR_ANY_TWO_ELIGIBLE_A100 min_free_mib=$MIN_FREE_MIB max_used_mib=$MAX_USED_MIB" >> "$LOG"
    sleep "$POLL_SECONDS"
    continue
  fi

  echo "$(date -u +%FT%TZ) ACQUIRED_CURRENT_TWO_GPU_TOPOLOGY=$PAIR" >> "$LOG"
  export V10MS_SINGLE_GPU=0
  export V10MS_TWO_GPU_IDS="$PAIR"
  export PYTHONPATH=src
  cd "$ROOT"
  "$PY" scripts/create_v10_multiseal_protocol.py >> "$LOG" 2>&1
  "$PY" scripts/run_v10_multiseal_oracle.py prepare --kind shadow >> "$LOG" 2>&1
  "$PY" scripts/run_v10_multiseal_oracle.py launch --kind shadow >> "$LOG" 2>&1
  "$PY" scripts/finalize_v10_multiseal_reference.py compatibility >> "$LOG" 2>&1

  STATUS="$($PY - <<'PY'
import json
print(json.load(open('outputs/v10_multiseal_reference_v1/CROSS_SEAL_COMPATIBILITY_DECISION.json'))['status'])
PY
)"
  if [[ "$STATUS" != "PASS" && "$STATUS" != "QUALIFIED_PASS" ]]; then
    echo "$(date -u +%FT%TZ) CROSS_SEAL_COMPATIBILITY=$STATUS; no missing-unit execution" >> "$LOG"
    exit 3
  fi

  "$PY" scripts/run_v10_multiseal_oracle.py prepare --kind missing >> "$LOG" 2>&1
  "$PY" scripts/run_v10_multiseal_oracle.py launch --kind missing >> "$LOG" 2>&1
  "$PY" scripts/finalize_v10_multiseal_reference.py finalize >> "$LOG" 2>&1
  echo "$(date -u +%FT%TZ) MULTI_SEAL_REFERENCE_FINALIZED; P0 binding required next" >> "$LOG"
  exit 0
done
