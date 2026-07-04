# Label Leakage Audit

Verdict: **BLOCKER**

Forbidden/reference-derived fields present in `interval_lattice_features_only.csv`:

```text
any_overlap, best_iou, center_hit, duration_inflation, event_overlap_ratio, interval_purity
```

Static pipeline term inventory:

| term | count |
| --- | --- |
| reference_events.csv | 9 |
| full_reference_units.csv | 3 |
| interval_labels_v2.csv | 9 |
| features_only | 6 |
| oracle_samples | 5 |
| calibrate | 8 |

Conclusion: the features-only artifact is not actually label-free because it includes reference-derived metric fields. Even if CILS does not intentionally use every leaked field, this violates the v2 trust boundary and makes the optimization input unsafe.
