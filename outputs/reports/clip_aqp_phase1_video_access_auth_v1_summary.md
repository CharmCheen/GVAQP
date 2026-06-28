# Nexar Phase 1.4 Auth Video Access Summary

Full output directory:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1`

Primary report:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_video_access_auth_v1/reports/NEXAR_AUTH_VIDEO_ACCESS_REPORT.md`

Result:

`VIDEO_AUTH_DECISION: NEED_HF_AUTH_OR_LICENSE`

Findings:

- HF CLI is available, but `hf auth whoami` reports that the environment is not logged in.
- The authenticated smoke manifest contains 5 positive and 5 normal videos from the prior HF-mapped access plan.
- Existing readable video `00822.mp4` was included and verified.
- Missing-video downloads were skipped because HF auth is absent.
- Frame smoke was skipped because only 1/10 videos is readable.

No VLM, training, GPU inference, candidate generation, or full-dataset download was run.
