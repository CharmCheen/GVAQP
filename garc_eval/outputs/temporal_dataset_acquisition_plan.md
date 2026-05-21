# Temporal Dataset Acquisition Plan

## Goal

Acquire a continuous-video dataset for G-ARC clip-level experiments. The dataset
must support frame-level proxy/oracle scoring and clip-level ground-truth
evaluation.

## Criteria

| Criterion | Requirement | Rationale |
|-----------|-------------|-----------|
| N (sampled frames) | >= 10,000 | Budget-relative statistical power |
| Positive frame rate | 1%-30% | Non-degenerate SUPG behavior |
| Continuous timestamps | Required | Clip construction needs temporal ordering |
| GT/pseudo-GT clips | >= 10 events | Meaningful clip recall/precision evaluation |
| Traffic/road scenes | Preferred | Consistent with existing YOLO proxy/oracle pipeline |
| Public availability | Required | Reproducibility |
| Resolution | >= 480p | YOLO detection quality |

## Candidate Datasets

### 1. UA-DETRAC

- **Source**: https://detrac-db.rit.albany.edu/
- **Content**: 100,000+ frames from 24 traffic surveillance videos
- **Annotations**: Vehicle bounding boxes, trajectories, occlusion labels
- **Resolution**: 960x540
- **Positive rate**: High vehicle density in most clips
- **Clip structure**: Natural temporal events (vehicle passes, congestion)
- **License**: Research use
- **Suitability**: HIGH — purpose-built for vehicle tracking, continuous video
- **Acquisition**: Direct download from website

### 2. CityFlow

- **Source**: https://cityflow-project.github.io/
- **Content**: 229,000+ frames from 40 camera feeds
- **Annotations**: Vehicle bounding boxes, tracking IDs
- **Resolution**: Varies (mostly 1080p)
- **Positive rate**: Moderate to high
- **Clip structure**: Multi-camera with temporal continuity
- **License**: Research use
- **Suitability**: HIGH — large-scale, multi-camera, continuous
- **Acquisition**: Direct download

### 3. D2-City

- **Source**: https://github.com/AIoT-Research/D2-City
- **Content**: 15,000+ video clips from dashcams
- **Annotations**: Vehicle bounding boxes
- **Resolution**: 1080p and 720p
- **Positive rate**: Varies by clip
- **Clip structure**: Dashcam clips with natural temporal events
- **License**: Research use
- **Suitability**: MEDIUM — dashcam perspective, variable clip lengths
- **Acquisition**: GitHub release

### 4. Long Traffic Surveillance Videos

- **Source**: YouTube (Creative Commons) or municipal open data portals
- **Content**: Hours-long continuous traffic camera footage
- **Annotations**: No built-in annotations; use YOLO pseudo-GT
- **Resolution**: 720p-1080p
- **Positive rate**: Depends on location/time
- **Clip structure**: Natural temporal events
- **License**: Varies (CC-BY preferred)
- **Suitability**: MEDIUM — requires manual curation, no built-in GT
- **Acquisition**: yt-dlp or direct download

### 5. User-Provided MP4 Corpus

- **Source**: User's own video data
- **Content**: Custom traffic/surveillance footage
- **Annotations**: User-provided or YOLO pseudo-GT
- **Resolution**: User-dependent
- **Positive rate**: User-dependent
- **Clip structure**: User-dependent
- **License**: User-owned
- **Suitability**: HIGH if available — no acquisition barriers
- **Acquisition**: User provides directly

## Recommended Priority

1. **UA-DETRAC** (primary) — purpose-built, well-annotated, continuous video
2. **CityFlow** (secondary) — larger scale, multi-camera
3. **User-provided MP4** (if available) — no acquisition overhead

## Acquisition Steps

1. Download dataset from official source
2. Extract frames at target fps (e.g., 5-10 fps for efficiency)
3. Run YOLOv8n proxy scoring on extracted frames
4. Run YOLOv8x pseudo-oracle scoring on extracted frames
5. Calibrate count threshold K for target positive rate
6. Build frames.parquet with columns: id, frame_idx, timestamp, proxy_score,
   oracle_count, label
7. Run clip_metrics evaluation pipeline

## Expected Output

- `garc_eval/outputs/<dataset>_clip_experiment/frames.parquet`
- `garc_eval/outputs/<dataset>_clip_experiment/clip_metrics_summary.md`
- `garc_eval/outputs/<dataset>_clip_experiment/gt_clips.json`
- `garc_eval/outputs/<dataset>_clip_experiment/pred_clips.json`

---

Generated: 2026-05-21
