# Round 2 Phase A/B Artifact Registration

UTC: 2026-07-02T04:43:56Z

## Main Goal

Register Phase A/B artifacts and review findings from existing outputs.

## Inputs Read

- `PROJECT_STATE.md`
- `TASK_QUEUE.yaml`
- `EXPERIMENT_REGISTRY.csv`
- `DECISIONS.md`
- `CLAIMS_LEDGER.md`
- `FAILURES.md`
- `HANDOFF.md`
- `outputs/FINAL_REVIEW.md`

## Registered Artifacts

| artifact | status | notes |
| --- | --- | --- |
| `outputs/probe_set_v1/` | complete, needs annotation | 25 probes, 25 clips, 25 centers, 25 sheets |
| `outputs/cheap_signal_v2/` | complete, diagnostic-only | metrics only on `6_event_reference` |
| `outputs/FINAL_REVIEW.md` | complete | no FAIL; multiple WARNING items |
| `src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py` | complete source artifact | no model inference imports found in prior review |

## Claim Boundary

The strongest supported claim remains:

> On `6_event_reference` within the existing top `p_answer` bin, new diagnostic
> signal families show stronger within-bin TP/FP separation than reviewed existing
> signals.

This does not support full-video recall/precision, expanded-reference metrics,
probe-set metrics, formal guarantees, or selector replacement.

## Decision

`T001_COMPLETE`

