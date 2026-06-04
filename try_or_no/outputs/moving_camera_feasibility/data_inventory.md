# Data Inventory for Moving-Camera Feasibility

## Search Results

Searched under `/qiuyeqing/llama_prl/G-ARC` and `/qiuyeqing/llama_prl` for nuScenes, Waymo, KITTI, and other moving-camera datasets.

---

## 1. nuScenes

**Status: NOT AVAILABLE**

No nuScenes data found anywhere under `/qiuyeqing/llama_prl/G-ARC` or `/qiuyeqing/llama_prl`.

Searched for:
- `nuScenes*`, `nuscenes*`, `v1.0-mini`, `v1.0-trainval`
- Any directory or file containing "nuscenes"

**Impact:** nuScenes mini would be the ideal dataset for this feasibility study. It provides ego pose, calibrated cameras, 3D boxes with instance tracks, timestamps, visibility metadata, and category labels. Its absence is the primary blocker for full validation.

---

## 2. Waymo

**Status: NOT AVAILABLE**

No Waymo data found anywhere.

Searched for:
- `waymo*`, `waymo_open_dataset*`, `segment*`

**Impact:** Waymo Open Dataset would also work but is not available.

---

## 3. KITTI Raw

**Status: PARTIALLY AVAILABLE — Missing Critical Components**

**Available:**
- 4 driving sequences from 2011_09_26
  - `2011_09_26_drive_0005_sync` (154 frames)
  - `2011_09_26_drive_0014_sync`
  - `2011_09_26_drive_0018_sync`
  - `2011_09_26_drive_0051_sync`
- Camera images (image_00 through image_03, 154 frames each for drive_0005)
- OXTS GPS/IMU data (ego pose: lat, lon, alt, roll, pitch, yaw, velocities, accelerations)
- Velodyne LiDAR point clouds
- Timestamps for all sensors

**NOT Available:**
- **Camera calibration files** (calib_cam_to_cam.txt, calib_imu_to_velo.txt) — NOT FOUND
- **3D object annotations** (no label_2/ directory, no KITTI tracking labels) — NOT FOUND
- **Instance track IDs** — no object annotations at all

**What KITTI Raw provides:**
| Requirement | Available? | Notes |
|-------------|-----------|-------|
| Continuous frames | YES | 154 frames at ~10 FPS |
| Ego pose | YES | OXTS with lat/lon/alt + roll/pitch/yaw |
| Calibrated cameras | NO | Images exist but calibration files missing |
| 3D boxes | NO | No object annotations |
| Track/instance IDs | NO | No object annotations |
| Timestamps | YES | OXTS and image timestamps |
| Visibility/occlusion | NO | No annotations |
| Category labels | NO | No annotations |
| Constructible clips | NO | No objects to track |

**Assessment:** KITTI raw provides ego motion data but lacks the critical 3D object annotations and camera calibration needed to define in_fov, within_30m, or ego_front predicates. It cannot support the moving-camera query table.

---

## 4. UA-DETRAC

**Status: AVAILABLE — Fixed Camera Only**

- Path: `/qiuyeqing/llama_prl/G-ARC/data/ua_detrac/`
- 60 surveillance camera sequences with 2D bounding box annotations
- Tracks with instance IDs (target_id)
- Processed data exists in `try_or_no/outputs/real_mvp/`

**What UA-DETRAC provides:**
| Requirement | Available? | Notes |
|-------------|-----------|-------|
| Continuous frames | YES | 60 video sequences |
| Ego pose | NO | Fixed surveillance camera |
| Calibrated cameras | NO | No calibration data |
| 3D boxes | NO | 2D bounding boxes only |
| Track/instance IDs | YES | target_id in annotations |
| Timestamps | YES | Frame numbers |
| Visibility/occlusion | PARTIAL | target_id = -1 for untracked |
| Category labels | YES | Vehicle classes |
| Constructible clips | YES | From track sequences |

**Assessment:** UA-DETRAC is a fixed-camera dataset. It cannot validate moving-camera geometry. It was used in the previous `real_kinematic_mvp` experiment as a 2D fallback, which explicitly does NOT validate the moving-camera direction.

---

## 5. BDD100K

**Status: AVAILABLE — 2D Only, No Video Sequences**

- Path: `/qiuyeqing/llama_prl/G-ARC/data/bdd100k/`
- 186,033 object annotations across images
- 2D bounding boxes with class labels

**What BDD100K provides:**
| Requirement | Available? | Notes |
|-------------|-----------|-------|
| Continuous frames | NO | Individual images, not video |
| Ego pose | NO | No ego motion data |
| Calibrated cameras | NO | No calibration |
| 3D boxes | NO | 2D only |
| Track/instance IDs | NO | No tracking |

**Assessment:** BDD100K cannot support any moving-camera queries.

---

## 6. DRIV100

**Status: AVAILABLE — Wrong Domain**

- Path: `/qiuyeqing/llama_prl/G-ARC/data/driv100/`
- 100 YouTube videos with semantic segmentation annotations
- No ego pose, no 3D boxes, no object tracking

**Assessment:** Not suitable for driving scene queries.

---

## Answers to Required Questions

### Q1: Is nuScenes mini available?
**NO.** No nuScenes data found anywhere under the project directory or the parent directory.

### Q2: Is Waymo sample available?
**NO.** No Waymo data found anywhere.

### Q3: Is there any dataset with ego pose + camera calibration + 3D boxes + instance tracks?
**NO.** The closest is KITTI raw, which has ego pose but lacks camera calibration and 3D object annotations. UA-DETRAC has tracks but no ego pose or 3D data.

### Q4: What exact data is missing?

To build a valid moving-camera query table, we need:
1. **nuScenes mini** (preferred) — provides all requirements
2. **Waymo Open Dataset** (alternative) — provides all requirements
3. **KITTI tracking benchmark** (partial) — would add 3D annotations to existing KITTI raw ego pose, but still needs calibration files

**What is locally available that could work with augmentation:**
- KITTI raw has ego pose + images + LiDAR. If we had:
  - Camera calibration files (calib_cam_to_cam.txt)
  - KITTI tracking labels (label_2/ directory)
  ...we could build the query table. But neither is available.

**What cannot work:**
- UA-DETRAC (fixed camera, no ego pose)
- BDD100K (no video, no ego pose)

---

## Recommendation

The feasibility study **cannot proceed** with real moving-camera geometry data. The required datasets (nuScenes, Waymo, or KITTI tracking with calibration) are not available locally.

**Options:**
1. **Download nuScenes mini** (~1GB) — would fully validate the direction
2. **Download KITTI tracking labels + calibration** (~10MB) — would partially validate using existing KITTI raw ego pose
3. **Accept the limitation** — report that the moving-camera direction cannot be validated with available data
