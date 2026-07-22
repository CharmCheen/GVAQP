# PSVR Research Contract

## Objective

Recover the event relation defined by exhaustive execution of the frozen semantic oracle and the frozen deterministic reference materializer under a hard physical wall-clock deadline. The active workload is `warm_oracle_cold_proxy`: Qwen is resident, proxy evidence is not materialized, and decode, proxy, physical oracle, K3, serialization, fsync, and atomic commit all count.

## Frozen benchmark semantics

- benchmark: `cbbv2_514c0d360fd5b2a4b5fe`
- source video SHA-256: `bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610`
- oracle: Qwen3-VL-32B-Instruct, model hash `c8104bb1...`
- prompt hash: `12187489...`
- parser hash: `9a741340...`
- frame-sampling code hash: `5b038acb...`
- unitization: 347 fixed 10-second units
- exact reference: 26 events reconstructed from all 347 frozen physical oracle responses
- controlled materializer: unchanged `k3_bridge_safe`

The model, prompt, sampling, clips, parser, labels, reference events, unitization, ontology, and reference materializer semantics may not change inside this benchmark version.

## Capability boundary

Selector and scheduler policy must execute in a clean-spawn, empty-chroot, unprivileged worker. They receive only public unit metadata, scanned proxy observations, and queried oracle observations. The launcher owns the restricted `query / queried_ids / query_count` capability. Unchanged K3 receives only public units and queried evidence in its own clean-spawn boundary. Evaluation runs after execution in a separate capability boundary.

## Physical accounting

- clock: `time.perf_counter_ns()`
- GPU stages: synchronize before start and after completion
- physical, replay, and logical calls are distinct fields
- deadline admission reserves the complete action path plus an independent durable-commit path
- missing, stale, insufficient, cache-contaminated, asynchronous, or wrong-workload profiles reject by default
- failed, slow, and deadline-miss samples are retained

## Evaluation and statistics

Main endpoint: wall-clock `AnytimeAUC_F1`. Report equal-call diagnostics separately. The independent inferential unit is source-video × query; units, events, seeds, and deadlines are not independent samples. Current evidence is single-video/single-query development evidence only. Held-out remains unopened.

## Stage order

1. Deadline safety
2. Minimal physical baselines
3. Coverage mechanism
4. Event-aware verification
5. Deadline-conditioned interleaving
6. Boundary allocation
7. Combined method
8. Held-out validation
9. Paper-level synthesis

No later stage begins at scale until the preceding gate passes.
