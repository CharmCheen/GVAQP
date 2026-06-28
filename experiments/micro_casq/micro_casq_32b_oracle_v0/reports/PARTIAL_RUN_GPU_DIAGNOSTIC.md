# Partial Run GPU Diagnostic

Generated: `2026-06-22T14:30:30Z`

The active Micro-CASQ 32B-oracle adjudication loop was stopped after suspected CPU execution or unverified GPU execution. Existing outputs were preserved in place.

## Partial Run Counts

- Attempted samples so far from raw JSON files: `50`
- Attempted samples observed in log lines: `50`
- Successful raw outputs: `46`
- Successful parses recorded in raw JSON: `46`
- `not_run_error` / error raw files: `4`

## GPU Visibility

- GPU compute visible during the run: `unverified`
- Post-stop `nvidia-smi` showed no running GPU processes because the adjudication loop had already been stopped.
- Existing pre-repair raw outputs must be treated as `unverified_gpu_or_cpu_suspected` unless rerun after GPU verification.

## Stop Reason

`suspected_cpu_execution_or_unverified_gpu_execution`

No files under `model_outputs/`, `tables/`, `logs/`, or `reports/` were discarded.
