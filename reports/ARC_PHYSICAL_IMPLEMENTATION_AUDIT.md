# ARC-UNIT-INSPIRED-PHYS-v1 implementation audit

Date: 2026-07-30 UTC

## Outcome

The ARC policy and its shared physical-runtime integration are implemented and
CPU-validated. The paired physical smoke is **not executed**. Its fail-closed
preflight rejects the only discovered calibration artifact before importing a
GPU framework, loading a model, or opening a video:

`UNSUPPORTED_ONE_POSITIVE_NOT_DEPLOYABLE`

Three independent execution blockers also remain: the current host has no GPU
compatible with the frozen A800 deadline profiles, every visible A100 was busy
at inspection, and the exact frozen Y8 and Qwen model bytes are absent from the
read-only source repository. Consequently there are no new ARC-versus-current
physical numbers, and `outputs/arc_unit_inspired_phys_v1/` was deliberately not
created. This is an implementation result, not a physical performance result.

The completed `ARC-CACHED-REPLAY-v1` experiment was not rerun or tuned. Its
whole-tree hash remains
`05d63af1f7daced4979191214c3bf0e237ae02f083cbc1523ac1069456cd42d2`;
`ARTIFACT_HASHES.csv` remains
`40d2de05e72b74f004d981e8b2be830725ac4f434a09affbd9f67ea34d537ec2`
and `RUN_MANIFEST.json` remains
`c59c84448095b7f320c312d21e241177752aa97646bd83060f67371a8436564e`.

## Current-method selection

There are two meanings of “latest” in the repository, and treating them as the
same would produce an invalid comparison.

1. The newest directory explicitly named `accelerated_event_query_v1` is the
   July-29 model-relative oracle work. Its own completion audit says the full
   SCAN/VERIFY loop, operational reference, proxy join, cost calibration,
   deadline safety, replay/controller, baselines, and event-query evaluation
   are missing. The newer full-grid runner is an oracle-label construction
   runner, not a current event-query method. It therefore cannot be used as a
   comparator. Evidence:
   `outputs/accelerated_event_query_v1/reports/COMPLETION_AUDIT_2026-07-29.md`
   (SHA-256 `e9f7e0c851c52bb00608b7e2cfc82c8545ff31e87f3144f77146a3ff062cd93a`).
2. The latest **executable accelerated policy on a complete shared physical
   event-query contract** is H-STAGE1, method `ST1`, run by
   `scripts/run_psvr_stage1_physical.py` (SHA-256
   `d22ecf781f26206dce349d1a53d0596c96a7a8df85ee6a4730401ebae8d456e1`).
   It wraps `scripts/run_psvr_two_video_physical.py`. ST1 freezes S1 max-gap
   coverage recovery, `cell_diverse_conservative` VERIFY, and the
   `stage_conditioned_v1` controller.

ST1 is selected because it is the newest runnable policy, not because it had a
good outcome. Its frozen decision is
`REJECT_NO_CROSS_VIDEO_QUALITY_SIGNAL`; the repository reports no validated
current core method. The comparison, if unblocked, must therefore be described
as ARC versus the latest executable but rejected current configuration—not as
ARC versus an accepted state of the art.

For context only, the historical ST1 matrix reported macro AnytimeAUC-F1
`0.0475467284`, deadline F1 `0.0733333333`, precision `0.5`, recall
`0.0395962733`, and `0.75` unique confirmed events. Those values used the old
run clock/profile environment and are **not** paired results for this new
physical contract. ARC has no corresponding physical values.

## Frozen shared task and runtime contract

The machine-resolved contract hash is
`b53a4de69875eddce59d1366f349b4c160eb828eaf4bcaf6eafe77ca511af5ea`.
The audit command is shown below.

