# Data Asset Inventory

## Protocol

- Requested protocol path: `docs/clip_aqp/CASQ_CODEX_BRIEF_V12_1.md`
- Actual protocol path read: `CASQ_CODEX_BRIEF_V12_1.md`
- Note: User-specified docs/clip_aqp/CASQ_CODEX_BRIEF_V12_1.md was missing; root CASQ_CODEX_BRIEF_V12_1.md was read as the available V12.1 protocol.

## Role Definitions

1. `debug_pipeline_data`: data useful for testing frame extraction, candidate generation, table schema, and scripts.
2. `noisy_external_label_data`: data whose labels come from an external source such as Nexar alert/collision metadata and are not equivalent to `O_enter_ego_path_v0` unless audited.
3. `candidate_mining_pool`: clips/windows/videos useful for finding possible `O_enter_ego_path_v0` events, but not treated as ground truth.
4. `adjudication_pool`: selected clips/windows that should be reviewed by bounded 32B VLM and/or human adjudication.
5. `gold_eval_candidate`: data that already has sufficiently clear labels and event boundaries to potentially enter a Micro-CASQ benchmark after verification.
6. `not_currently_usable`: files/data lacking video path, timing, label semantics, or recoverable provenance.

## Discovery Summary

- Discovered assets: 1268
- By file type: {'directory': 190, 'md': 699, 'csv': 377, 'tar.gz': 1, 'missing': 1}
- By primary role: {'debug_pipeline_data': 231, 'not_currently_usable': 577, 'candidate_mining_pool': 357, 'noisy_external_label_data': 94, 'gold_eval_candidate': 9}

## Strict Interpretation

Nexar-derived labels are treated as `LOOSE_APPROXIMATION / AUDIT_UNRELIABLE`.
Old VLM labels are oracle/pseudo-oracle evidence for mining only, not human truth.
Human-audited subsets are possible gold candidates only after schema, video-path, timing, and boundary verification.

## Inventory Sample

| file_path | file_type | row_count | likely_label_source | likely_boundary_source | short_notes |
| --- | --- | --- | --- | --- | --- |
| .agents/skills/aqp-event-budget-loop | directory |  | unknown_or_mixed | missing_or_unknown | directory children=3; no recursive byte scan |
| .agents/skills/aqp-event-budget-loop/SKILL.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| .agents/skills/aqp-event-budget-loop/references/metric_definitions.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| .pytest_cache/README.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| AGENTS.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| CASQ_CODEX_BRIEF_V12_1.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| G-ARC_Research_Report.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| GARC_EVAL_BUILD_PLAN.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| datasets/casq_external/dada2000/README_CASQ_MAPPING.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| datasets/casq_external/dota/README_CASQ_MAPPING.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| datasets/casq_external/micro_casq_v0/README_CASQ_MAPPING.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| datasets/casq_external/micro_casq_v0/micro_casq_events_template.csv | csv | 0 | unknown_or_mixed | event_boundary_columns_present_source_unclear |  |
| datasets/casq_external/nexar | directory |  | external_nexar_metadata | missing_or_unknown | directory children=8; no recursive byte scan |
| datasets/casq_external/nexar/README_CASQ_MAPPING.md | md |  | external_nexar_metadata | missing_or_unknown |  |
| datasets/casq_external/nexar/videos_hf | directory |  | external_nexar_metadata | missing_or_unknown | directory children=2; no recursive byte scan |
| docs/clip_aqp | directory |  | unknown_or_mixed | missing_or_unknown | directory children=1; no recursive byte scan |
| docs/clip_aqp/CASQ_CODEX_BRIEF_V11.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/README_supg_repro.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/abae_bdd100k_count_coverage/report.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/abae_bdd100k_smoke/report.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/abae_paper_synthetic_reproduction/report.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/abae_reproduction_status.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/abae_synthetic_smoke/report.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/abae_temporal_stress/abae_temporal_assumption_stress.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/abae_temporal_stress/phase1_temporal_redundancy.csv | csv | 10 | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/adaptive_oracle_allocation/adaptive_oracle_allocation_study.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/bdd100k_formal_100trials/report.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/bdd100k_formal_100trials/summary.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/bdd100k_smoke/report.md | md |  | unknown_or_mixed | missing_or_unknown |  |
| garc_eval/outputs/bdd100k_smoke/supg_results/summary.md | md |  | unknown_or_mixed | missing_or_unknown |  |

_Showing 30 of 1268 rows._
