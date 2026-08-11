# Long-Horizon True External Blocker

Current phase: `PHASE_2_V7_REFERENCE_EXECUTION`.

## Blocker

The sealed V7 full-grid launcher requires the fixed physical GPU pairs
`[2, 6]`, `[3, 5]`, and `[1, 7]`. All six devices have external compute
contexts and memory residency above the frozen maximum of 16 MiB. The V7
execution root therefore remains absent: no model call, partial label, or
formal reference artifact was created.

## Autonomous recovery attempts

1. Recovered the exact V7 processor runtime in `.venv-v7-oracle` and passed
   all three no-model worker validations.
2. Invoked the original sealed launcher. It rejected the non-idle initial pair
   before initializing an execution root, exactly as its fail-closed policy
   requires.
3. Rechecked the bound GPU pairs over three consecutive long-horizon turns;
   external PIDs `1337010`, `1337011`, `1337012`, `1340363`, `1340364`, and
   `1340365` remain resident (the surrounding process namespace does not
   expose controllable host processes).

## Why user/external action is strictly required

The V7 schedule is sealed to those physical pairs. Reassigning GPUs would
change the preregistered execution protocol; killing the external contexts is
outside the project scope and not authorized. No legal engineering workaround
remains until the external scheduler/process owner releases the six devices.

## Exact minimum action

Release GPUs 1, 2, 3, 5, 6, and 7 so each has no compute context and at most
16 MiB reported memory, then resume with:

```bash
cd /root/charm/GVAQP
PYTHONPATH=src .venv-v7-oracle/bin/python \
  scripts/launch_accelerated_event_query_oracle_v3_full_grid.py
```

## Preserved work

- Frozen scan/proxy release: `outputs/v3_scan_proxy_preregistration_v1/`
- Isolated V7 runtime: `.venv-v7-oracle/`
- Phase checkpoint: `outputs/long_horizon_evidence_convergence_v1/LONG_HORIZON_STATE.json`

P0 and all downstream semantic evaluations remain unexecuted.