| Component | Shared identity |
|---|---|
| Benchmark | `psvr2v_6250e3124206dccec5a3` |
| Tasks | `V0_Q1`, `V0_Q2`, `V1_Q1`, `V1_Q2` |
| Registered paired smoke | `V0_Q1`, `T_transition`, replicate 0, Y8 |
| V0 | 347 frozen units; SHA-256 `bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610` |
| V1 | 567 frozen units; SHA-256 `64cb0cfac6c37e52045552b4ed24e8aa20fd2c1fddc22509cf33dd957d14fd09` |
| Queries | Q1 `OTHER_VEHICLE_ENTERS_EGO_PATH`; Q2 `VRU_ENTERS_EGO_PATH` |
| Query protocol | `5705a1365e6033445932c06f4aa2432ff6bdcdfcb813ee822dfad39da3ae25c0` |
| Proxy | frozen Y8/YOLOv8n, 640, 5 fps; config hash `2c3026fcffcab75fa7a1024e8a929b6eec339b7cbeec4ece9827bcb7e811035d` |
| VERIFY | cache-free Qwen3-VL-32B generic prompt and frozen Q1/Q2 projection, fresh logical ledger per run |
| Oracle model identity | `c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210` |
| K3 | `k3_bridge_safe`, `g_max=1`, `d_core_max=40`, `d_seg_max=60` |
| K3/materializer hash | `0a7a8ad4a13cc4404b0cfe7dfb1aef8958197267e22ff1df545ac4dbbf744610` |
| Durable commit | shared `materialize_and_commit` plus `durable_json`: serialize, file fsync, atomic replace, directory fsync |
| Action provenance | shared fsynced, hash-chained `ActionLedger` |
| Deadline admission | shared `TailAwareDeadlineGuard`, action plus durable-commit tail reservation |
| Evaluator | `scripts/evaluate_psvr_two_video_physical.py`, SHA-256 `de291f2a8ee706cf8dfdc3edb1436d8b60d094bf316822bb7cfb9a84060af5b7` |

The unit grid uses contiguous 10-second records with frozen terminal source
exceptions: V0 unit 346 is 5.0 seconds and V1 unit 566 is 5.535333 seconds.
These immutable tails are not padded or retuned. ARC uses `tau=1` unit.

The frozen deadline grid is:

| Task | T_transition | T_high |
|---|---:|---:|
| V0_Q1 | 122.2528144965554 s | 123.9524739725 s |
| V0_Q2 | 122.2528144965554 s | 123.9524739725 s |
| V1_Q1 | 199.19407308333996 s | 202.7927274621175 s |
| V1_Q2 | 199.19407308333996 s | 202.7927274621175 s |

The smoke cell was fixed as the first canonical task/deadline/replicate before
physical outcomes were available. No test-set sweep was performed.

## Shared-runtime integration map

| Physical stage | ARC | ST1 current method | Shared implementation/accounting |
|---|---|---|---|
| Clock start | Before materializer, policy/oracle service, and model initialization | Same external start injected into the base runner | `time.perf_counter_ns` |
| Initial result | Empty K3 EventRelation committed before expensive model loading | Same | `materialize_and_commit`, `durable_json` |
| Video/proxy | Chronological exhaustive Y8 pass over every unit | Frozen S1 max-gap online scan | Same `UnitProxyEngine`, decoder, detector, tracker, scoring code |
| Probability input | Complete-pass score transformed by a deployable frozen calibrator to `p`; ARC receives `[1-p,p]` | Uses its frozen observed proxy frontier | Calibration gate is before GPU/video access |
| Temporal grouping | Fixed sequential Jensen-Shannon distance threshold `0.001` | Not applicable | Existing parity-tested ARC selector |
| Scheduling | ARC progressive sampling/propagation after the complete pass only | Frozen ST1 stage-conditioned controller | Policy sees no references or future labels |
| VERIFY | One explicit unique selected unit at a time | Same | Same physical `OracleAccessor`, prompt, parser, projection, no cache |
| Indeterminate result | Preserved as parse failure/abstain/unusable; never made negative or propagated | Frozen parser result | Raw result remains durable |
| EventRelation | Only explicit determinate physical VERIFY rows; propagated labels are diagnostics only | Explicit physical VERIFY rows | Same K3 materializer |
| Checkpoint | Initial and after every legal SCAN/VERIFY | Same | Same durable snapshot path |
| Admission | Full VERIFY plus commit reservation after ARC controller time | Same guard after current controller time | Same task-matched profiles |
| Finalization | CUDA synchronization charged; last durable snapshot is immutable | Same paired-mode final synchronization | Same outer clock |
| Evaluation | After both services stop | After both services stop | Same frozen evaluator instance/hash |

If ARC cannot finish all proxy units plus complete scoring by the deadline, it
does not construct or call the selector. The last already durable confirmed
EventRelation is returned; normally this is the initial empty relation. The
controller never receives a reference event, stored oracle labels, ST1
selections, or unobserved proxy evidence.

## Implementation changes

