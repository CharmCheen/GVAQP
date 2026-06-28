# Phase 1 Local Candidate Smoke Summary

Output directory: `test_vlm/outputs/clip_aqp_phase1_local_candidate_smoke_v1`

## Scope

This run smoke-tested local-video candidate generation using videos and clips already present in the G-ARC project. It did not use Hugging Face, download datasets, train models, run a 32B VLM scan, or fabricate event boundaries.

The evaluation is local-pseudo/debugging only. Clean event boundaries are absent, so results are unit-level enrichment against available conservative VLM/human-audit labels rather than event-IoU recall.

## Artifacts

- Report: `test_vlm/outputs/clip_aqp_phase1_local_candidate_smoke_v1/reports/LOCAL_CANDIDATE_SMOKE_REPORT.md`
- Video inventory: `tables/local_video_inventory.csv`
- Label inventory: `tables/local_label_inventory.csv`
- Smoke units: `tables/local_smoke_units.csv`
- Frame index: `tables/local_frame_index.csv`
- Candidate CSVs: `candidates/*.csv`
- Evaluation table: `tables/local_candidate_eval_results.csv`
- Figures: `figures/local_candidate_recall_or_enrichment.png`, `figures/local_candidate_runtime.png`
- Wrapper/log: `scripts/run_local_candidate_smoke.sh`, `logs/run_local_candidate_smoke.log`

## Key Results

- Local videos inventoried: 2564 readable video files.
- Smoke units: 102 local-pseudo kinematic proxy clips.
- Extracted frames: 600.
- Candidate generators completed: fixed sliding window, random, motion energy, existing proxy score, YOLO count proxy.
- Optional CLIP/SigLIP scoring was skipped because no local model assets were configured and no download was allowed.
- YOLO used GPU: NVIDIA A800-SXM4-80GB.
- YOLO frames processed: 306.
- YOLO runtime: 28.73 seconds.
- YOLO throughput: 10.65 fps.

At k=20, fixed sliding window and YOLO count proxy reached unit-level positive coverage 0.45 and precision@20 0.45 on the local-pseudo labels. Random and motion energy were at 0.20 coverage and precision@20 0.20. These results are useful for pipeline debugging, not research-valid event-boundary claims.

## Verification

- `python -m py_compile scripts/*.py` passed.
- Completion audit passed for required directories, required files, CSV schemas, candidate non-oracle flags, no fabricated clean boundaries, wrapper `set -euo pipefail`, report decision, and figures.

## Decision

LOCAL_CANDIDATE_DECISION: PIPELINE_READY_FOR_NEXAR_VIDEO
