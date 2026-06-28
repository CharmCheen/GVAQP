# V13.6 Preflight Report

**Protocols read:**
- `/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md`
- `/qiuyeqing/llama_prl/G-ARC/docs/clip_aqp/REALCARTEST_ORACLE_RELATIVE_VALIDATION_V13_5.md`

**Date:** 2026-06-23

## Required V13.5 Input Verification

| File | Status |
|---|---|
| `v13_5_.../tables/coarse_5s_clip_grid.csv` | ✅ EXISTS |
| `v13_5_.../tables/proxy_features_5s.csv` | ✅ EXISTS |
| `v13_5_.../tables/vlm_pilot_sample_100.csv` | ✅ EXISTS |
| `v13_5_.../tables/vlm_pilot_labels.csv` | ✅ EXISTS |
| `v13_5_.../raw_vlm_responses/pilot/` | ✅ 100 JSON files |

## Video
- Path: `/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4`
- Duration: 3,987.1s
- Resolution: 1920×1080, 24fps, H.264

## Decision
```
PREFLIGHT_PASS — all required inputs present
```
