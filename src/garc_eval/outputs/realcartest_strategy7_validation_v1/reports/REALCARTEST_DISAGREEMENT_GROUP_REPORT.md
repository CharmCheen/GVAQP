# Realcartest Disagreement Group Report

- Output timestamp: 2026-06-27T14:37:19Z
- High threshold: top 25% `object_count_mean`, implemented as >= q75=7.750000.
- Low threshold: bottom 50% `object_count_mean`, implemented as <= median=5.650000.
- Thresholds were pre-registered and not tuned using Qwen labels.
- Group construction uses cheap proxy score and GLM parsed label only.
- Qwen labels and event clusters are evaluation-only.

| group | size | Qwen positives | positive rate | enrichment | L3-missed positives B20 |
|---|---:|---:|---:|---:|---:|
| L3_high_GLM_negative | 59 | 24 | 0.406780 | 1.726650 | 21 |
| L3_low_GLM_positive_or_uncertain | 48 | 12 | 0.250000 | 1.061170 | 12 |
| object_count_low_GLM_positive_or_uncertain | 46 | 12 | 0.260870 | 1.107308 | 12 |
| GLM_positive_or_uncertain | 106 | 47 | 0.443396 | 1.882075 | 34 |
| GLM_negative | 292 | 46 | 0.157534 | 0.668683 | 43 |
