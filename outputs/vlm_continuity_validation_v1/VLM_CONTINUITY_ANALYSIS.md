# Independent VLM Event-Continuity Analysis

## Design and completeness

Judge A was the pre-frozen cross-family `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` on all 40 blinded public cases. The original human benchmark remains untouched: `HUMAN_CONTINUITY_VALIDATION = PENDING`, zero human labels.

Raw logs and a 40-row label CSV are hash-frozen. However, only `5` rows have a frozen schema-valid/recoverable `SAME_EVENT` or `DIFFERENT_EVENTS` label. Label counts are `{'UNCERTAIN': 35, 'DIFFERENT_EVENTS': 5}`; parse status counts are `{'PARSE_FAILURE_COERCED_TO_UNCERTAIN': 35, 'LABEL_TOKEN_RECOVERED': 5}`. The majority were explicit parser failures conservatively represented as `UNCERTAIN`, not converted to boundaries.

## Method comparison

On the `5` eligible rows, C1−C0 accuracy is `0.0000` (paired bootstrap 95% CI `0.0000`, `0.0000`); K3−C1 is `0.2000` (95% CI `0.0000`, `0.6000`). These estimates do not meet the frozen minimum of 28 eligible cases and cannot support a scientific continuity conclusion.

## Decision

`VLM_CONTINUITY_DECISION = INCONCLUSIVE_VLM`.

The study is a failed-to-be-informative cross-family sanity probe, not negative semantic evidence against C1/K3. It leaves the reference-circularity risk **UNRESOLVED**, retains `REAL_HUMAN_VALIDATION = PENDING`, and forbids retuning/repeating the same cases to repair the judge output format.
