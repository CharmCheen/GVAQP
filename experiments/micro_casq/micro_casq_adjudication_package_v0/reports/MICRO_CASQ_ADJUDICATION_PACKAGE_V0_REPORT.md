# Micro-CASQ Adjudication Package v0 Report

## 1. Goal

Construct a metadata-preserving Micro-CASQ adjudication sample package from the existing data asset audit. This run did not label clips, infer event boundaries, run VLM, run YOLO, run embeddings, train models, or download datasets.

## 2. Protocol Reference

Protocol path read: `/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md`

## 3. Inputs

All required data asset audit inputs were present.

## 4. Candidate Pool Quality

Candidate pool rows: `488314`. See `tables/candidate_pool_quality_audit.csv` and `reports/CANDIDATE_POOL_QUALITY_AUDIT.md`.

## 5. Adjudication Sample Selection

Selected `500` proposed adjudication samples. Selected by stratum: `{'hard_negative': 220, 'likely_positive': 80, 'boundary_uncertain': 80, 'possible_false_negative': 60, 'label_disagreement': 60}`. Under-filled strata: `none`.

## 6. Sample Feasibility

Materializable samples: `153`. Feasibility statuses: `{'missing_video': 347, 'materializable': 153}`.

## 7. Pilot Review Set

Pilot samples selected: `50`. Pilot by stratum: `{'likely_positive': 18, 'label_disagreement': 18, 'possible_false_negative': 10, 'hard_negative': 4}`.

## 8. Materialized Review Artifacts

Pilot clips created or already present: `50`. Contact sheets created or already present: `50`. Reviewable pilot rows by artifact availability: `50`.

## 9. Human Review Guide

`review_package/README.md` and `reports/HUMAN_REVIEW_GUIDE.md` were created. They state that old labels, Nexar-derived labels, and VLM-derived labels are provenance only.

## 10. Pilot Adjudication Template

`review_package/micro_casq_pilot_adjudication_template.csv` was created with known metadata pre-filled and adjudication fields left blank.

## 11. Readiness for Adjudication

The package is ready for pilot adjudication if at least 40 pilot rows have usable artifacts or sufficient metadata. This run reached that threshold.

## 12. Risks and Limitations

- This is an engineering package, not a research-valid benchmark conclusion.
- Existing old labels are noisy provenance and were not promoted to gold.
- Materialization was attempted only for the 50 pilot samples.
- The candidate pool may be biased toward prior VLM, Nexar, and kinematic-proxy workflows.

## 13. Next Action

Start bounded human adjudication on the pilot package, or explicitly authorize a separate 32B adjudication pass using the blank template. If positive yield or artifact usability is low, repair the sampling plan before scaling beyond the pilot.

## 14. Final Decision

MICRO_CASQ_PACKAGE_DECISION: READY_FOR_PILOT_ADJUDICATION
