# YOLO Environment Audit

## 1. Python Environment

| Item | Value |
|------|-------|
| Python | 3.10.20 |
| Path | `/qiuyeqing/tools/miniconda3/envs/garc/bin/python3` |
| Conda env | `garc` |

## 2. Package Availability

| Package | Status | Version |
|---------|--------|---------|
| ultralytics | ✅ installed | 8.4.51 |
| torch | ✅ installed | 2.12.0+cu126 |
| torchvision | ✅ installed | 0.27.0+cu126 |
| opencv-python-headless | ✅ installed | 4.10.0.84 |
| numpy | ✅ installed | 1.26.4 |
| pandas | ✅ installed | 2.2.2 |
| scipy | ✅ installed | (via ultralytics) |
| supervision | ❌ not installed | — |
| lap | ❌ not installed | — |
| filterpy | ❌ not installed | — |

**Note:** `supervision`, `lap`, and `filterpy` are not installed but are NOT required for this pipeline. The pipeline only needs ultralytics + opencv + pandas + numpy, all of which are present.

## 3. GPU Availability

| Item | Value |
|------|-------|
| CUDA available | ✅ Yes |
| Device count | 1 |
| Device name | NVIDIA GeForce RTX 2080 Ti |
| CUDA capability | 7.5 |
| Estimated VRAM | ~11 GB |

**Status:** GPU inference is available. The RTX 2080 Ti can run both yolov8n (6.3 MB) and yolov8x (131 MB) without issues.

## 4. Discovered Model Files

| Model | Path | Size | Likely Role |
|-------|------|------|-------------|
| YOLOv8n | `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt` | 6.3 MB | **Proxy (cheap)** |
| YOLOv8x | `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt` | 131 MB | **Pseudo-oracle (strong)** |

Both are YOLOv8 models from Ultralytics with COCO-pretrained weights (80 classes).

## 5. Class Name Mapping (COCO)

Both models share the same 80-class COCO nameset. The requested vehicle classes map as follows:

| Vehicle Class | COCO Class ID | COCO Name |
|---------------|---------------|-----------|
| car | 2 | car |
| bus | 5 | bus |
| truck | 7 | truck |
| motorcycle | 3 | motorcycle |

**Note:** `bicycle` (class 1) is NOT in the default `--vehicle-classes` list but exists in the model. The user can add it via `--vehicle-classes car,bus,truck,motorcycle,bicycle` if desired.

**Warning:** COCO class 51 is `carrot`, not `car`. The script must match by exact name, not substring, to avoid false positives.

## 6. Model Role Justification

| Property | YOLOv8n (proxy) | YOLOv8x (oracle) |
|----------|-----------------|-------------------|
| Parameters | ~3.2M | ~68.2M |
| FLOPs | ~8.7G | ~257.8G |
| COCO mAP50-95 | ~37.3 | ~53.9 |
| Inference speed | Fast | Slow |
| Cost tier | Cheap | Expensive |

The size gap (6.3 MB vs 131 MB) and accuracy gap (37.3 vs 53.9 mAP) make this a reasonable proxy/oracle pair. The oracle is NOT human ground truth — it is a stronger YOLO model used as pseudo-oracle.

## 7. Recommended Configuration

```bash
# Proxy model (cheap, fast)
--proxy-model /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt

# Oracle model (strong, slower)
--oracle-model /qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8x.pt

# Vehicle classes (COCO standard)
--vehicle-classes car,bus,truck,motorcycle

# Recommended K-values for SUPG experiments
--k-values 5,10,20
```

## 8. Missing Dependencies

None critical for this pipeline. All required packages are installed.

**Optional (not needed for this pipeline):**
- `supervision` — for advanced annotation/visualization
- `lap` — for MOT-style tracking
- `filterpy` — for Kalman-filter tracking

## 9. Risks and Caveats

1. **Architecture bias:** Both models are YOLOv8 — they share backbone architecture. Proxy/oracle disagreements may underestimate true error because both models have similar failure modes.
2. **Not ground truth:** The YOLOv8x oracle is a stronger detector, not a human annotator. Treat its outputs as pseudo-labels.
3. **COCO only:** Both models are COCO-pretrained. They do NOT detect domain-specific classes (e.g., "rickshaw", "tuk-tuk", "e-scooter"). If the video contains non-COCO vehicles, they will be missed.
4. **Frame-level only:** This pipeline produces per-frame counts, not tracking. Clip-level statistics are derived from consecutive frame thresholds, not MOT.
