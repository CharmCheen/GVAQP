# Micro-CASQ Adjudication Plan

This plan does not run VLM or human review. It defines how to sample from the existing candidate mining pool for a first bounded adjudication pass.

## Target Benchmark Size

- Confirmed positive events: 50-100
- Confirmed negative windows: 200-300
- Ambiguous / abstain: retained for analysis but excluded from main recall metrics
- Videos: as many unique videos as possible
- Boundary rule: only `boundary_status=ok` positive events enter event-IoU recall metrics

This is a first Micro-CASQ adjudicated benchmark, not the final full paper benchmark.

## Current Pool

- Candidate pool rows: 488314
- Recommended-for-adjudication rows: 820

## Sampling Strata

| stratum_name | target_sample_count | selection_rule | risk | expected_use |
| --- | --- | --- | --- | --- |
| likely_positive | 80 | Sample unique videos first from recommended pool rows with old positive/conservative_positive/human-positive labels; avoid duplicate clips from the same source  | Old VLM positives are not human truth and may be scene-biased. | Positive adjudication candidates; positives with boundary_status=ok can enter event-IoU recall evaluation. |
| label_disagreement | 60 | Prioritize rows where external_label=positive and conservative_positive=no, or where human audit overrode VLM positive. | May overrepresent known failure patterns from one audit. | Boundary/mapping stress test; many rows may become negative or abstain. |
| possible_false_negative | 60 | Select old negative/external-negative windows with positive VLM evidence or high existing proxy/candidate score columns; do not generate new scores. | Existing score provenance may be diagnostic and not comparable across runs. | Candidate mining and false-negative audit. |
| hard_negative | 220 | Sample negatives across negative_reason/event_type values and videos; include old human-confirmed negatives where available. | Negative reason taxonomy differs across old outputs and may need normalization. | Heldout negative windows and precision/error analysis. |
| boundary_uncertain | 80 | Sample derived/pseudo/uncertain boundary rows, especially Nexar near-label windows and Phase 0 pseudo-events. | Many rows may be excluded from headline recall if boundary_status is not ok. | Boundary-quality audit and exclusion accounting. |
