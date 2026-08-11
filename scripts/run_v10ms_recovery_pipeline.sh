#!/usr/bin/env bash
# Non-semantic V10-MS orchestration. It invokes only frozen, hash-bound code.
set -euo pipefail
root_dir="/root/charm/GVAQP"
out_dir="$root_dir/outputs/v10_multiseal_reference_v1"
log="$out_dir/V10MS_PIPELINE.log"

log_line() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$log"; }

ready_pairs() {
  local targets="$1" table apps index row uuid util memory
  table="$(nvidia-smi --query-gpu=index,uuid,utilization.gpu,memory.used --format=csv,noheader,nounits)" || return 1
  apps="$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader,nounits 2>/dev/null || true)"
  for index in $targets; do
    row="$(printf '%s\n' "$table" | awk -F, -v wanted="$index" '$1+0==wanted {gsub(/^ +| +$/, "", $2); gsub(/^ +| +$/, "", $3); gsub(/^ +| +$/, "", $4); print $2 "," $3 "," $4}')"
    [ -n "$row" ] || return 1
    uuid="${row%%,*}"; row="${row#*,}"; util="${row%%,*}"; memory="${row#*,}"
    [ "$util" -eq 0 ] && [ "$memory" -le 16 ] || return 1
    ! printf '%s\n' "$apps" | grep -Fqx "$uuid" || return 1
  done
}

wait_pairs() {
  local targets="$1" label="$2"
  until ready_pairs "$targets"; do log_line "waiting for $label GPU pairs: $targets"; sleep 60; done
  log_line "authenticated idle precondition observed for $label GPU pairs: $targets"
}

cd "$root_dir"
wait_pairs "1 2 3 5 6 7" "outcome-blind shadow"
log_line "launching frozen V10-MS shadow seal"
env PYTHONPATH=src .venv-v7-oracle/bin/python scripts/run_v10_multiseal_oracle.py launch --kind shadow >> "$log" 2>&1
log_line "running frozen cross-seal compatibility finalizer"
env PYTHONPATH=src .venv-v7-oracle/bin/python scripts/finalize_v10_multiseal_reference.py compatibility >> "$log" 2>&1
status="$(PYTHONPATH=src .venv-v7-oracle/bin/python -c 'import json; print(json.load(open("outputs/v10_multiseal_reference_v1/CROSS_SEAL_COMPATIBILITY_DECISION.json"))["status"])')"
case "$status" in PASS|QUALIFIED_PASS) ;; *) log_line "terminal compatibility failure: $status"; exit 2;; esac
wait_pairs "2 6" "exact DALI missing-set"
log_line "launching frozen V10-MS exact missing-unit Seal B"
env PYTHONPATH=src .venv-v7-oracle/bin/python scripts/run_v10_multiseal_oracle.py launch --kind missing >> "$log" 2>&1
log_line "running frozen complete-only multi-seal finalizer"
env PYTHONPATH=src .venv-v7-oracle/bin/python scripts/finalize_v10_multiseal_reference.py finalize >> "$log" 2>&1
log_line "V10-MS reference pipeline complete; P0 remains explicitly unlaunched"
