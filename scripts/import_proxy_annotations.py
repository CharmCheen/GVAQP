#!/usr/bin/env python3
"""
Import and validate human annotations for H-PROXY1.

Reads COCO detection annotations, MOT tracking CSVs, and lane GeoJSON files.
Validates schema compliance, coordinate ranges, track continuity, and cross-references.

Usage:
  python scripts/import_proxy_annotations.py detection  --input path/to/coco.json
  python scripts/import_proxy_annotations.py tracking   --input-dir path/to/tracking/
  python scripts/import_proxy_annotations.py lane        --input-dir path/to/lane/
  python scripts/import_proxy_annotations.py validate    --all
"""

import sys, os, json, argparse
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs/proxy_frontend_comparison_v0"
ANNO_DIR = OUTPUT_DIR / "annotations"
IMPORT_DIR = ANNO_DIR / "imports"

CLASS_NAMES = {0: "car", 1: "truck", 2: "bus", 3: "motorcycle", 4: "bicycle", 5: "person"}
VALID_CLASSES = set(CLASS_NAMES.keys())
VALID_TRACK_STATES = {"active", "occluded", "out_of_view", "stationary", "ambiguous"}
VALID_VISIBILITY = {"clear", "partial", "unavailable"}
VALID_SCENE_TYPES = {"straight", "curve_left", "curve_right", "intersection", "merge", "tunnel", "other"}


def validate_detection_annotations(coco_path):
    """Validate detection annotations in COCO JSON format."""
    print(f"Validating detection annotations: {coco_path}")
    with open(coco_path) as f:
        data = json.load(f)

    errors = []
    warnings = []

    # Required top-level keys
    for key in ["images", "annotations", "categories"]:
        if key not in data:
            errors.append(f"Missing top-level key: {key}")

    if errors:
        return errors, warnings

    # Validate images
    image_ids = set()
    frame_keys = set()
    for img in data["images"]:
        if "id" not in img:
            errors.append(f"Image missing 'id'")
            continue
        image_ids.add(img["id"])
        
        wid = img.get("width", 0)
        hei = img.get("height", 0)
        if wid != 1920 or hei != 1080:
            warnings.append(f"Image {img['id']}: unexpected dimensions {wid}x{hei} (expected 1920x1080)")
        
        fidx = img.get("frame_index")
        cid = img.get("clip_id")
        if fidx is None or cid is None:
            errors.append(f"Image {img['id']}: missing frame_index or clip_id")
        else:
            frame_keys.add((cid, fidx))

    # Validate annotations
    seen_ann_ids = set()
    for ann in data["annotations"]:
        aid = ann.get("id")
        if aid is None:
            errors.append("Annotation missing 'id'")
            continue
        if aid in seen_ann_ids:
            errors.append(f"Duplicate annotation id: {aid}")
        seen_ann_ids.add(aid)

        img_id = ann.get("image_id")
        if img_id not in image_ids:
            errors.append(f"Annotation {aid}: image_id {img_id} not in images")

        cat_id = ann.get("category_id")
        if cat_id not in VALID_CLASSES:
            errors.append(f"Annotation {aid}: invalid category_id {cat_id} (valid: {VALID_CLASSES})")

        bbox = ann.get("bbox")
        if bbox is None or len(bbox) != 4:
            errors.append(f"Annotation {aid}: invalid bbox")
        else:
            x, y, w, h = bbox
            if x < 0 or y < 0 or w <= 0 or h <= 0:
                errors.append(f"Annotation {aid}: bbox out of bounds: {bbox}")
            if x + w > 1920 or y + h > 1080:
                warnings.append(f"Annotation {aid}: bbox extends beyond frame: {bbox}")

        attrs = ann.get("attributes", {})
        for attr in ["small_or_distant", "partially_occluded", "adjacent_lane", "near_ego_path", "interaction_relevant"]:
            if attr not in attrs:
                warnings.append(f"Annotation {aid}: missing attribute '{attr}'")

    # Check frame coverage against manifest
    manifest_path = ANNO_DIR / "SAMPLE_MANIFEST.csv"
    if manifest_path.exists():
        manifest = pd.read_csv(manifest_path)
        det_frames = manifest[manifest["task_type"].str.contains("detection")]
        manifest_keys = set(zip(det_frames["clip_id"], det_frames["frame_index"]))
        missing = manifest_keys - frame_keys
        extra = frame_keys - manifest_keys
        if missing:
            warnings.append(f"{len(missing)} frames in manifest not in annotations")
        if extra:
            warnings.append(f"{len(extra)} frames in annotations not in manifest")

    # Summary
    print(f"  Images: {len(data['images'])}")
    print(f"  Annotations: {len(data['annotations'])}")
    print(f"  Categories: {len(data['categories'])}")
    print(f"  Errors: {len(errors)}")
    print(f"  Warnings: {len(warnings)}")

    for e in errors[:10]:
        print(f"    ERROR: {e}")
    for w in warnings[:10]:
        print(f"    WARNING: {w}")

    return errors, warnings


