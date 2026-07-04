# Envelope Definitions

- `E0_threshold_merge`: threshold/merge proposal family, or all candidates if unavailable.
- `E1_top_score_envelope`: active-score top candidates with temporal NMS.
- `E2_dense_lattice_upper`: diagnostic oracle-like lattice upper; uses labels and is not a deployable method.
- `E3_craq_stratified_repair`: high-score initial envelope plus outside-stratum diagnostic repair replay.

Budgets are candidate-count budgets `[20, 50, 100, 200, 400]`. Duration budgets are reported via total selected duration rather than enforced.