- Added `src/garc_eval/arc_physical/calibration.py`: a deployable-calibrator
  schema, monotone query-specific piecewise-linear mapping, and fail-closed
  rejection of exploratory artifacts. The identity calibrator is explicitly
  test-only and cannot be mistaken for a physical artifact.
- Added `src/garc_eval/arc_physical/policy.py`: complete-pass state boundary,
  calibrated Bernoulli vectors, fixed Jensen-Shannon clustering, `tau=1`,
  duplicate prevention, indeterminate outcomes, and separation of propagated
  scheduling labels from comparable EventRelation evidence.
- Added `src/garc_eval/arc_physical/runtime.py`: monotonic deadline loop,
  scan-plus-commit reservation, full-pass gate, controller/VERIFY/K3 commits,
  immutable last snapshot, final synchronization, and injected capabilities
  for CPU tests and the real runtime.
- Added `src/garc_eval/arc_physical/contract.py`: hash-bound task, current
  runner, proxy, deadlines, K3, durable runtime, and evaluator audit.
- Added `scripts/run_arc_physical_smoke.py`: the two-leg preregistered smoke,
  physical-input resolution by frozen hash, shared services, shared evaluator,
  pair checks, and refusal to overwrite an existing physical output root.
- Minimally extended `scripts/run_psvr_two_video_physical.py` for paired-mode
  use: an externally started clock, immutable input-path remapping, injected
  pre-model initial checkpoint/ledger, and charged final CUDA synchronization.
  All arguments default to the legacy behavior, so frozen historical outputs
  are not rewritten.
- Added `tests/arc_physical/test_arc_physical.py`.

Final implementation hashes include:

- paired runner: `7bd09f9669c6ac54a790c8fb38fbeef759dd60f421994496b4f54ce54eb95d60`
- shared base runner with integration seam: `2e7fddcbaf95027a47625538609bd5230ff074d43d1f0a48bb0b40d70bb418a7`
- ARC calibration/policy/runtime:
  `5c373c7da91c1c3de32d1624552ac165235abe93e08791389248b45d88b41e84`,
  `cacde8c2eb366f0e162129500129b807d30e434f65245ccbe724ca0993693943`,
  `d75da267b2ed90527fec7f00d9c996734d569c923cd502f67bc45b00e47dd1a8`

Vendored/historical ARC code, frozen prompts, parsers, labels, references,
parameters, evaluator, and all cached-replay outputs were left unchanged.

## CPU validation

Final commands:

```bash
python -m py_compile src/garc_eval/arc_physical/*.py scripts/run_arc_physical_smoke.py scripts/run_psvr_two_video_physical.py
python -m pytest -q tests/psvr_runtime tests/arc_physical tests/arc_cached_replay
python scripts/run_arc_physical_smoke.py audit-contract
git diff --check
sha256sum /root/charm/GVAQP/data/realcam/wuhan.mp4 /root/charm/GVAQP/data/realcam/dali.mp4
```

Results:

- pytest: **114 passed, 0 failed, 0 skipped** in the final run.
- Python compilation: pass.
- contract audit: pass; it resolved ST1 to S1 / cell-diverse conservative /
  stage-conditioned v1 on `V0_Q1`, T_transition, replicate 0, with the frozen
  current target of three scans and one VERIFY opportunity.
- whitespace/error check: pass.
- both source-video bytes match their frozen SHA-256 identities.
- `ruff` and `mypy` executables were not available; no lint/type result is
  claimed.

The tests cover deployable-calibrator gating, exact `[1-p,p]` construction,
fixed clustering and tau, complete-pass-before-refinement, incomplete-pass
empty snapshot behavior, oracle causality, no reference API, duplicate query
prevention, indeterminate parser semantics, propagated-positive exclusion,
determinism, shared task/K3/deadline/evaluator identity, historical ARC parity,
identical K3 output for identical traces, durable runner boundaries, and tail
deadline admission.

## Physical preflight and GPU inspection

Exact attempted smoke command:

```bash
python scripts/run_arc_physical_smoke.py paired-smoke --calibrator-manifest outputs/mf_psvr_publication_program/cycle_01_training_pool/stage_a/modeling/STAGE_A_MODEL_READINESS_DECISION.json
```

It exited 1 at the calibration gate with
`UNSUPPORTED_ONE_POSITIVE_NOT_DEPLOYABLE`. This is an expected safety failure,
not a passed smoke. Because the gate precedes output allocation, no partial
physical output directory was created and neither physical leg started.

