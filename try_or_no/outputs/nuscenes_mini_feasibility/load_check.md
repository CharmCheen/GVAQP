# nuScenes Mini Load Check

## Status: SUCCESS

```python
from nuscenes.nuscenes import NuScenes
nusc = NuScenes(version='v1.0-mini', dataroot='/qiuyeqing/llama_prl/G-ARC/data/nuscenes', verbose=True)
```

## Results

| Metric | Count |
|--------|-------|
| Scenes | 10 |
| Samples (keyframes) | 404 |
| Sample data records | 31,206 |
| Sample annotations | 18,538 |
| Instances | 911 |
| Categories | 23 |
| Attributes | 8 |
| Visibility levels | 4 |
| Sensors | 12 |
| Calibrated sensors | 120 |
| Ego poses | 31,206 |
| Maps | 4 |
| Logs | 8 |

## Camera Names

- CAM_FRONT
- CAM_FRONT_LEFT
- CAM_FRONT_RIGHT
- CAM_BACK
- CAM_BACK_LEFT
- CAM_BACK_RIGHT

## Ego Pose Access

```python
ego = nusc.get("ego_pose", cam_sd["ego_pose_token"])
# ego["translation"]: [x, y, z] in global frame
# ego["rotation"]: [w, x, y, z] quaternion
```

Verified: ego translation = [411.42, 1181.20, 0.0]

## Calibrated Sensor Access

```python
calib = nusc.get("calibrated_sensor", cam_sd["calibrated_sensor_token"])
# calib["camera_intrinsic"]: 3x3 matrix
# calib["translation"]: [x, y, z] relative to ego
# calib["rotation"]: [w, x, y, z] quaternion
```

Verified: calib translation = [1.70, 0.016, 1.51]

## Visibility Metadata

4 visibility levels available (token-based lookup via `nusc.get("visibility", token)`).

## Annotation Access

First sample has 69 annotations. Each annotation has:
- `translation`: [x, y, z] 3D box center in global frame
- `size`: [w, l, h] 3D box dimensions
- `rotation`: [w, x, y, z] quaternion
- `instance_token`: links to instance across frames
- `category_name`: object class
- `visibility_token`: visibility level
