# NVIDIA-SMI GPU Monitoring Report

## Availability

- `nvidia-smi` available: `True`
- GPU name: `NVIDIA A100-SXM4-80GB`
- Python process appeared in compute-apps: `True`

## Observed GPU Use

- Maximum GPU memory used in 1-second GPU monitor: `64695` MiB
- Mean GPU utilization in 1-second GPU monitor: `58.297`%
- Maximum GPU utilization in 1-second GPU monitor: `79`%
- Progress snapshot maximum GPU memory used: `64695` MiB
- Progress snapshot maximum GPU utilization: `80`%
- GPU utilization frequently zero: `False`
- GPU memory stayed high while utilization was low: `True`

## Interpretation

`GPU inference confirmed; GPU memory resident and compute appears bursty / I/O-bound under nvidia-smi sampling`

The final accepted successful 32B-oracle outputs should be considered GPU-backed because the run has all of the following evidence: Python PID `15996` appeared in `nvidia-smi --query-compute-apps` with about 64.7 GiB GPU memory, GPU memory remained resident during inference, GPU utilization/power spikes were captured by `nvidia-smi`/dmon/progress snapshots, and the final result rows record `device_status=gpu_verified` with model parameters on `cuda:0`.

## Limitations

nvidia-smi monitors were attached after the repaired run was already in progress, around the middle of the 153-sample loop; earlier GPU-verified samples rely on torch device diagnostics and raw-output device provenance. Therefore, the monitoring evidence covers the attached/resumed window directly, while earlier repaired samples are supported by the forced-CUDA diagnostic and per-row device provenance rather than the 1-second monitor file.
