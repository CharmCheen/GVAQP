# Data Inventory

## Available Datasets

### 1. UA-DETRAC (Primary — Used)
- **Path:** `/qiuyeqing/llama_prl/G-ARC/data/ua_detrac/ua_detrac_training_set.zip`
- **Size:** ~5.6GB (zip), annotations are small CSVs inside
- **Continuous frames:** Yes — 60 video sequences, 25 FPS
- **Ego pose:** NO — fixed surveillance camera
- **Camera calibration:** NO
- **3D boxes:** NO — 2D bounding boxes only
- **Track/instance IDs:** YES — `target_id` in annotations.csv (341 unique tracks)
- **Visibility/occlusion:** Partial — `target_id = -1` for untracked/occluded objects
- **Supports queries:**
  - `in_fov(target)`: YES (2D: `in_image_label` — bbox area >= threshold)
  - `within_distance(target, ego, D)`: NO (no 3D/ego data)
  - `in_ego_front_region(target)`: PARTIAL (2D: center in front-region box)
  - `enters/exits field of view`: YES (track start/end frames)
  - `count(vehicle) >= K`: YES (per-frame vehicle count)

### 2. KITTI Raw (Available but not used for main experiments)
- **Path:** `/qiuyeqing/llama_prl/G-ARC/data/kitti_raw/`
- **Drives:** 4 sequences (drive_0005, 0014, 0018, 0051)
- **Total frames:** 1,176 with OXTS ego pose data
- **Ego pose:** YES — OXTS data (lat, lon, alt, roll, pitch, yaw, velocities, accelerations)
- **Camera calibration:** YES — 4 cameras (image_00 to image_03)
- **3D boxes:** NO — no object annotations available locally
- **Track/instance IDs:** NO
- **Supports queries:**
  - `in_fov(target)`: NO (no object annotations)
  - `within_distance(target, ego, D)`: NO (no object positions)
  - `in_ego_front_region(target)`: NO
  - `enters/exits field of view`: NO
  - `count(vehicle) >= K`: NO (no annotations)

### 3. BDD100K (Not used — not continuous video)
- **Path:** `/qiuyeqing/llama_prl/G-ARC/data/bdd100k/`
- **Images:** 10,000 independent validation images
- **Annotations:** Object detection (car, truck, bus, etc.)
- **Continuous frames:** NO — independent images, not video
- **Ego pose:** NO

## Missing Data

To fully validate the kinematic query direction with 3D ego-relative geometry, we would need:
1. **nuScenes mini** — has ego pose, calibrated cameras, 3D boxes, track IDs
2. **Waymo Open Dataset** — has ego pose, 3D boxes, track IDs

Neither is available locally. Downloading was not attempted per constraints.

## Implication

The current MVP uses UA-DETRAC as a **2D fallback**. It validates the *temporal prediction and clip construction* aspects of the research direction, but **cannot validate full 3D ego-relative geometry** (within_distance, true FOV with camera intrinsics). This limitation is documented throughout.
