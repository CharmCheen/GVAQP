# Continuity Population Summary

Population definition: every consecutive pair of full-grid `relevant` VLM unit anchors within the same video/query. This is a hidden analysis population; it is never provided to the annotator.

- Total instances: `248`.
- Per video: `{'DALI': 81, 'HANGZHOU': 92, 'WUHAN': 75}`.
- Prediction patterns `(C0,C1,K3)`: `{'100': 149, '110': 33, '111': 66}`.
- C0/C1 disagreements: `149`.
- C1/K3 disagreements: `33`.
- All-method agreements: `66`.
- Frozen primary/reserve sizes: `40/20`.

The counts are structural/model-prediction metadata only. No human label existed when this population and samples were frozen.
