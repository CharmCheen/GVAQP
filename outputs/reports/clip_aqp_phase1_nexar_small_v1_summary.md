# CASQ Phase 1.1 Nexar Small v1 Summary

Output directory:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_small_v1`

Main report:

`reports/NEXAR_SMALL_INGESTION_REPORT.md`

The run prepares a small-subset manifest and CASQ conversion/validation scaffolding for Nexar without downloading the full dataset, running VLMs, training models, or building a perception stack.

Latest verified decision:

`NEXAR_SMALL_DECISION: BOUNDARIES_ARE_DERIVED_ONLY`

The smoke run used public metadata CSVs only, selected 25 positive and 25 normal rows, converted 25 CASQ events, and generated fixed 5s/10s/15s units. No videos were downloaded.
