# nuScenes Mini Download Status

## Download Result: SUCCESS

- URL: https://www.nuscenes.org/data/v1.0-mini.tgz
- File: v1.0-mini.tgz (4,167,696,325 bytes = ~3.9 GB)
- Download time: ~4 minutes at ~16.6 MB/s
- File type: gzip compressed tar (verified)
- Extraction: successful

## Directory Structure

```
/qiuyeqing/llama_prl/G-ARC/data/nuscenes/
├── maps/
├── samples/
│   ├── CAM_BACK/
│   ├── CAM_BACK_LEFT/
│   ├── CAM_BACK_RIGHT/
│   ├── CAM_FRONT/
│   ├── CAM_FRONT_LEFT/
│   ├── CAM_FRONT_RIGHT/
│   ├── LIDAR_TOP/
│   └── RADAR_*/
├── sweeps/
└── v1.0-mini/
```

## Devkit Load Verification

Successfully loaded with:
```python
NuScenes(version='v1.0-mini', dataroot='/qiuyeqing/llama_prl/G-ARC/data/nuscenes', verbose=True)
```

Results:
- 10 scenes
- 404 keyframe samples
- 31,206 sample_data records
- 18,538 sample_annotations
- 6 cameras: CAM_FRONT, CAM_FRONT_RIGHT, CAM_BACK_RIGHT, CAM_BACK, CAM_BACK_LEFT, CAM_FRONT_LEFT
- ego_pose: accessible
- calibrated_sensor: accessible
- 4 visibility levels
