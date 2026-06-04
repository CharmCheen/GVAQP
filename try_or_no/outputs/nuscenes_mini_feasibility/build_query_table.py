"""
Build real 3D query table from nuScenes mini.

Iterates over all scenes/samples/annotations, projects 3D boxes into CAM_FRONT,
computes ego-relative predicates (in_fov, within_30m, ego_front).
"""

import csv
import json
import math
import os
import sys

import numpy as np

# Add devkit to path
from nuscenes.nuscenes import NuScenes
from nuscenes.utils.geometry_utils import BoxVisibility, transform_matrix, view_points
from pyquaternion import Quaternion

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
DATAROOT = "/qiuyeqing/llama_prl/G-ARC/data/nuscenes"


def yaw_from_quat(qw, qx, qy, qz):
    """Extract yaw angle from quaternion."""
    # yaw (z-axis rotation)
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return math.atan2(siny_cosp, cosy_cosp)


def main():
    print("Loading nuScenes v1.0-mini...")
    nusc = NuScenes(version="v1.0-mini", dataroot=DATAROOT, verbose=True)

    rows = []
    row_id = 0

    for scene in nusc.scene:
        scene_token = scene["token"]
        scene_name = scene["name"]

        sample_token = scene["first_sample_token"]
        while sample_token:
            sample = nusc.get("sample", sample_token)
            timestamp = sample["timestamp"]

            # Get CAM_FRONT sample_data
            cam_token = sample["data"]["CAM_FRONT"]
            cam_sd = nusc.get("sample_data", cam_token)

            # Get ego pose at camera timestamp
            ego = nusc.get("ego_pose", cam_sd["ego_pose_token"])
            ego_x, ego_y, ego_z = ego["translation"]
            ego_q = Quaternion(ego["rotation"])
            ego_yaw = yaw_from_quat(ego_q.w, ego_q.x, ego_q.y, ego_q.z)

            # Get calibrated sensor
            calib = nusc.get("calibrated_sensor", cam_sd["calibrated_sensor_token"])
            cam_intrinsic = np.array(calib["camera_intrinsic"])  # 3x3
            cam_translation = np.array(calib["translation"])
            cam_rotation = Quaternion(calib["rotation"])

            # Build transform matrices for projection
            # ego_from_sensor: sensor -> ego
            ego_from_sensor = transform_matrix(
                cam_translation, cam_rotation, inverse=False
            )
            # global_from_ego: ego -> global
            global_from_ego = transform_matrix(
                ego["translation"], ego_q, inverse=False
            )
            # sensor_from_global: global -> sensor
            sensor_from_global = np.linalg.inv(
                global_from_ego @ ego_from_sensor
            )

            # Process each annotation
            for ann_token in sample["anns"]:
                ann = nusc.get("sample_annotation", ann_token)
                instance_token = ann["instance_token"]
                category = ann["category_name"]
                visibility_token = ann["visibility_token"]

                # Object position (3D box center in global frame)
                obj_x, obj_y, obj_z = ann["translation"]

                # Object position in ego frame
                global_from_ego_mat = transform_matrix(
                    ego["translation"], ego_q, inverse=False
                )
                ego_from_global = np.linalg.inv(global_from_ego_mat)
                obj_global = np.array([obj_x, obj_y, obj_z, 1.0])
                obj_in_ego = ego_from_global @ obj_global
                obj_rel_x = obj_in_ego[0]
                obj_rel_y = obj_in_ego[1]
                obj_rel_z = obj_in_ego[2]

                # Distance to ego (in ego frame)
                dist = math.sqrt(obj_rel_x ** 2 + obj_rel_y ** 2 + obj_rel_z ** 2)

                # ego_front_label: object in front of ego, reasonable lateral range
                ego_front = 1 if (obj_rel_x > 0 and abs(obj_rel_y) <= 10.0) else 0

                # within_30m_label
                within_30m = 1 if dist <= 30.0 else 0

                # Project into CAM_FRONT
                # Transform object center from global to sensor frame
                obj_in_sensor = sensor_from_global @ obj_global
                depth = obj_in_sensor[2]

                # Project using camera intrinsic
                if depth > 0:
                    projected = cam_intrinsic @ obj_in_sensor[:3]
                    proj_x = projected[0] / projected[2]
                    proj_y = projected[1] / projected[2]

                    # Check image bounds (1600x900 for nuScenes cameras)
                    img_w, img_h = 1600, 900
                    in_fov = 1 if (0 <= proj_x <= img_w and 0 <= proj_y <= img_h) else 0
                else:
                    proj_x = -1.0
                    proj_y = -1.0
                    in_fov = 0

                is_valid = 1 if depth > 0 else 0

                rows.append({
                    "id": row_id,
                    "scene_token": scene_token,
                    "scene_name": scene_name,
                    "sample_token": sample_token,
                    "timestamp": timestamp,
                    "camera_name": "CAM_FRONT",
                    "instance_token": instance_token,
                    "annotation_token": ann_token,
                    "category_name": category,
                    "visibility_token": visibility_token,
                    "ego_x": round(ego_x, 4),
                    "ego_y": round(ego_y, 4),
                    "ego_z": round(ego_z, 4),
                    "ego_yaw": round(ego_yaw, 6),
                    "obj_x": round(obj_x, 4),
                    "obj_y": round(obj_y, 4),
                    "obj_z": round(obj_z, 4),
                    "obj_distance_to_ego": round(dist, 4),
                    "obj_rel_x_ego": round(obj_rel_x, 4),
                    "obj_rel_y_ego": round(obj_rel_y, 4),
                    "obj_rel_z_ego": round(obj_rel_z, 4),
                    "in_fov_label": in_fov,
                    "within_30m_label": within_30m,
                    "ego_front_label": ego_front,
                    "projected_center_x": round(proj_x, 2),
                    "projected_center_y": round(proj_y, 2),
                    "projected_depth": round(depth, 4),
                    "is_valid": is_valid,
                })
                row_id += 1

            # Next sample
            sample_token = sample["next"]

    # Write CSV
    out_path = os.path.join(OUTPUT_DIR, "real_3d_query_table.csv")
    fieldnames = [
        "id", "scene_token", "scene_name", "sample_token", "timestamp",
        "camera_name", "instance_token", "annotation_token", "category_name",
        "visibility_token", "ego_x", "ego_y", "ego_z", "ego_yaw",
        "obj_x", "obj_y", "obj_z", "obj_distance_to_ego",
        "obj_rel_x_ego", "obj_rel_y_ego", "obj_rel_z_ego",
        "in_fov_label", "within_30m_label", "ego_front_label",
        "projected_center_x", "projected_center_y", "projected_depth",
        "is_valid",
    ]

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to {out_path}")

    # Print summary stats
    n_valid = sum(1 for r in rows if r["is_valid"] == 1)
    n_in_fov = sum(1 for r in rows if r["in_fov_label"] == 1)
    n_within_30m = sum(1 for r in rows if r["within_30m_label"] == 1)
    n_ego_front = sum(1 for r in rows if r["ego_front_label"] == 1)
    n_instances = len(set(r["instance_token"] for r in rows))
    n_scenes = len(set(r["scene_token"] for r in rows))
    n_samples = len(set(r["sample_token"] for r in rows))

    print(f"\nSummary:")
    print(f"  Total records: {len(rows)}")
    print(f"  Valid (depth>0): {n_valid}")
    print(f"  In FOV: {n_in_fov} ({n_in_fov/len(rows)*100:.1f}%)")
    print(f"  Within 30m: {n_within_30m} ({n_within_30m/len(rows)*100:.1f}%)")
    print(f"  Ego front: {n_ego_front} ({n_ego_front/len(rows)*100:.1f}%)")
    print(f"  Instances: {n_instances}")
    print(f"  Scenes: {n_scenes}")
    print(f"  Samples: {n_samples}")


if __name__ == "__main__":
    main()
