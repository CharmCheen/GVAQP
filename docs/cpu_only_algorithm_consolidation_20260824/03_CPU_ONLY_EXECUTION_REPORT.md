# CPU-Only Execution Report

Date: 2026-08-24

## 1. Scope

This execution completed only deterministic CPU work. It did not invoke a VLM/LLM, use a GPU, train a model, tune a controller, or modify source observations.

## 2. Implemented artifacts

- `src/garc/datb_sv.py`: unified deterministic replay runner.
- `scripts/run_datb_sv_cpu_replay.py`: single-command CPU replay entry point.
- `tests/test_datb_sv.py`: unit tests for scheduling, admission, durability, deduplication, and oracle-source invariance.
- `src/garc/__init__.py`: public exports.

## 3. Test execution

The authorized CPU suite executed:

```text
python3 -m unittest \
  tests/test_datb_sv.py \
  tests/test_deadline_admission.py \
  tests/test_frontier_contract.py \
  tests/scan_scheduler/test_safe_coverage.py
```

Observed result:

```text
Ran 6 tests
OK
```

The six DATB-SV tests cover:

1. deterministic breadth-first bisection order;
2. fixed SCAN/VERIFY alternation and event deduplication;
3. commit-reserve admission and safe fallback;
4. post-deadline immutability;
5. trace invariance to oracle-source metadata;
6. cost-bound violation handling.

## 4. Synthetic end-to-end replay

A synthetic replay manifest was processed through the command-line entry point.

Observed result:

```text
status: DATB_SV_CPU_INTEGRATION_PASS
durable_actions: 10
scan_actions: 6
verify_actions: 4
distinct_utility: 3
stop_reason: NO_COMPLETE_ACTION_FITS
new_inference: false
training: false
```

This result validates pipeline mechanics only. It is not scientific evidence of performance.

## 5. What is and is not ready

| Layer | Status | Meaning |
|---|---|---|
| Scheduler contract | PASS | Deterministic SCAN/VERIFY policy is executable |
| Deadline admission | PASS | Unsafe work is not admitted under declared bounds |
| Durable commit | PASS | Only pre-deadline committed events count |
| Oracle decoupling | PASS at interface level | Oracle identity is not used for action selection |
| Synthetic integration | PASS | Manifest-to-results path works |
| Real cached workload replay | BLOCKED | Compatible exposure/cost/oracle manifest not yet bound |
| Physical wall-clock comparison | `BLOCKED_BY_NON_CPU_REQUIREMENT` | Existing scan and Qwen timings are not pairable |
| Generalization claim | NOT IDENTIFIABLE | Only two production queries exist |
| Human utility claim | DEFERRED | Independent annotations are not available |

## 6. Reproducible command

```bash
python scripts/run_datb_sv_cpu_replay.py \
  --replay <compatible_cached_manifest.json> \
  --deadline <seconds> \
  --scan-upper <seconds> \
  --verify-upper <seconds> \
  --commit-reserve <seconds> \
  --output-dir <output-directory>
```

The command must not be run on a fabricated adapter. Missing provenance or incompatible cost semantics is a valid blocked outcome.

## 7. CPU-only next action

Recover or formally retire the missing endogenous scan preflight provenance. This is a bounded file/provenance audit and requires no GPU. It determines whether a real cached replay can be run without changing the workload definition.
