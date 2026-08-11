# ARC vs RC-SEM common-input cached replay

## Strongest supported conclusion

This experiment compares ARC and RC-SEM on identical frozen inputs, logical
VERIFY budgets, strict K3 eventization, and evaluator output schemas.  The
query-identity-complete primary domain is `dataset3_development`, bound to
prompt hash `12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33`.

RC-SEM admitted **0 probable events**.  Cross-source calibration
found a deployable 0.80 precision-floor threshold: **False**.  Therefore
any measured advantage is a VERIFY scheduling result, not evidence that safe
unverified event publication works.

## Primary query-bound result

| budget | event_precision_arc | event_precision_rcsem | event_recall_arc | event_recall_rcsem | event_f1_arc | event_f1_rcsem | delta_f1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 10 | 0.200 | 0.000 | 0.008 | 0.000 | 0.015 | 0.000 | -0.015 |
| 20 | 0.600 | 1.000 | 0.031 | 0.115 | 0.058 | 0.207 | 0.149 |
| 50 | 1.000 | 1.000 | 0.123 | 0.192 | 0.218 | 0.323 | 0.105 |
| 80 | 1.000 | 1.000 | 0.223 | 0.385 | 0.364 | 0.556 | 0.192 |
| 100 | 1.000 | 1.000 | 0.277 | 0.423 | 0.434 | 0.595 | 0.161 |

## Two-source-video sensitivity summary

| method | event_precision_auc | event_recall_auc | event_f1_auc | tiou_03_auc | tiou_05_auc |
| --- | --- | --- | --- | --- | --- |
| ARC-CACHED-REPLAY-v1 | 0.645 | 0.192 | 0.262 | 0.053 | 0.036 |
| RC-SEM-CACHED-COMMON-v1 | 0.857 | 0.381 | 0.483 | 0.136 | 0.115 |

The macro treats the two `realcartest` slices as one source video before
averaging with `dataset3`; five repeated RC-SEM seeds are deterministic pairing
rows, not five independent samples.

## Evidence boundaries

- ARC rows were copied byte-for-byte from its independently validated cached
  replay; 180 original rows and 640 artifact hashes were independently
  rechecked before this comparison.
- Both methods read the same `units.csv`, `proxy_only.csv`, `oracle_labels.csv`,
  and `reference_events.csv`; RC-SEM target ordering is computed before the
  held-out source-video oracle is revealed.
- `dataset3_development` has complete model/prompt/parser binding.  The two
  `realcartest` derivatives lack prompt and parser hashes, so their results are
  sensitivity evidence only.
- This is an exploratory, open-benchmark cached replay.  It is neither a
  prospective comparison nor a physical hard-deadline experiment.
- The physical ARC/RC-SEM smoke remains blocked by non-deployable calibration,
  missing immutable model/proxy bytes, stale deadline profiles, and unavailable
  compatible GPUs.  No physical claim follows from this replay.

## Interpretation and rejection trigger

The decisive question is whether RC-SEM's scheduling advantage survives a
shared physical runtime with a deployable event posterior.  Reject a general
RC-SEM advantage if that paired run loses at equal wall-clock budget, if a
held-out source video reverses the gain, or if probable-event precision fails
the frozen 0.80 lower-confidence-bound gate.
