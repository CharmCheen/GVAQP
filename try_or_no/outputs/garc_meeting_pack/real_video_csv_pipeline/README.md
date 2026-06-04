# Real Video SUPG-style CSV Pipeline

Convert a real video into per-frame proxy/oracle records using two YOLO models for preliminary real-video validation of G-ARC motivation.

## What This Is (and Is Not)

**This is:** A pipeline that runs a cheap YOLO (proxy) and a stronger YOLO (pseudo-oracle) on every frame of a video, producing a CSV with per-frame detection counts and SUPG-compatible columns.

**This is NOT:** ARC reproduction, G-ARC implementation, or a human-ground-truth benchmark. The oracle is a stronger neural network, not a human annotator.

## Prerequisites

- Python 3.10+ with `ultralytics`, `opencv-python`, `pandas`, `numpy`
- CUDA GPU (recommended) or CPU
- Two YOLO `.pt` model files

Already available in this environment:
- ultralytics 8.4.51
- CUDA with RTX 2080 Ti
- Proxy: `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt` (6.3 MB)
- Oracle: `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt` (131 MB)

## Quick Start

### 1. Audit Environment

```bash
cat outputs/garc_meeting_pack/real_video_csv_pipeline/yolo_environment_audit.md
```

### 2. Smoke Test (100 frames)

```bash
python outputs/garc_meeting_pack/real_video_csv_pipeline/video_to_supg_csv.py \
    --video /path/to/your/video.mp4 \
    --proxy-model /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt \
    --oracle-model /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt \
    --output-csv outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg_smoke.csv \
    --output-report outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg_smoke_report.md \
    --max-frames 100 \
    --frame-stride 1
```

This processes only 100 frames — fast enough to verify everything works.

### 3. Full Video Run

```bash
python outputs/garc_meeting_pack/real_video_csv_pipeline/video_to_supg_csv.py \
    --video /path/to/your/video.mp4 \
    --proxy-model /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt \
    --oracle-model /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt \
    --output-csv outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg.csv \
    --output-report outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg_report.md \
    --frame-stride 1
```

### 4. Strided Processing (for long videos)

