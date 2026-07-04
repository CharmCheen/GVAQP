# probe_set_v1 VLM Oracle Signal Evaluation

Reference source: `probe_set_v1_vlm_oracle_reference`.

These are VLM-oracle-relative diagnostics, not human-ground-truth metrics. Do not call them true recall or ground truth recall.

## Scope

- Labels: `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`
- Signal table: `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`
- Scored probes: 20/25, because current cheap_signal_v2 feature coverage ends at local 1200s.
- Oracle positives among scored probes: 7
- Bootstrap: 2000 percentile bootstrap resamples by probe.

## Metric Role

Primary readouts are positive-probe ranks and hit@5/hit@10. AUC and precision@k are auxiliary summaries; precision@20 is reference-only because the positive count and feature coverage cap its useful range.

## Outputs

- `probe_signal_metrics.csv`
- `probe_positive_rank_cases.csv`
- `probe_unscored_cases.csv`
- `probe_signal_scores_long.csv`

## Limitation

Representative features and ranking directions come from the pre-existing 6-event diagnostic design table. This evaluation does not use probe labels to choose features, thresholds, or selectors.
