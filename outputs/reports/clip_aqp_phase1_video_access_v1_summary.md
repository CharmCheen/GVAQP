# Nexar Phase 1.4 Video Access Summary

Full output directory:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_v1`

Primary report:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_v1/reports/NEXAR_VIDEO_ACCESS_REPORT.md`

Result:

`VIDEO_ACCESS_DECISION: NEED_HF_AUTH_OR_LICENSE`

Findings:

- Local search initially found no raw Nexar videos; after the controlled attempt, one smoke video exists under `datasets/casq_external/nexar/videos_smoke/positive/00822.mp4`.
- Hugging Face repo `nexar-ai/nexar_collision_prediction` is public/listable and contains the Nexar-200 manifest filenames.
- Kaggle CLI and credentials are not configured.
- Controlled unauthenticated HF download verified 1 of the requested 10 smoke videos; the remaining 9 attempts timed out under the bounded per-file timeout.

No VLM, GPU inference, training, candidate generation, or full-dataset download was run.