```bash
# Process every 5th frame — 5x faster, still captures dynamics
python outputs/garc_meeting_pack/real_video_csv_pipeline/video_to_supg_csv.py \
    --video /path/to/your/video.mp4 \
    --proxy-model /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt \
    --oracle-model /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt \
    --output-csv outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg_stride5.csv \
    --output-report outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg_stride5_report.md \
    --frame-stride 5
```

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--video` | required | Input video path |
| `--proxy-model` | required | Cheap YOLO model (.pt) |
| `--oracle-model` | required | Stronger YOLO model (.pt) |
| `--output-csv` | required | Output CSV path |
| `--output-report` | required | Output report path (.md) |
| `--frame-stride` | 1 | Process every N-th frame |
| `--vehicle-classes` | car,bus,truck,motorcycle | Comma-separated class names |
| `--k-values` | 5,10,20 | Comma-separated K values for label columns |
| `--conf` | 0.25 | YOLO confidence threshold |
| `--imgsz` | 640 | Inference image size |
| `--max-frames` | 0 (unlimited) | Max frames to process |
| `--device` | auto | Device: auto/cpu/cuda/cuda:0 |

## Output Files

### CSV (`video_supg.csv`)

Each row = one processed frame. Key columns:

| Column | Description |
|--------|-------------|
| `id` | Frame index (SUPG row ID) |
| `frame_idx` | Original video frame number |
| `timestamp_sec` | Frame timestamp |
| `proxy_vehicle_count` | Vehicles detected by proxy |
| `oracle_vehicle_count` | Vehicles detected by oracle |
| `proxy_score` | count + 0.01 * conf_sum |
| `proxy_score_supg` | Same as proxy_score |
| `proxy_positive_K{K}` | 1 if proxy count >= K |
| `oracle_positive_K{K}` | 1 if oracle count >= K |
| `label_K{K}` | Pseudo-label (oracle positive) |

### Report (`video_supg_report.md`)

Contains:
- Data provenance (video, models, settings)
- Per-K statistics (positive rates)
- Proxy/oracle agreement (precision, recall, F1)
- Clip statistics (tau=20, tau=30 with IoU matching)
- Limitations and caveats

## Using the CSV for Experiments

### SUPG-style Experiments

The CSV has the required SUPG columns:
- `id`: row identifier
- `proxy_score_supg`: proxy score (continuous)
- `label_K{K}`: pseudo-label from oracle (binary)

Use these to simulate SUPG-style selection:
1. Rank frames by `proxy_score_supg`
2. Select top-N frames
3. Evaluate selection quality against `label_K{K}`

### ARC-style Experiments

Use `proxy_vehicle_count` as the proxy signal and `oracle_vehicle_count` as the oracle signal. Frame-level counts can drive adaptive sampling policies.

### G-ARC-style Experiments

The per-frame proxy/oracle structure supports gradient-based resource allocation experiments. The K-threshold labels allow studying how different "interestingness" definitions affect selection.

## Customization

### Different Vehicle Classes

```bash
--vehicle-classes car,bus,truck,motorcycle,bicycle
```

### Different K Values

```bash
--k-values 3,5,10,15,20,30
```

### Different Confidence Threshold

```bash
--conf 0.1  # lower threshold = more detections, more noise
--conf 0.5  # higher threshold = fewer detections, more precision
```

## How This Relates to ARC and G-ARC

### ARC's High-Level Idea

ARC targets **relevant clip queries** over large-scale video repositories. A relevant clip query returns continuous video clips, not individual frames. A typical query is:

> Find clips of duration at least tau where every frame satisfies a predicate, such as count(vehicle) >= K.

ARC's high-level workflow can be described as:

1. Run a cheap proxy model over the video.
2. Use proxy outputs to prune unlikely regions.
3. Form initial candidate clips.
4. Exploit temporal clustering / continuity.
5. Use a stronger oracle model to refine candidates.
6. Estimate candidate-side confidence.
7. Return relevant candidate clips under budget.

ARC is designed to maximize recall and reduce oracle cost while maintaining a confidence estimate for returned candidate clips. Its confidence is **candidate-side / precision-like**: it estimates whether returned candidate clips are likely to be hits. It does not directly certify that all true relevant clips outside candidates have been found.

### Why Candidate-Side Confidence Is Not Enough for G-ARC

Candidate-side confidence answers: *"Are the returned candidate clips reliable?"*

It does not answer: *"How many true relevant clips were missed outside the candidate set?"*

Therefore high candidate confidence can coexist with low clip-level recall, especially when the proxy has high precision but low recall.

In our real-video smoke, YOLOv8n proxy had high frame-level precision but low frame-level recall against YOLOv8x pseudo-oracle. Under a tau-length clip constraint, sparse proxy positives may fail to form candidate clips, causing low or even zero clip recall.

**This is motivation only, not proof that ARC fails.**

### G-ARC's Target

G-ARC aims to add a **recall-certification layer** on top of ARC-style candidate generation. Target guarantee:

Pr[ClipRecall(C_hat, C_star; theta, tau) >= gamma] >= 1 - delta

where C_hat is the returned candidate clip set, C_star is the true relevant clip set under the oracle, theta is the IoU hit threshold, tau is the minimum clip length, gamma is the target clip recall, and delta is the allowed failure probability.

G-ARC is not just trying to make candidates more precise. Its key goal is to audit possible missed clips.

### Proposed G-ARC Workflow

1. **Step 1:** ARC-style candidate generation using proxy scores.
2. **Step 2:** Candidate and boundary verification using limited oracle calls.
3. **Step 3:** Non-candidate region audit by verification sampling.
4. **Step 4:** Estimate a conservative upper bound on missed true clips.
5. **Step 5:** Derive a clip recall lower bound.
6. **Step 6:** Return candidate clips with a recall certificate, or report that the oracle budget is insufficient.

### Role of This Pipeline

This pipeline only creates the per-frame table needed for later experiments. It provides frame_idx, proxy vehicle counts/scores from YOLOv8n, pseudo-oracle vehicle counts/scores from YOLOv8x, and SUPG-compatible labels and proxy scores.

This table can be used later to test:
- proxy-only clip retrieval;
- SUPG-style frame selection + stitching;
- ARC-style candidate generation;
- G-ARC verification sampling and recall certification.

**This pipeline itself is not ARC and not G-ARC.**

## Caveats

1. **Oracle is NOT human ground truth.** It's a stronger YOLO model.
2. **Both models share YOLOv8 architecture.** They may have correlated failure modes.
3. **COCO classes only.** Non-standard vehicles (rickshaws, e-scooters, etc.) won't be detected.
4. **No tracking.** Clip statistics are derived from consecutive frames, not MOT.
5. **This is NOT ARC or G-ARC.** It's a data preparation step.
