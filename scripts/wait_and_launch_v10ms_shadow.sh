#!/usr/bin/env bash
# Non-semantic launch waiter. The frozen runner re-authenticates every pair.
set -euo pipefail
root_dir="/root/charm/GVAQP"
log_path="$root_dir/outputs/v10_multiseal_reference_v1/SHADOW_GPU_WAIT.log"
target_indices="1 2 3 5 6 7"

ready_now() {
  local table apps index util memory uuid
  table="$(nvidia-smi --query-gpu=index,uuid,utilization.gpu,memory.used --format=csv,noheader,nounits)" || return 1
  apps="$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader,nounits 2>/dev/null || true)"
  for index in $target_indices; do
    local row
    row="$(printf '%s\n' "$table" | awk -F, -v wanted="$index" '$1+0==wanted {gsub(/^ +| +$/, "", $2); gsub(/^ +| +$/, "", $3); gsub(/^ +| +$/, "", $4); print $2 "," $3 "," $4}')"
    [ -n "$row" ] || return 1
    uuid="${row%%,*}"; row="${row#*,}"; util="${row%%,*}"; memory="${row#*,}"
    [ "$util" -eq 0 ] && [ "$memory" -le 16 ] || return 1
    ! printf '%s\n' "$apps" | grep -Fqx "$uuid" || return 1
  done
}

while true; do
  if ready_now; then
    printf '%s sealed V10-MS shadow GPU pairs authenticated idle; launching frozen seal\n' "$(date -u +%FT%TZ)" >> "$log_path"
    cd "$root_dir"
    exec env PYTHONPATH=src .venv-v7-oracle/bin/python scripts/run_v10_multiseal_oracle.py launch --kind shadow >> "$log_path" 2>&1
  fi
  printf '%s waiting for V10-MS shadow GPU pairs\n' "$(date -u +%FT%TZ)" >> "$log_path"
  sleep 60
done
