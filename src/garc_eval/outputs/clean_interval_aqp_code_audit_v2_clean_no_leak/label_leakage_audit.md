# Label Leakage Audit

Verdict: **PASS**

Forbidden/reference-derived fields present in `interval_lattice_features_only.csv`:

```text
none
```

Static pipeline term inventory:

| term | count |
| --- | --- |
| reference_events.csv | 9 |
| full_reference_units.csv | 3 |
| interval_labels_v2_clean.csv | 9 |
| features_only | 6 |
| oracle_samples | 5 |
| calibrate | 8 |

Conclusion: the features-only artifact is label-free under the audited forbidden/reference-derived field inventory.
