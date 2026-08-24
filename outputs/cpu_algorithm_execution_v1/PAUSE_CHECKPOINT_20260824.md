# CPU Execution Pause Checkpoint

## Pause status

`PAUSED_BY_USER_LOW_BATTERY`

The active T2-C1 replay was interrupted with exit code 130 after 255.41 seconds.
No GPU, model inference, training, deletion, overwrite, or canonical state update
was performed.

## Frozen completed results

- T0 provenance: `RETIRED_FOR_CLAIM_USE`.
- T0.5 historical evaluator: `EVALUATOR_PARITY_UNRESOLVED`.
- M0 shared causal executor: 15 focused CPU tests passed.
- H2 V1: `FAIL_SYNTHETIC_MECHANISM_SCREEN_ONLY`.
- H2 V2: `FAIL_SYNTHETIC_MECHANISM_V2_ONLY`.
- H2 V3 holdout: `FAIL_SYNTHETIC_COUPLING_MECHANISM_ONLY`.
- ExSample-EndToEnd-Adapted killer: `PASS_SYNTHETIC_EXSAMPLE_KILLER`.

## Invalid/incomplete output

`outputs/t2_c1_existing_corpus_replay_v1_retry1/` belongs to the interrupted run
and must not be treated as a result or reused as an output destination.

## Sole resume action

When power is stable, run:

```bash
PYTHONPATH=src:scripts python3 scripts/run_t2_c1_existing_corpus_replay.py \
  --proxy-root outputs/v3_scan_proxy_preregistration_v1/frozen_raw \
  --outcomes docs/cpu_only_event_utility_freeze_20260823/frozen_cached_semantic_outcomes.csv \
  --output outputs/t2_c1_existing_corpus_replay_v1_retry2
```

Do not change policies, seeds, costs, deadline levels, tail-unit exclusion,
failure handling, or ExSample envelope before resuming.

