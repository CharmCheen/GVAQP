# Code Diff Report

## Files modified

- `outputs/late_aqp_d3_accounting_fix_v1/run_d3_accounting_fix.py` (new file)
- No changes to existing files in `outputs/late_aqp_event_diverse_discovery_v1/`.

## Function changed

- `discovery_d3_chunk_bandit` → `discovery_d3_chunk_bandit_fixed`

## What changed

| Aspect | Before | After |
|---|---|---|
| `queried` argument | Ignored | Used to initialize bandit state and exclude bins |
| `sampled` set | Starts empty | Starts as copy of `queried` |
| `n_c` init | Zeros | Counts queried bins per chunk |
| `N1_c` init | Zeros | Counts singleton-positive queried bins |
| Selection pool | All chunk bins | Only chunk bins not in `queried` |
| Algorithm strategy | Unchanged | Unchanged |

## What did NOT change

- Thompson sampling shape/rate: `Gamma(N1_c + 0.1, 1/(n_c + 1))`
- Chunk size (120 s), bin size (10 s)
- Repair trigger and expansion logic
- Core/Halo release rules
- Budget grid and seeds
