# CASQ Phase 1 Data v1 Summary

Phase 1-data ingestion scaffolding was prepared under:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_data_v1`

Key artifacts:

- `reports/PHASE1_DATA_PLAN.md`
- `reports/EVENT_COUNT_TARGET_PLAN.md`
- `reports/PHASE1_DATA_REPORT.md`
- `schema/casq_events_schema.json`
- `schema/casq_units_schema.json`
- `scripts/run_phase1_data_audit.sh`

Dataset directories and mapping READMEs were created under:

`/qiuyeqing/llama_prl/G-ARC/datasets/casq_external`

Decision:

`DATA_DECISION: READY_TO_DOWNLOAD_SMALL_SUBSET`

Recommended first subset: Nexar metadata plus 25 positive and 25 normal videos, after explicit user approval and access/license review. Existing Phase 0 pseudo-events remain debugging-only and are not clean human-truth event boundaries.
