# BLOCKED: Learned Anomaly Proxy Feasibility Check

No runnable local DoTA / traffic anomaly / learned anomaly proxy was found. No learned anomaly scores were generated, and no learned-anomaly budget simulation was run.

## Searched Directories

- `/qiuyeqing/llama_prl/G-ARC/test_vlm`
- `/qiuyeqing/llama_prl/G-ARC/refe_repos`
- `/qiuyeqing/llama_prl/G-ARC/models`
- `/qiuyeqing/llama_prl/G-ARC/try_or_no`

## Installed Local Repositories Found

- `/qiuyeqing/llama_prl/G-ARC/refe_repos/abae`
- `/qiuyeqing/llama_prl/G-ARC/refe_repos/supg`

## Candidate Traffic-Anomaly Directories

- none

## Candidate Traffic-Anomaly Text Files

- none

## Candidate Pretrained Weights

- none

## All Local Weight-Like Files Observed

- `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt`
- `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt`
- `/qiuyeqing/llama_prl/G-ARC/try_or_no/arc_source/preprocessing/Everest/docs/Unity2Skfb.bin`
- `/qiuyeqing/llama_prl/G-ARC/try_or_no/arc_source/preprocessing/model_weights/yolov5s.pt`
- `/qiuyeqing/llama_prl/G-ARC/try_or_no/arc_source/preprocessing/model_weights/yolov5su.pt`

## Candidate Inference / Demo Entrypoints

- none

## Why This Is Blocked

- No DoTA / traffic anomaly detector repository was found under the allowed search directories.
- No pretrained traffic-anomaly checkpoint was found. The local weight-like files observed are VLM, YOLO, or otherwise unrelated assets, not learned anomaly detector weights.
- No traffic-anomaly inference or demo entrypoint was found.
- Because there is no runnable detector, producing `score_learned_anomaly` would be fabricated and is not allowed.

## Minimum User-Provided Resources Needed

Provide the following local resources before this route can be evaluated:

- `repo path`: path to a DoTA / traffic anomaly / video anomaly detector repository.
- `checkpoint path`: pretrained weights compatible with that repository.
- `inference command`: command that accepts either clip videos, frame directories, or an annotation/table format and emits frame-level or clip-level anomaly scores.
- `expected input format`: one of raw video clips, extracted frames, optical flow, bbox tracks, or DoTA-format annotations.
- `score semantics`: whether larger scores mean more anomalous and whether scores are calibrated per frame or per clip.

## Planned Adapter Contract Once Resources Exist

- Per-clip learned scores should be written to `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/learned_anomaly_scores.csv`.
- Required columns: `clip_id,start_time,end_time,clip_path,score_learned_anomaly,score_source,score_aggregation,runtime_sec,status,error_message`.
- If detector output is frame-level, aggregate to clip level using max or top-k mean and document the aggregation.
- Merge `score_learned_anomaly` into `/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/proxy_scores_augmented.csv` alongside existing `score_count`, `score_naive`, and `score_kinematic`.
- Only after real scores exist should `05_budget_simulation.py` be extended/run with learned-anomaly methods such as `top_learned_anomaly`, `temporal_nms_learned_anomaly`, and learned ensembles.

## Recommendation

- Continue using count / naive proxies plus temporal NMS, proxy-triggered expansion, and conservative VLM pseudo-GT as the main experimental line.
- Do not invest in the DoTA / learned anomaly route until a concrete local repo, checkpoint, and inference command are available.
- Do not resume blind kinematic-v0 tuning as the main path.
