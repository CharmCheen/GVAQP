# Local nuScenes Mini Inventory

## Search Results

Searched the following paths for nuScenes mini data:

| Path | nuScenes v1.0-mini found? |
|------|--------------------------|
| /qiuyeqing/llama_prl/G-ARC | NO |
| /qiuyeqing/llama_prl | NO |
| /data/sets/nuscenes | Directory does not exist |
| /data/nuscenes | Directory does not exist |
| /datasets/nuscenes | Directory does not exist |
| /mnt/data/nuscenes | Directory does not exist |
| ./data/nuscenes | Directory does not exist |
| ./datasets/nuscenes | Directory does not exist |

Also searched:
- Global `find / -name "v1.0-mini" -type d` — no results
- Global `find / -name "nuscenes" -type d` — no results
- Global `find / -name "*.json" -path "*nuscenes*"` — no results

## Existing Datasets (Not nuScenes)

The following datasets exist locally but do NOT satisfy the moving-camera requirements:

| Dataset | Path | Ego Pose | Calibrated Cam | 3D Boxes | Tracks |
|---------|------|----------|----------------|----------|--------|
| KITTI Raw | data/kitti_raw/ | YES (OXTS) | NO (missing calib files) | NO (no annotations) | NO |
| UA-DETRAC | data/ua_detrac/ | NO (fixed cam) | NO | 2D only | YES |
| BDD100K | data/bdd100k/ | NO | NO | 2D only | NO |

## Answer: Is nuScenes mini available locally?

**NO.** nuScenes mini does not exist anywhere on this system.

No v1.0-mini directory, no samples/CAM_FRONT, no metadata JSON files, no map files were found.