After CPU validation, GPU state was inspected read-only with:

```bash
nvidia-smi --query-gpu=index,name,uuid,memory.total,memory.used,memory.free,utilization.gpu,compute_mode --format=csv,noheader
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory --format=csv,noheader
```

All eight visible devices were A100-SXM4-80GB devices at 91–100% utilization,
with existing compute contexts. No process was killed or changed. More
fundamentally, the frozen action/commit profile requires
`NVIDIA A800-SXM4-80GB, GPU-dd328315-ff82-8c7d-4cba-f9800a92560a,
580.65.06`; the visible A100/driver-535 environment is not compatible. The
profiles are also stale under their frozen 86,400-second maximum-age rule; the
guard returns `profile_invalid` and enumerates all V0_Q1 observations as stale.

## Required model inputs and blockers

The paired run requires all of the following without substitution:

- an independently supported, frozen, deployable Q1/Q2 unit-probability
  calibrator bound to Y8 config hash
  `2c3026fcffcab75fa7a1024e8a929b6eec339b7cbeec4ece9827bcb7e811035d`;
- YOLOv8n checkpoint hash
  `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`;
- exact Qwen3-VL-32B-Instruct content identity
  `c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210`;
- a hardware-compatible, current, independently frozen action/commit latency
  profile and idle compatible GPU resources.

Observed blockers:

1. The only discovered final calibrator has one positive among 28 calibration
   rows (Q1=1, Q2=0) and explicitly says `deployable=false` and
   `NOT_READY_FOR_PHYSICAL_PILOT`. Using raw empirical percentiles as
   probabilities would violate the ARC contract, so the implementation refuses
   it.
2. `/root/charm/GVAQP` contains the exact videos under immutable renamed paths,
   but does not contain the frozen Y8 checkpoint path or exact 14-shard
   Qwen3-VL-32B-Instruct directory. Its available seven-shard 32B FP8 model is a
   different identity and cannot be substituted.
3. The frozen deadline profiles bind a different A800/driver identity and are
   stale. Reprofiling on A100 would create a new physical contract; it cannot
   be silently done in this task.
4. No visible GPU was free at the required inspection point.
5. The newest repository line named accelerated-event-query still lacks an
   executable current SCAN/VERIFY method. ST1 is only the latest compatible
   executable policy and is itself a rejected descriptive configuration.

These are genuine immutable/scientific and resource blockers. Changing the
calibration map, using the available FP8 model, substituting hardware, or
refreshing/tuning profiles after seeing outcomes would invalidate the requested
comparison.

## Expected physical output schema

Only a successful, fully preflighted invocation may create:

```text
outputs/arc_unit_inspired_phys_v1/
  SHARED_CONTRACT.json
  arc/raw/<run>/attempt_001/
    started.json
    ACTION_LEDGER.jsonl
    checkpoint_000_snapshot.json
    scan_NNN_proxy.json
    COMPLETE_PROXY_SCORES.json        # only after all units
    query_NNN_oracle.json
    checkpoint_NNN_snapshot.json
    complete.json | failed.json
  arc/tables/
    RUN_METRICS.csv
    MECHANISM_CURVES.csv
    ... shared evaluator aggregates ...
  current/raw/<run>/attempt_001/
    ... identical current-runner durable schema ...
  current/tables/
    ... same evaluator outputs ...
  PAIRED_SMOKE_METRICS.json
  PAIRED_SMOKE_CHECKS.json
```

`PAIRED_SMOKE_CHECKS.json` gates task/deadline equality, zero reference
visibility, zero duplicates, existing durable snapshots, and identical
evaluator identity. A full matrix is not exposed or launched by this runner.

## Final status

- Policy/runtime implementation: complete and CPU-validated.
- Expected physical runs: 2 (one ARC, one ST1 on the same smoke cell).
- Completed physical runs: 0.
- Paired ARC-versus-ST1 metrics: unavailable; no scientifically valid win,
  tie, or loss can be reported.
- Full matrix: not launched, as required.
- Original repository: tracked state unchanged; its seven pre-existing
  untracked full-grid directories remain untouched.
- Cached replay: unchanged and still a cached algorithmic replay, not a
  physical result.

The next scientifically valid action is not to force the smoke. It is to
provide a provenance-complete deployable calibrator and the exact frozen model
bytes, then establish a compatible current hardware/profile contract before
rerunning the same preregistered pair.
