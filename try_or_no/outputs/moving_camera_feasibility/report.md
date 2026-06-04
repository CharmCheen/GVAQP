# Moving-Camera Feasibility Report

## 1. Which real moving-camera dataset was used?

**None.** No suitable moving-camera geometry dataset is available locally.

## 2. What exact paths were read?

- `/qiuyeqing/llama_prl/G-ARC/data/` — scanned all subdirectories
- `/qiuyeqing/llama_prl/G-ARC/data/kitti_raw/` — 4 KITTI raw driving sequences
- `/qiuyeqing/llama_prl/G-ARC/data/kitti_raw/2011_09_26_drive_0005_sync.zip` — checked contents for calibration files
- `/qiuyeqing/llama_prl/G-ARC/data/ua_detrac/` — UA-DETRAC fixed-camera data
- `/qiuyeqing/llama_prl/G-ARC/data/bdd100k/` — BDD100K 2D annotations
- `/qiuyeqing/llama_prl/` — searched for nuScenes and Waymo data

## 3. How many scenes, frames, samples, objects, tracks, and clips were used?

**Zero.** No dataset was used because no dataset satisfies the minimum requirements for moving-camera geometry validation.

## 4. Does the dataset satisfy the six minimum requirements?

### Available datasets and their capabilities:

| Requirement | KITTI Raw | UA-DETRAC | BDD100K |
|-------------|-----------|-----------|---------|
| Ego pose | YES (OXTS) | NO (fixed camera) | NO |
| Calibrated camera | NO (missing files) | NO | NO |
| 3D boxes / tracks | NO (no annotations) | 2D only | 2D only |
| Definable in_fov | NO | 2D proxy only | NO |
| Definable within_30m | NO | NO | NO |
| Definable ego_front | NO | 2D proxy only | NO |
| Constructible clips | NO | YES | NO |
| Runnable baselines | NO | YES (2D only) | NO |

### KITTI Raw (closest candidate):
- **Has:** ego pose (OXTS with lat/lon/alt/roll/pitch/yaw), camera images, LiDAR, timestamps
- **Missing:** Camera calibration files (calib_cam_to_cam.txt, calib_imu_to_velo.txt), 3D object annotations (KITTI tracking labels)
- **Assessment:** Cannot build query table. Ego pose alone is insufficient without objects to track and calibration to project them.

### UA-DETRAC (used in previous experiment):
- **Has:** 2D bounding boxes, instance tracks, video sequences
- **Missing:** Ego pose, camera calibration, 3D data
- **Assessment:** Fixed-camera only. The previous `real_kinematic_mvp` experiment used this as a 2D fallback, which explicitly does NOT validate the moving-camera direction.

### BDD100K:
- **Has:** 2D bounding boxes, class labels
- **Missing:** Video sequences, ego pose, calibration, 3D data, tracks
- **Assessment:** Individual images only. Cannot support temporal queries.

**Answer: NO dataset satisfies the six minimum requirements.**

## 5-13. Remaining Questions

Since no suitable dataset is available, the remaining questions cannot be answered:

- How were oracle states derived? **N/A — no data**
- How were query labels derived? **N/A — no data**
- Which queries were evaluated? **N/A — no data**
- Which baselines were implemented? **N/A — no data**
- Does query-impact-aware triggering beat baselines? **N/A — no data**
- Does it reduce boundary error? **N/A — no data**
- What is the best cost-quality tradeoff? **N/A — no data**
- Is the advantage visible on real moving-camera data? **N/A — no data**
- Is this direction strong enough to continue? **Cannot assess without data**

## Critical Gap Analysis

The moving-camera direction requires ego-relative geometric predicates:
- `in_fov(target)`: needs camera intrinsics + 3D object position
- `within_distance(target, ego, D)`: needs ego pose + 3D object position
- `in_ego_front_region(target)`: needs ego pose + 3D object position in ego frame

**What is missing locally:**
1. **nuScenes mini** (~1GB) — would provide all requirements
2. **Waymo Open Dataset** — would provide all requirements
3. **KITTI tracking labels + calibration** (~10MB) — would augment existing KITTI raw ego pose

**What cannot be done:**
- Build a valid 3D query table without 3D annotations
- Derive in_fov without camera calibration
- Derive within_30m without 3D object positions
- Validate moving-camera geometry with fixed-camera data

## What Was Previously Attempted

The `real_kinematic_mvp` experiment used UA-DETRAC (fixed camera, 2D boxes) to test temporal prediction and clip construction. This experiment:
- Used 2D image-space predicates (in_image, in_front) instead of ego-relative 3D predicates
- Did not involve ego motion
- Was explicitly labeled as "2D fallback" that does not validate the moving-camera direction

## Final Judgment

**NO-GO**

No suitable moving-camera geometry data is available locally. The datasets that exist (KITTI raw, UA-DETRAC, BDD100K) lack either ego pose, camera calibration, or 3D object annotations — or some combination of all three.

**The moving-camera research direction cannot be validated with available data.**

## Options to Proceed

1. **Download nuScenes mini** (~1GB) — would fully validate the direction
   - nuScenes provides: ego pose, calibrated cameras, 3D boxes with instance tracks, timestamps, visibility, category labels
   - This is the minimum viable dataset for the proposed research

2. **Download KITTI tracking benchmark + calibration** (~10MB) — would partially validate
   - Existing KITTI raw ego pose could be combined with tracking labels
   - Limited to 4 sequences but would demonstrate feasibility

3. **Abandon the moving-camera direction** — if data acquisition is not possible

4. **Pivot to a different formulation** — e.g., fixed-camera temporal AQP (already tested in real_kinematic_mvp) or synthetic validation with realistic parameters

## Recommendation

Option 1 (download nuScenes mini) is the clearest path forward. The dataset is small (~1GB), well-documented, and directly supports all required predicates. Without it, the moving-camera direction remains unvalidated and should not be pursued as the main research topic.
