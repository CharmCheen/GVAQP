# DRIV100 SUPG-Style Real-Video Smoke Report

## 1. Dataset
- dataset: DRIV100
- source: Zenodo record 4389243
- selected video path: none
- downloaded file name / archive name: json.zip
- video size: none
- note: SUPG-style real-video reproduction, not exact SUPG night-street reproduction
- status: stopped before frame extraction because the Zenodo record does not include video files

## 2. Environment
- python: 3.10.20
- torch version: 2.12.0+cu126
- cuda availability: True
- GPU name: NVIDIA H20-3e
- ultralytics version: 8.4.51

## 3. Frame Extraction
- sample_fps: 1.0
- max_frames: 1000
- extracted frame count: 0
- frame table path: /qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/driv100_smoke/frame_metadata.parquet
- status: not run; /qiuyeqing/llama_prl/G-ARC/data/videos/driv100_sample.mp4 was not created

## 4. Proxy / Oracle
- proxy model: YOLOv8n
- oracle model: YOLOv8x
- target_class: car
- label rule: oracle_score >= 0.5
- label mean / positive rate: not available
- proxy score min/max: not available
- status: not run because no video frames were available

## 5. SUPG Smoke Results
Not run. summary.csv was not generated because frame extraction and score materialization could not proceed without a source video.

## 6. Issues
- Zenodo record 4389243 listed json2label.py, json.zip, README.txt, frame_extract.py, and meta.csv, but no mp4/mov/avi/mkv/webm file.
- The script downloaded the smallest archive, json.zip (6,494,352 bytes), extracted it, and found 401 JSON label files but no video file.
- DRIV100 README states that 720p YouTube videos must already be stored in a DRIV100 directory for frame extraction.
- label mean was not computed.
- SUPG/U-CI results were not produced, so no vacuous-result check was possible.
- GPU was available and would have been used via cuda:0.
- failed command: download-first-video exited with status 1 after reporting that no video could be automatically found.

## 7. Next Step
Provide or download one DRIV100 source YouTube video as /qiuyeqing/llama_prl/G-ARC/data/videos/driv100_sample.mp4, then rerun extraction, YOLO materialization, and the 5-trial SUPG smoke.
