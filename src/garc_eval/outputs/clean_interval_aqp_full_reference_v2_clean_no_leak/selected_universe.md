# Selected Mini-Universe

Experiment: `clean_interval_aqp_full_reference_v1`

Selected video segment: `realcartest` from 2000.0s to 3200.0s (20.0 minutes).

Selection basis: existing V13.8 Qwen3-VL-32B pseudo-oracle labels were used only to choose a compact
mini-universe with enough cut-in / near-conflict / abnormal interaction events and substantial negative
background. This curation step is explicitly not part of the tested retrieval method.

Reference-event count inside segment: 20

Positive center10 anchors inside segment: 32/120 (0.267)

Leakage boundary: Stage 2 cheap signals, Stage 4 proposal generation, and Stage 7 optimization do not
read full-reference labels. Reference labels are used for Stage 1 materialization, oracle replay lookup,
diagnostics, and final evaluation only.
