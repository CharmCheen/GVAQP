# CASQ Phase 1 Nexar-200 Derived v1 Summary

Output directory:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_200_v1`

Main report:

`reports/NEXAR_200_DERIVED_BENCHMARK_REPORT.md`

This run builds a metadata-only Nexar-derived CASQ benchmark with up to 200 positive derived-boundary events and 200 normal videos, then reruns Phase 0-style SUPG stitch and no-repair block/event audit validation. No VLM, training, perception stack, full dataset download, or original-boundary fabrication is used.

Latest verified result:

- Manifest: 200 positive rows and 200 normal rows.
- CASQ events: 200, all `derived_from_alert_time_to_event_moment`.
- Units: 4,401 fixed 5s / 10s / 15s units.
- Reference block-audit condition: theta=0.3, gamma=0.8, delta=0.1, 10s blocks, 35% certification sample.
- Reference true derived recall: 0.06.
- Reference median LCB recall: 0.0.
- Reference fraction vacuous: 1.0.
- Reference GVR: 0.0, with certificate success rate 0.0.

Decision:

`NEXAR_200_DECISION: METHOD_STILL_TOO_VACUOUS`
