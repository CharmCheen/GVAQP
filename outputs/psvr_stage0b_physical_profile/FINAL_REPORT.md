# PSVR Stage 0B — Re-frozen Physical Workload Regimes

`COLD_PROCESS_COLD_PROXY_REGIME = NO_GO`

`WARM_ORACLE_COLD_PROXY_REGIME = GO`

## Replication

- coarse scan: n=10
- full proxy: n=10
- independent oracle cold initialization processes: n=5
- valid physical VERIFY: n=20; cache replay used for latency: 0
- paired K3 + snapshot: n=50

## Regime B — warm oracle, cold/unmaterialized proxy

Coarse and full-proxy repetitions in this gate were measured with the physical Qwen3-VL-32B checkpoint resident on the same GPU.

- T_min_B = 29.830 s
- T_max_B = 123.952 s
- interval_width_B = 94.123 s
- normalized_interval_width_B = 0.7593

## Regime A — cold process, cold/unmaterialized proxy

- Serial T_min_A = 208.256 s
- T_max_A = 123.001 s
- serial interval width = -85.255 s
- true same-A800 parallel trace status = ok; end-to-end = 255.787950262 s

Regime C is reported separately as oracle-resident and proxy-materialized; it is not used to support a partial-proxy claim. All latency observations are physical; frozen response replay is excluded.
