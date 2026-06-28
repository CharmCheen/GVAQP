# Phase 1.4 Nexar Candidate Feasibility Summary

Full output directory:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_candidate_v1`

Primary report:

`/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase1_candidate_v1/reports/CANDIDATE_FEASIBILITY_REPORT.md`

Result:

`CANDIDATE_DECISION: NEED_VIDEO_ACCESS`

The Nexar-200 manifest points to 400 expected local videos, but the smoke subset check found 0 accessible files out of 100 selected videos. The available Nexar metadata contains filenames and scene/weather fields but no remote download URLs, so video-based candidate generation, frame extraction, feature extraction, and certification of promising candidates were not run.

GPU visibility was logged, but GPU inference was not used because no video files were accessible.