def validate_tracking_annotations(tracking_dir):
    """Validate tracking annotations in MOT CSV format."""
    print(f"Validating tracking annotations: {tracking_dir}")
    tracking_dir = Path(tracking_dir)
    errors = []
    warnings = []

    csv_files = sorted(tracking_dir.glob("gt_tracks_*.csv"))
    if not csv_files:
        errors.append(f"No gt_tracks_*.csv files found in {tracking_dir}")
        return errors, warnings

    for csv_path in csv_files:
        clip_id = csv_path.stem.replace("gt_tracks_", "")
        print(f"\n  Clip: {clip_id}")
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            errors.append(f"{csv_path}: read error: {e}")
            continue

        required_cols = ["frame_index", "track_id", "x1", "y1", "x2", "y2"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            errors.append(f"{clip_id}: missing columns: {missing_cols}")
            continue

        # Check coordinate bounds
        for col in ["x1", "x2"]:
            oob = df[(df[col] < 0) | (df[col] > 1920)]
            if len(oob) > 0:
                errors.append(f"{clip_id}: {len(oob)} boxes with x oob")
        for col in ["y1", "y2"]:
            oob = df[(df[col] < 0) | (df[col] > 1080)]
            if len(oob) > 0:
                errors.append(f"{clip_id}: {len(oob)} boxes with y oob")

        # Check box validity
        invalid = df[(df["x2"] <= df["x1"]) | (df["y2"] <= df["y1"])]
        if len(invalid) > 0:
            errors.append(f"{clip_id}: {len(invalid)} invalid boxes (x2<=x1 or y2<=y1)")

        # Track continuity: frames should be monotonic per track
        for tid, grp in df.groupby("track_id"):
            frames = sorted(grp["frame_index"].unique())
            if len(frames) < 2:
                warnings.append(f"{clip_id}: track {tid} has only 1 frame")
                continue
            # Check for gaps
            gaps = np.diff(frames)
            max_gap = gaps.max()
            if max_gap > 10:  # > 2 seconds at 5fps
                warnings.append(f"{clip_id}: track {tid} has max gap of {max_gap} frames")

        # Class IDs
        if "class_id" in df.columns:
            invalid_class = df[~df["class_id"].isin(list(VALID_CLASSES) + [-1])]
            if len(invalid_class) > 0:
                warnings.append(f"{clip_id}: {len(invalid_class)} boxes with invalid class_id")

        # Track states
        if "track_state" in df.columns:
            invalid_state = df[~df["track_state"].isin(VALID_TRACK_STATES)]
            if len(invalid_state) > 0:
                warnings.append(f"{clip_id}: {len(invalid_state)} boxes with invalid track_state")

        print(f"    Tracks: {df['track_id'].nunique()}")
        print(f"    Frames: {df['frame_index'].nunique()}")
        print(f"    Boxes: {len(df)}")

    print(f"\n  Total errors: {len(errors)}, warnings: {len(warnings)}")
    for e in errors[:10]:
        print(f"    ERROR: {e}")
    return errors, warnings


def validate_lane_annotations(lane_dir):
    """Validate lane annotations in GeoJSON format."""
    print(f"Validating lane annotations: {lane_dir}")
    lane_dir = Path(lane_dir)
    errors = []
    warnings = []

    json_files = sorted(lane_dir.glob("lane_gt_*.json"))
    if not json_files:
        errors.append(f"No lane_gt_*.json files found in {lane_dir}")
        return errors, warnings

    for jf in json_files:
        try:
            with open(jf) as f:
                data = json.load(f)
        except Exception as e:
            errors.append(f"{jf.name}: read error: {e}")
            continue

        fidx = data.get("frame_index")
        if fidx is None:
            errors.append(f"{jf.name}: missing frame_index")
            continue

        # Check boundaries
        for side in ["left_boundary", "right_boundary"]:
            boundary = data.get(side, {})
            coords = boundary.get("coordinates", [])
            if len(coords) < 3:
                errors.append(f"{jf.name}: {side} has < 3 points ({len(coords)})")
                continue
            for i, (x, y) in enumerate(coords):
                if x < 0 or x > 1920 or y < 0 or y > 1080:
                    errors.append(f"{jf.name}: {side} point {i} out of bounds ({x},{y})")

        # Visibility
        vis = data.get("lane_visibility", "")
        if vis not in VALID_VISIBILITY:
            errors.append(f"{jf.name}: invalid lane_visibility '{vis}'")

        # Scene type
        st = data.get("scene_type", "")
        if st not in VALID_SCENE_TYPES and st != "TO_BE_DETERMINED":
            warnings.append(f"{jf.name}: unrecognized scene_type '{st}'")

    print(f"  Files: {len(json_files)}")
    print(f"  Errors: {len(errors)}, Warnings: {len(warnings)}")
    for e in errors[:10]:
        print(f"    ERROR: {e}")
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Import & Validate H-PROXY1 Annotations")
    parser.add_argument("command", choices=["detection", "tracking", "lane", "validate"])
    parser.add_argument("--input", type=str, help="Path to COCO JSON (detection)")
    parser.add_argument("--input-dir", type=str, help="Path to annotation directory (tracking/lane)")
    parser.add_argument("--all", action="store_true", help="Validate all annotation types using default paths")
    args = parser.parse_args()

    IMPORT_DIR.mkdir(parents=True, exist_ok=True)

    all_errors = []
    all_warnings = []

    if args.command == "validate" or args.all:
        # Detection
        det_path = args.input or str(ANNO_DIR / "tasks/detection/detection_tasks.json")
        if Path(det_path).exists():
            e, w = validate_detection_annotations(det_path)
            all_errors.extend(e); all_warnings.extend(w)
        else:
            print(f"Detection annotations not found at {det_path}")

        # Tracking
        trk_dir = args.input_dir or str(ANNO_DIR / "tasks/tracking")
        if Path(trk_dir).exists():
            e, w = validate_tracking_annotations(trk_dir)
            all_errors.extend(e); all_warnings.extend(w)

        # Lane
        lane_dir = str(ANNO_DIR / "tasks/lane")
        if Path(lane_dir).exists():
            e, w = validate_lane_annotations(lane_dir)
            all_errors.extend(e); all_warnings.extend(w)

    elif args.command == "detection":
        det_path = args.input or str(ANNO_DIR / "tasks/detection/detection_tasks.json")
        all_errors, all_warnings = validate_detection_annotations(det_path)

    elif args.command == "tracking":
        trk_dir = args.input_dir or str(ANNO_DIR / "tasks/tracking")
        all_errors, all_warnings = validate_tracking_annotations(trk_dir)

    elif args.command == "lane":
        lane_dir = args.input_dir or str(ANNO_DIR / "tasks/lane")
        all_errors, all_warnings = validate_lane_annotations(lane_dir)

    # Summary
    print("\n" + "=" * 60)
    if all_errors:
        print(f"VALIDATION FAILED: {len(all_errors)} errors")
        sys.exit(1)
    else:
        print(f"VALIDATION PASSED: {len(all_warnings)} warnings (non-blocking)")
        sys.exit(0)


if __name__ == "__main__":
    main()
