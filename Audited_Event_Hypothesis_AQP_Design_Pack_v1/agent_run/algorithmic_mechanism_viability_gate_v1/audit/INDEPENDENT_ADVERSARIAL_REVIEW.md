# Independent Adversarial Review

## Verdict

The initial `EVENT_SATURATION_ONLY_GO` classification was rejected. The evidence supports `IDEAL_SIGNAL_ONLY` under the preregistered mutually exclusive definitions.

## Decisive evidence

- Synthetic hypotheses are assigned directly from hidden true-event intervals before controlled fragmentation and false-hypothesis injection; they are oracle-aligned by construction.
- S1 is explicitly evaluator-derived and event-aligned. Its mean P1−P0 event-F1 AUC effect is positive (`+0.025434`).
- S2 uses frozen H1 public hypotheses, the only tested non-oracle-aligned representation. P1−P0 is negative in all 15 S2 cells (mean `-0.003978`); at AUROC 0.95 all three recall cells are significantly negative.
- Therefore saturation gains require oracle/event-aligned hypotheses, matching the `IDEAL_SIGNAL_ONLY` clause.

## Other decisions

- `REAL_CHEAP_PRIMITIVE_ENGINEERING_JUSTIFIED = false` is supported by the failed transfer to S2 and the inactive Suite B `merge_ambiguity` manipulation.
- `IMPLEMENTATION_CALIBRATION_GAP = false` is supported: the moderate synthetic calibration effect is `-0.000045`, synthetic cell magnitudes remain below `0.0018`, and semi-synthetic effects are small/null (maximum about `0.0032`).
- Exploration is not a robust alternative: it is strongly negative in synthetic and S1 evidence despite a small positive S2 mean.
- Independent seal verification passed config, test, physical-call, required-output, full-completion, file-manifest, and sentinel checks.

## Required correction

Replace `EVENT_SATURATION_ONLY_GO` with `IDEAL_SIGNAL_ONLY`. Retain the recommendation to stop planner/cheap-primitive engineering and continue only the EventRelation + BB-EM/operator representation route.
