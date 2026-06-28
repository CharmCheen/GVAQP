# Clip AQP Data Asset Audit v1 Summary

- Output directory: `test_vlm/outputs/clip_aqp_data_asset_audit_v1`
- Protocol read: `CASQ_CODEX_BRIEF_V12_1.md`
- Discovered assets: 1268
- Role counts: {'debug_pipeline_data': 231, 'not_currently_usable': 577, 'candidate_mining_pool': 357, 'noisy_external_label_data': 94, 'gold_eval_candidate': 9}
- Candidate pool size: 488314
- Adjudication target: 50-100 confirmed positives, 200-300 confirmed negatives, ambiguous retained but excluded from headline recall.
- Recommendation: `DATA_PATH_RECOMMENDATION: BUILD_MICRO_CASQ_FROM_EXISTING_DATA`
- Final report: `test_vlm/outputs/clip_aqp_data_asset_audit_v1/reports/DATA_ASSET_AUDIT_FINAL_REPORT.md`
- Completion audit: `test_vlm/outputs/clip_aqp_data_asset_audit_v1/reports/COMPLETION_AUDIT.md`

This was a metadata-only planning pass. No VLM, YOLO, model training, candidate generation, dataset download, or existing-output overwrite was performed.
