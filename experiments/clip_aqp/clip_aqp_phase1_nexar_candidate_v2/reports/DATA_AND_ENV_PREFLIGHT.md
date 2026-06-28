# Data and Environment Preflight

## Protocol

CASQ_CODEX_BRIEF_V12_1.md was read. This is a Phase 1+ candidate-feasibility v2 run, not a Phase 0 run.

## Input Data

- Nexar manifest rows: 400
- CASQ event rows: 200
- CASQ unit rows: 4401
- Repair readability rows: 400
- Full readable rows: 392
- Positive readable rows: 200
- Normal readable rows: 192
- Balanced readable rows: 384

## Design / Report Split

Split protocol: HELD_OUT_REPORT.

Candidate hyperparameters are selected on `candidate_dev` videos only. Reported final metrics are computed on `heldout_report` videos.

| split_role | label | videos |
| --- | --- | --- |
| candidate_dev | normal | 96 |
| candidate_dev | positive | 96 |
| heldout_report | normal | 96 |
| heldout_report | positive | 96 |

## Local Model Inventory

| asset | available | path | notes |
| --- | --- | --- | --- |
| CASQ_CODEX_BRIEF_V12_1 | True | /qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md | read by v2 runner |
| Nexar video repair output | True | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_video_repair_v1/tables/post_download_manifest_readability.csv | VIDEO_REPAIR_DECISION: READY_FOR_NEXAR_CANDIDATE_RERUN |
| videos_hf | True | /qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/videos_hf | local repaired video root |
| YOLOv8n | True | /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt | default proxy candidate model |
| YOLOv8x | True | /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt | pseudo-oracle model path; not used for candidate v2 |
| torch_cuda | True |  | NVIDIA H20-3e |
| representation_based_candidate | False |  | REPRESENTATION_CANDIDATE_NOT_AVAILABLE |
| 32B audit imported | True | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_nexar_candidate_v2/audits/vlm_micro_audit_results.csv | imported from v1 without rerun |

## External Label Mapping

LOOSE_APPROXIMATION / AUDIT_UNRELIABLE.

Nexar-derived labels must not be treated as equivalent to O_enter_ego_path_v0. Candidate and certificate results are Nexar-derived-boundary-relative.
