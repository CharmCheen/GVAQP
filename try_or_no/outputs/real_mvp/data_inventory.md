# Data Inventory

## Available Datasets

### 1. BDD100K (Primary — Used)
- **Path:** `/qiuyeqing/llama_prl/G-ARC/data/bdd100k/bdd100k/`
- **Images:** 10,000 validation images in `images/100k/val/`
- **Annotations:** `bdd100k.csv` (186,033 object annotations, 12MB)
- **Format:** CSV with columns: `object_id, image_path, class_name, xmin, ymin, xmax, ymax`
- **Classes:** car (102,837), traffic sign (34,724), traffic light (26,884), pedestrian (13,425), truck (4,243), bus (1,660), bicycle (1,039), rider (658), motorcycle (460), other vehicle (85), train (15), trailer (2)
- **Vehicle count per image:** mean=11.1, median=10, min=0, max=61
- **Supports count(vehicle) >= K:** Yes. 9,486/10,000 images have >= 3 vehicles
- **Supports clip construction:** Limited — images are independent frames, not sequential video. Can group by video_id prefix for pseudo-clips.
- **Size on disk:** ~575MB (images + annotations)

### 2. UA-DETRAC (Used for clip-level)
- **Path:** `/qiuyeqing/llama_prl/G-ARC/data/ua_detrac/`
- **Videos:** 60 sequences in zip (`ua_detrac_training_set.zip`, 5.6GB)
- **Frames extracted:** 83,756 frames across 8 sequences (in `frames/uadetrac/`)
- **Annotations:** Per-sequence `annotations.csv` inside zip (60 files)
- **Format:** CSV with columns: `filename, width, height, class, xmin, ymin, xmax, ymax, confidence, target_id`
- **Vehicle count per frame:** mean=10.8, all sequences have vehicles
- **Supports clip construction:** Yes — each sequence is a natural clip (437-2,635 frames each)
- **Size on disk:** ~5.6GB (zip)

### 3. KITTI Raw
- **Path:** `/qiuyeqing/llama_prl/G-ARC/data/kitti_raw/`
- **Frames:** Symlinked in `frames/kitti_0005/` (22 frames from drive 0005)
- **Annotations:** Not extracted; would need KITTI devkit
- **Supports clip construction:** Yes (sequential driving frames)
- **Status:** Not used — too few frames without annotation extraction

### 4. DRIV100
- **Path:** `/qiuyeqing/llama_prl/G-ARC/data/driv100/`
- **Data:** 400 evaluation records in `meta.csv` (hand/object detection annotations)
- **JSON annotations:** 10 files in `json.zip.extracted/json/`
- **Format:** YouTube video URLs with eval_frame, start_frame, end_frame
- **Status:** Not used — different domain (hand detection), no vehicle annotations

### 5. COCO
- **Path:** `/qiuyeqing/llama_prl/G-ARC/data/coco/`
- **Status:** Directory exists but contents not inspected; would need COCO annotations

## Datasets NOT Available Locally
- nuScenes mini — not found
- CityFlow — not found

## Recommendation
BDD100K is the best available dataset: 10K images with full object detection annotations, ready to use without extraction. UA-DETRAC provides video sequences for clip-level experiments.
