# Input Artifact Audit

Strict benchmark `cbbv2_514c0d360fd5b2a4b5fe` is frozen and read-only. Inputs contain 347 units, 1735 proxy rows across 5 public proxy fields, 39 VLM-defined positive units, and 26 VLM-defined pseudo-events from one diagnostic video.

The failed BCM uses `config/`, not the requested `configs/`. It has no `analysis/` directory and did not preserve all-candidate scores. The exact H0 candidate-score reconstruction from Hypothesis Repair v1 is resolved explicitly and remains evaluator-only. No stale artifact was silently substituted.

Leakage boundary: public construction features are physically separate from oracle/reference tables. Oracle labels and reference IDs are used only in files named `EVALUATOR_ONLY` or aggregate diagnostics; no online trace or frozen ordering is changed.
