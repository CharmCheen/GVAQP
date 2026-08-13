# P1 automated-only completion audit

## Status

`COMPLETE_AUTOMATED_ONLY_MODEL_RELATIVE_AUDIT`

All non-human automatic work is complete: the 1,475-unit Qwen3-VL-32B grid
passed integrity verification, the two frozen natural-proxy characterizations
completed, and this audit materialized outcome-blind-trace diagnostics over
both complete semantic queries and both proxy families.

## What the derived endpoints mean

- `model_relative_relevant_unit_coverage`: fraction of all Qwen/released-model
  relevant units acquired by a trace.
- `model_relative_full_C1_event_coverage`: fraction of C1 events constructed
  from the *complete same-model semantic table* touched by the trace's
  verified-positive units.

They are automated, model-relative coverage diagnostics only. They are not
human labels, an independent reference, a P1 primary endpoint, a P1 PASS/FAIL
decision, or evidence for a geometry-aware policy.

## Files

- `P1_AUTOMATED_MODEL_RELATIVE_TRACE_ENDPOINTS.csv`: all 1,008 trace-query rows.
- `P1_AUTOMATED_MODEL_RELATIVE_EQUAL_YIELD_MATCHED.csv`: deterministic
  equal-selected-positive, high-versus-low geometry contrasts.
- `P1_AUTOMATED_MODEL_RELATIVE_CLUSTER_SUMMARY.csv`: within video-query-proxy
  medians; strata are not treated as independent samples.

The accompanying JSON contains exact input/output/code hashes.
