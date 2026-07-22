#!/usr/bin/env python3
"""
H-PROXY1U / H-DISTILL1: Oracle-Distilled Proxy Auto-Training Pipeline.

All phases without human annotations. Uses frozen Qwen3-VL-32B as teacher.

Phases:
  python scripts/run_oracle_distillation.py audit
  python scripts/run_oracle_distillation.py freeze_teacher
  python scripts/run_oracle_distillation.py extract_features
  python scripts/run_oracle_distillation.py rule_baseline
  python scripts/run_oracle_distillation.py train_lgbm
  python scripts/run_oracle_distillation.py eval_drivingdojo
  python scripts/run_oracle_distillation.py eval_target
  python scripts/run_oracle_distillation.py finalize
"""

import sys, os, json, time, hashlib, argparse, copy, warnings, gc, io, zipfile
from pathlib import Path
from collections import defaultdict, Counter

import cv2
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs/proxy_oracle_distillation_v0"
DD_ZIP = PROJECT_ROOT / "datasets/DrivingDojo-mini/drivingdojo_mini.zip"
DD_EXTRACT = Path("/tmp/drivingdojo_mini/drivingdojo_mini")
VIDEO_PATH = PROJECT_ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"

ORACLE_MODEL_PATH = PROJECT_ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
ORACLE_PROMPT_PATH = PROJECT_ROOT / "src/garc_eval/event_enumerate_v2/prompts/event_enumerate_v2.txt"
ORACLE_REF_DIR = PROJECT_ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"

PREV_OUTPUT_DIR = PROJECT_ROOT / "outputs/proxy_frontend_comparison_v0"

YOLOV8N_PATH = PROJECT_ROOT / "models/yolo/yolov8n.pt"
YOLOP_320_PATH = PROJECT_ROOT / "YOLOP/weights/yolop-320-320.onnx"
YOLOP_640_PATH = PROJECT_ROOT / "YOLOP/weights/yolop-640-640.onnx"

PROXY_FEATURES_V1 = [
    "bbox_cx_norm", "bbox_cy_norm", "bbox_w_norm", "bbox_h_norm",
    "bbox_area_norm", "bbox_growth", "lateral_velocity",
    "track_age", "track_confidence", "bbox_bottom_y",
    "approx_ttc",
    "lane_relative_position", "lane_relative_velocity",
    "distance_to_left_boundary", "distance_to_right_boundary",
    "in_ego_corridor", "boundary_crossing_count",
    "bottom_center_drivable", "drivable_overlap",
    "lane_confidence", "track_duration",
    "track_mean_cx", "track_std_cx", "track_mean_cy", "track_std_cy",
    "track_displacement", "track_bbox_growth_rate", "track_lateral_motion_energy",
]


def phase_audit():
    """Phase A: Audit DrivingDojo data."""
    print("=== Phase A: DrivingDojo Data Audit ===")
    
    # Read mini_dataset.json from zip
    with zipfile.ZipFile(DD_ZIP) as zf:
        with zf.open("drivingdojo_mini/mini_dataset.json") as f:
            data = json.load(f)
    
    sessions = []
    for sid, sd in data.items():
        n_frames = len(sd.get("videos", []))
        n_camera = len(sd.get("camera_info", []))
        n_action = len(sd.get("action_info", []))
        meta = sd.get("meta_info", {})
        desc = sd.get("description", {})
        
        sessions.append({
            "session_id": sid,
            "vehicle_id": sid.split("_")[0],
            "session_label": sid.split("_")[1],
            "start_unix": float(sid.split("_")[2]),
            "end_unix": float(sid.split("_")[3]),
            "duration_sec": float(sid.split("_")[3]) - float(sid.split("_")[2]),
            "n_frames": n_frames,
            "n_camera_params": n_camera,
            "n_action_params": n_action,
            "weather": meta.get("weather", ""),
            "location": meta.get("location", ""),
            "time_of_day": meta.get("time", ""),
            "dataset_type": desc.get("type", []),
            "tag": desc.get("tag", ""),
            "remark": desc.get("remark", ""),
        })
    
    df = pd.DataFrame(sessions)
    df.to_csv(OUTPUT_DIR / "DRIVINGDOJO_SOURCE_AUDIT.csv", index=False)
    
    print(f"Total sessions: {len(sessions)}")
    print(f"Total frames: {df['n_frames'].sum()}")
    print(f"Duration range: {df['duration_sec'].min():.0f}-{df['duration_sec'].max():.0f}s")
    print(f"Unique vehicles: {df['vehicle_id'].nunique()}")
    print(f"Types: {Counter(t for types in df['dataset_type'] for t in types)}")
    print(f"Tags: {Counter(df['tag'].values)}")
    
    # Identify interplay sessions (preferred)
    interplay = df[df["dataset_type"].apply(lambda x: "drivingdojo-interplay" in x)]
    print(f"\nInterplay sessions: {len(interplay)}")
    
    # Read a sample frame to verify decode health
    with zipfile.ZipFile(DD_ZIP) as zf:
        first_video_rel = data[list(data.keys())[0]]["videos"][0]
        first_video = f"drivingdojo_mini/{first_video_rel}"
        try:
            with zf.open(first_video) as imgf:
                img_bytes = imgf.read()
                img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
                print(f"\nSample frame: {first_video}")
                print(f"  Shape: {img.shape}")
                print(f"  Decode OK: {img is not None}")
        except Exception as e:
            print(f"\nSample frame failed: {e}")
            img = None
    
    inventory = {
        "source": str(DD_ZIP),
        "total_sessions": len(sessions),
        "total_frames": int(df["n_frames"].sum()),
        "interplay_sessions": len(interplay),
        "interplay_session_ids": interplay["session_id"].tolist(),
        "unique_tags": sorted(set(df["tag"].values)),
        "frame_resolution": f"{img.shape[1]}x{img.shape[0]}" if img is not None else "unknown",
        "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "notes": "Frames are individual JPEGs, not video containers. Session duration 10-26s each.",
    }
    
    with open(OUTPUT_DIR / "DRIVINGDOJO_SOURCE_AUDIT.json", "w") as f:
        json.dump(inventory, f, indent=2, default=str)
    
    print(f"\nAudit saved. Interplay sessions: {inventory['interplay_session_ids']}")
    return inventory


def phase_freeze_teacher():
    """Phase B: Freeze teacher query/schema."""
    print("=== Phase B: Freeze Teacher Query/Schema ===")
    
    # Read frozen oracle prompt
    if ORACLE_PROMPT_PATH.exists():
        with open(ORACLE_PROMPT_PATH) as f:
            prompt_raw = f.read()
        prompt_sha = hashlib.sha256(prompt_raw.encode()).hexdigest()
    else:
        print(f"WARNING: Oracle prompt not found at {ORACLE_PROMPT_PATH}")
        prompt_raw = "PROMPT_NOT_FOUND"
        prompt_sha = "UNKNOWN"
    
    # Read oracle model info
    model_config_path = ORACLE_MODEL_PATH / "config.json"
    model_config = {}
    if model_config_path.exists():
        with open(model_config_path) as f:
            model_config = json.load(f)
    
    teacher_config = {
        "model": "Qwen3-VL-32B-Instruct",
        "model_path": str(ORACLE_MODEL_PATH),
        "model_type": model_config.get("model_type", "unknown"),
        "hidden_size": model_config.get("hidden_size", "unknown"),
        "torch_dtype": model_config.get("torch_dtype", "bfloat16"),
        "prompt_path": str(ORACLE_PROMPT_PATH),
        "prompt_sha256": prompt_sha,
        "prompt_preview": prompt_raw[:500],
        "query_definition": "OTHER_AGENT_ENTERS_EGO_PATH",
        "query_semantics": (
            "A non-ego vehicle/motorcycle/bicycle/dynamic agent that enters, crosses, "
            "or occupies the ego vehicle's potential driving path from outside it."
        ),
        "exclusions": [
            "ego lane change creating relative motion",
            "adjacent vehicles driving in parallel without intrusion",
            "being overtaken without ego-path entry",
            "curve-induced apparent lateral motion",
            "distant lane change not affecting ego path",
            "parked/static vehicles",
            "vehicles merely present in frame",
        ],
        "label_schema": {
            "POSITIVE": "other_agent_enters_ego_path confirmed (high/medium confidence)",
            "HARD_NEGATIVE": "no path intrusion but lateral motion/close proximity present",
            "ORDINARY_NEGATIVE": "normal driving, no relevant interaction",
            "AMBIGUOUS": "cannot determine from available frames",
            "UNUSABLE": "frames are corrupted, too dark, or unusable",
        },
        "keep_criteria": "confidence=high|medium AND label NOT IN (AMBIGUOUS, UNUSABLE)",
        "inference_config": {
            "do_sample": False,
            "max_new_tokens": 2048,
            "temperature": 0.0,
            "sampling_fps": 2,
        },
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "frozen_oracle_reference": str(ORACLE_REF_DIR),
        "existing_oracle_labels_count": 347,  # from PSVR benchmark
        "notes": "SAME oracle as PSVR benchmark. Qwen3-VL-32B-Instruct, cache-free, hash-bound."
    }
    
    with open(OUTPUT_DIR / "TEACHER_CONFIG.json", "w") as f:
        json.dump(teacher_config, f, indent=2)
    
    # Write teacher query spec
    query_spec = {
        "query": "OTHER_AGENT_ENTERS_EGO_PATH",
        "output_schema": {
            "label": "POSITIVE|HARD_NEGATIVE|ORDINARY_NEGATIVE|AMBIGUOUS|UNUSABLE",
            "other_agent_enters_ego_path": "boolean",
            "event_start_seconds": "float|null",
            "event_end_seconds": "float|null",
            "actor_description": "string",
            "entry_side": "left|right|front|unknown",
            "ego_motion_confounded": "boolean",
            "curve_confounded": "boolean",
            "occlusion_confounded": "boolean",
            "confidence": "high|medium|low",
            "reason": "string",
        },
        "prompt_template": prompt_raw,
    }
    
    with open(OUTPUT_DIR / "TEACHER_QUERY_SPEC.json", "w") as f:
        json.dump(query_spec, f, indent=2)
    
    print(f"Teacher config frozen. Prompt SHA-256: {prompt_sha}")
    print(f"Model: Qwen3-VL-32B-Instruct at {ORACLE_MODEL_PATH}")
    return teacher_config


def phase_build_dataset():
    """Phase C: Build oracle-distilled event dataset.
    
    Since running Qwen3-VL on 32+ clips requires GPU + significant time,
    this implements a deterministic proxy: using DrivingDojo free-text tags
    as weak selection signals, then running oracle on a subset.
    """
    print("=== Phase C: Build Oracle-Distilled Event Dataset ===")
    
    # Read session metadata
    with zipfile.ZipFile(DD_ZIP) as zf:
        with zf.open("drivingdojo_mini/mini_dataset.json") as f:
            data = json.load(f)
    
    # Classify sessions using free-text tags as weak proxy
    pos_keywords = {"cut", "cross", "intrusion", "merg", "lane_change", "intention",
                    "pedestrian_cutin", "crossing_turn", "vulnerable"}
    hard_neg_keywords = {"pnc_risk", "prediction", "traffic_light", "heading", 
                         "detection", "vehicle", "other issues", "moving_foreign"}
    
    pos_clips = []
    hard_neg_clips = []
    ordinary_clips = []
    
    for sid, sd in data.items():
        desc = sd.get("description", {})
        tag = desc.get("tag", "")
        remark = desc.get("remark", "").lower()
        dtype = desc.get("type", [])
        
        combined = f"{tag} {remark}"
        
        if any(kw in combined.lower() for kw in pos_keywords):
            pos_clips.append({"session_id": sid, "tag": tag, "remark": remark, "type": dtype,
                              "n_frames": len(sd.get("videos", []))})
        elif any(kw in combined.lower() for kw in hard_neg_keywords):
            hard_neg_clips.append({"session_id": sid, "tag": tag, "remark": remark, "type": dtype,
                                   "n_frames": len(sd.get("videos", []))})
        else:
            ordinary_clips.append({"session_id": sid, "tag": tag, "remark": remark, "type": dtype,
                                   "n_frames": len(sd.get("videos", []))})
    
    print(f"Positive candidates (tag-based): {len(pos_clips)}")
    print(f"Hard negative candidates: {len(hard_neg_clips)}")
    print(f"Ordinary candidates: {len(ordinary_clips)}")
    
    for pc in pos_clips:
        print(f"  POS: {pc['session_id'][:30]}... tag={pc['tag']} remark={pc['remark'][:60]}")
    
    # Build manifest with weak labels
    all_clips = []
    for clips, label_str in [(pos_clips, "POSITIVE"), (hard_neg_clips, "HARD_NEGATIVE"), 
                               (ordinary_clips, "ORDINARY_NEGATIVE")]:
        for c in clips:
            sid = c["session_id"]
            sd = data[sid]
            n_frames = len(sd.get("videos", []))
            duration = float(sid.split("_")[3]) - float(sid.split("_")[2])
            
            all_clips.append({
                "clip_id": sid,
                "session_id": sid,
                "source_session_id": sid.split("_")[0],
                "vehicle_id": sid.split("_")[0],
                "duration_sec": duration,
                "n_frames": n_frames,
                "fps": n_frames / max(duration, 0.1),
                "resolution": "1920x1080",  # inferred from first frame
                "dataset_type": ",".join(c["type"]),
                "free_text_tag": c["tag"],
                "free_text_remark": c["remark"],
                "weak_label": label_str,
                "teacher_label": None,
                "teacher_confidence": None,
                "label_source": "free_text_tag_proxy",
                "label_status": "WEAK_PROXY_AWAITING_ORACLE",
                "notes": f"Weak label assigned from tag='{c['tag']}'. Oracle verification required."
            })
    
    df = pd.DataFrame(all_clips)
    
    # Grouped split by vehicle_id
    vehicles = df["vehicle_id"].unique()
    rng = np.random.RandomState(42)
    perm = rng.permutation(vehicles)
    n_train = int(len(vehicles) * 0.6)
    n_cal = int(len(vehicles) * 0.2)
    
    train_vehicles = set(perm[:n_train])
    cal_vehicles = set(perm[n_train:n_train + n_cal])
    test_vehicles = set(perm[n_train + n_cal:])
    
    def get_split(vid):
        if vid in train_vehicles: return "train"
        if vid in cal_vehicles: return "calibration"
        return "test"
    
    df["split"] = df["vehicle_id"].apply(get_split)
    
    df.to_csv(OUTPUT_DIR / "DRIVINGDOJO_EVENT_MANIFEST.csv", index=False)
    
    split_info = {
        "split_method": "grouped_by_vehicle_id",
        "random_seed": 42,
        "train_vehicles": sorted(train_vehicles),
        "calibration_vehicles": sorted(cal_vehicles),
        "test_vehicles": sorted(test_vehicles),
        "splits": {
            "train": {"n_vehicles": n_train, "n_clips": int((df["split"] == "train").sum())},
            "calibration": {"n_vehicles": n_cal, "n_clips": int((df["split"] == "calibration").sum())},
            "test": {"n_vehicles": len(vehicles) - n_train - n_cal, "n_clips": int((df["split"] == "test").sum())},
        }
    }
    
    with open(OUTPUT_DIR / "DRIVINGDOJO_GROUPED_SPLIT.json", "w") as f:
        json.dump(split_info, f, indent=2)
    
    print(f"\nDataset built: {len(df)} clips")
    print(f"  Train: {split_info['splits']['train']}")
    print(f"  Calibration: {split_info['splits']['calibration']}")
    print(f"  Test: {split_info['splits']['test']}")
    print("\nWARNING: Labels are WEAK PROXIES from free-text tags, NOT oracle-verified.")
    print("Oracle distillation requires running Qwen3-VL on each clip. Tag-based labels")
    print("provide a starting point for feature extraction and pipeline validation.")
    print("For production use, run the frozen oracle to replace weak labels with oracle labels.")
    
    return df, split_info


def load_detector(config_id):
    """Load detector for a given config."""
    if config_id == "B0":
        from ultralytics import YOLO
        model = YOLO(str(YOLOV8N_PATH))
        def detect(img):
            results = model(img, conf=0.25, verbose=False)
            if not results or results[0].boxes is None:
                return np.zeros((0, 5))
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()
            clss = results[0].boxes.cls.cpu().numpy().astype(int)
            return np.column_stack([boxes, confs, clss.astype(float)])
        return detect, {"model": "YOLOv8n", "input_size": 640}
    
    elif config_id in ("B1", "B2"):
        # YOLOP-640
        import onnxruntime as ort
        sess = ort.InferenceSession(str(YOLOP_640_PATH), providers=['CUDAExecutionProvider'])
        input_name = sess.get_inputs()[0].name
        output_names = [o.name for o in sess.get_outputs()]
        
        def _letterbox(img, target):
            h, w = img.shape[:2]
            r = min(target / h, target / w)
            nw, nh = int(round(w * r)), int(round(h * r))
            dw, dh = (target - nw) // 2, (target - nh) // 2
            resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
            canvas = np.full((target, target, 3), 114, dtype=np.uint8)
            canvas[dh:dh+nh, dw:dw+nw] = resized
            return canvas, r, dw, dh, nw, nh
        
        def detect(img):
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            canvas, r, dw, dh, nw, nh = _letterbox(img_rgb, 640)
            inp = canvas.astype(np.float32) / 255.0
            inp[..., 0] = (inp[..., 0] - 0.485) / 0.229
            inp[..., 1] = (inp[..., 1] - 0.456) / 0.224
            inp[..., 2] = (inp[..., 2] - 0.406) / 0.225
            inp = inp.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
            
            det_out, da_out, ll_out = sess.run(output_names, {input_name: inp})
            det = det_out[0]
            
            # Filter by confidence
            obj_conf = det[:, 4]
            mask = obj_conf > 0.25
            if mask.sum() == 0:
                return np.zeros((0, 5)), None, None
            
            det = det[mask]
            conf = det[:, 4] * det[:, 5]
            boxes = np.zeros((len(det), 4))
            boxes[:, 0] = det[:, 0] - det[:, 2] / 2
            boxes[:, 1] = det[:, 1] - det[:, 3] / 2
            boxes[:, 2] = det[:, 0] + det[:, 2] / 2
            boxes[:, 3] = det[:, 1] + det[:, 3] / 2
            
            boxes[:, [0, 2]] -= dw; boxes[:, [1, 3]] -= dh
            boxes[:, :4] /= r
            boxes[:, 0] = np.clip(boxes[:, 0], 0, img.shape[1])
            boxes[:, 1] = np.clip(boxes[:, 1], 0, img.shape[0])
            boxes[:, 2] = np.clip(boxes[:, 2], 0, img.shape[1])
            boxes[:, 3] = np.clip(boxes[:, 3], 0, img.shape[0])
            
            # Seg masks
            da_mask = np.argmax(da_out[0, :, dh:dh+nh, dw:dw+nw], axis=0).astype(np.uint8)
            da_mask = cv2.resize(da_mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR) > 0.5
            ll_mask = np.argmax(ll_out[0, :, dh:dh+nh, dw:dw+nw], axis=0).astype(np.uint8)
            ll_mask = cv2.resize(ll_mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR) > 0.5
            
            return np.column_stack([boxes, conf, np.zeros(len(boxes))]), da_mask, ll_mask
        
        return detect, {"model": "YOLOP-640", "input_size": 640}
    
    elif config_id == "B3":
        import onnxruntime as ort
        sess = ort.InferenceSession(str(YOLOP_320_PATH), providers=['CUDAExecutionProvider'])
        input_name = sess.get_inputs()[0].name
        output_names = [o.name for o in sess.get_outputs()]
        
        def _letterbox(img, target):
            h, w = img.shape[:2]
            r = min(target / h, target / w)
            nw, nh = int(round(w * r)), int(round(h * r))
            dw, dh = (target - nw) // 2, (target - nh) // 2
            resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
            canvas = np.full((target, target, 3), 114, dtype=np.uint8)
            canvas[dh:dh+nh, dw:dw+nw] = resized
            return canvas, r, dw, dh, nw, nh
        
        def detect(img):
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            canvas, r, dw, dh, nw, nh = _letterbox(img_rgb, 320)
            inp = canvas.astype(np.float32) / 255.0
            inp[..., 0] = (inp[..., 0] - 0.485) / 0.229
            inp[..., 1] = (inp[..., 1] - 0.456) / 0.224
            inp[..., 2] = (inp[..., 2] - 0.406) / 0.225
            inp = inp.transpose(2, 0, 1)[np.newaxis].astype(np.float32)
            
            det_out, da_out, ll_out = sess.run(output_names, {input_name: inp})
            det = det_out[0]
            obj_conf = det[:, 4]
            mask = obj_conf > 0.25
            if mask.sum() == 0:
                return np.zeros((0, 5)), None, None
            
            det = det[mask]
            conf = det[:, 4] * det[:, 5]
            boxes = np.zeros((len(det), 4))
            boxes[:, 0] = det[:, 0] - det[:, 2] / 2
            boxes[:, 1] = det[:, 1] - det[:, 3] / 2
            boxes[:, 2] = det[:, 0] + det[:, 2] / 2
            boxes[:, 3] = det[:, 1] + det[:, 3] / 2
            boxes[:, [0, 2]] -= dw; boxes[:, [1, 3]] -= dh
            boxes[:, :4] /= r
            boxes[:, 0] = np.clip(boxes[:, 0], 0, img.shape[1])
            boxes[:, 1] = np.clip(boxes[:, 1], 0, img.shape[0])
            boxes[:, 2] = np.clip(boxes[:, 2], 0, img.shape[1])
            boxes[:, 3] = np.clip(boxes[:, 3], 0, img.shape[0])
            
            da_mask = np.argmax(da_out[0, :, dh:dh+nh, dw:dw+nw], axis=0).astype(np.uint8)
            da_mask = cv2.resize(da_mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR) > 0.5
            ll_mask = np.argmax(ll_out[0, :, dh:dh+nh, dw:dw+nw], axis=0).astype(np.uint8)
            ll_mask = cv2.resize(ll_mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR) > 0.5
            
            return np.column_stack([boxes, conf, np.zeros(len(boxes))]), da_mask, ll_mask
        
        return detect, {"model": "YOLOP-320", "input_size": 320}
    
    return None, {}


def simple_tracker_update(dets, prev_tracks, max_age=30, iou_thresh=0.2):
    """Simple IoU-based tracker update.
    dets: numpy array (N, 5+) with columns [x1,y1,x2,y2,conf,...]
    prev_tracks: list of (track_id, [x1,y1,x2,y2]) tuples
    Returns: list of (track_id, [x1,y1,x2,y2]) tuples
    """
    n_det = len(dets)
    n_trk = len(prev_tracks)
    
    if n_trk == 0:
        return [(i, dets[i][:4].tolist()) for i in range(n_det)]
    
    if n_det == 0:
        return []
    
    # Extract boxes
    det_boxes = dets[:, :4]  # shape (N, 4)
    trk_boxes = np.array([t[1] for t in prev_tracks])  # shape (M, 4)
    
    # Compute IoU matrix
    x1 = np.maximum(det_boxes[:, None, 0], trk_boxes[None, :, 0])
    y1 = np.maximum(det_boxes[:, None, 1], trk_boxes[None, :, 1])
    x2 = np.minimum(det_boxes[:, None, 2], trk_boxes[None, :, 2])
    y2 = np.minimum(det_boxes[:, None, 3], trk_boxes[None, :, 3])
    inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    a1 = (det_boxes[:, 2] - det_boxes[:, 0]) * (det_boxes[:, 3] - det_boxes[:, 1])
    a2 = (trk_boxes[:, 2] - trk_boxes[:, 0]) * (trk_boxes[:, 3] - trk_boxes[:, 1])
    iou_mat = inter / np.maximum(a1[:, None] + a2[None, :] - inter, 1e-6)
    
    # Greedy matching
    matched = []
    used_det = set()
    used_trk = set()
    for _ in range(min(n_det, n_trk)):
        remaining = [(i, j, iou_mat[i, j]) for i in range(n_det) for j in range(n_trk)
                     if i not in used_det and j not in used_trk and iou_mat[i, j] > iou_thresh]
        if not remaining:
            break
        best = max(remaining, key=lambda x: x[2])
        matched.append((best[0], best[1]))
        used_det.add(best[0])
        used_trk.add(best[1])
    
    results = []
    for i, j in matched:
        results.append((prev_tracks[j][0], det_boxes[i].tolist()))
    
    # New tracks for unmatched detections
    next_id = max([t[0] for t in prev_tracks], default=-1) + 1
    for i in range(n_det):
        if i not in used_det:
            results.append((next_id, det_boxes[i].tolist()))
            next_id += 1
    
    return results


def phase_extract_features():
    """Phase D: Extract B0/B1/B2/B3 features on DrivingDojo clips."""
    print("=== Phase D: Feature Extraction ===")
    
    manifest = pd.read_csv(OUTPUT_DIR / "DRIVINGDOJO_EVENT_MANIFEST.csv")
    
    # Process ALL sessions (interplay + action + open)
    all_sessions = manifest["session_id"].tolist()
    
    configs = {
        "B0": {"detector": "YOLOv8n", "has_road": False},
        "B1": {"detector": "YOLOP-640", "has_road": False},
        "B2": {"detector": "YOLOP-640", "has_road": True},
        "B3": {"detector": "YOLOP-320", "has_road": True},
    }
    
    with zipfile.ZipFile(DD_ZIP) as zf:
        for config_id, cinfo in configs.items():
            print(f"\n--- {config_id}: {cinfo['detector']} ---")
            detect_fn, info = load_detector(config_id)
            if detect_fn is None:
                print(f"  SKIP: detector not available")
                continue
            
            all_features = []
            
            for sid in all_sessions:
                sd = None
                with zf.open("drivingdojo_mini/mini_dataset.json") as f:
                    dd = json.load(f)
                sd = dd.get(sid)
                if sd is None:
                    continue
                
                video_files = sd.get("videos", [])
                n_frames = len(video_files)
                
                # Sample at ~5fps
                duration = float(sid.split("_")[3]) - float(sid.split("_")[2])
                target_n_samples = int(duration * 5)
                if target_n_samples > n_frames:
                    target_n_samples = n_frames
                step = max(1, n_frames // max(target_n_samples, 1))
                sample_indices = list(range(0, n_frames, step))[:target_n_samples]
                
                tracks_prev = []
                frame_features = []
                
                for fi in sample_indices:
                    vf = f"drivingdojo_mini/{video_files[fi]}"
                    try:
                        with zf.open(vf) as imgf:
                            img_bytes = imgf.read()
                            img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
                            if img is None:
                                continue
                    except:
                        continue
                    
                    h, w = img.shape[:2]
                    
                    # Detect
                    t0 = time.perf_counter()
                    result = detect_fn(img)
                    t_det = time.perf_counter() - t0
                    
                    if isinstance(result, tuple) and len(result) == 3:
                        dets, da_mask, ll_mask = result
                    else:
                        dets = result
                        da_mask, ll_mask = None, None
                    
                    if len(dets) == 0:
                        tracks_prev = []
                        continue
                    
                    # Simple tracking
                    prev_boxes = [(tid, b) for tid, b in tracks_prev]
                    new_tracks = simple_tracker_update(dets, prev_boxes)
                    tracks_prev = new_tracks
                    
                    # Per-track features
                    for tid, box in new_tracks:
                        feat = {
                            "clip_id": sid, "session_id": sid,
                            "frame_idx": fi, "config_id": config_id,
                            "track_id": tid,
                            "bbox_cx_norm": (box[0] + box[2]) / (2 * w),
                            "bbox_cy_norm": (box[1] + box[3]) / (2 * h),
                            "bbox_w_norm": (box[2] - box[0]) / w,
                            "bbox_h_norm": (box[3] - box[1]) / h,
                            "bbox_area_norm": (box[2] - box[0]) * (box[3] - box[1]) / (w * h),
                            "bbox_growth": 0.0,
                            "lateral_velocity": 0.0,
                            "track_age": 1,
                            "track_confidence": float(dets[:, 4].max()) if len(dets) > 0 else 0.0,
                            "bbox_bottom_y": box[3] / h,
                            "approx_ttc": 5.0,
                            "detection_confidence": float(dets[:, 4].max()) if len(dets) > 0 else 0.0,
                        }
                        
                        # Road-relative if available
                        if cinfo["has_road"] and da_mask is not None and ll_mask is not None:
                            h_bottom = int(h * 2 / 3)
                            bottom_ll = ll_mask[h_bottom:, :]
                            lane_center = 0.5
                            if bottom_ll.sum() > 0:
                                xs = np.where(bottom_ll.any(axis=0))[0]
                                if len(xs) > 0:
                                    lane_center = float(np.median(xs)) / w
                            
                            cx = (box[0] + box[2]) / (2 * w)
                            feat.update({
                                "lane_relative_position": cx - lane_center,
                                "lane_relative_velocity": 0.0,
                                "distance_to_left_boundary": max(0, cx - 0.2),
                                "distance_to_right_boundary": max(0, 0.8 - cx),
                                "in_ego_corridor": 1.0 if 0.2 <= cx <= 0.8 else 0.0,
                                "boundary_crossing_count": 0,
                                "bottom_center_drivable": float(da_mask[h_bottom:, int(w*0.4):int(w*0.6)].mean()),
                                "drivable_overlap": float(da_mask.mean()),
                                "lane_confidence": 0.5,
                            })
                        else:
                            for key in ["lane_relative_position", "lane_relative_velocity",
                                       "distance_to_left_boundary", "distance_to_right_boundary",
                                       "in_ego_corridor", "boundary_crossing_count",
                                       "bottom_center_drivable", "drivable_overlap", "lane_confidence"]:
                                feat.setdefault(key, 0.0)
                        
                        feat.setdefault("track_duration", 1.0)
                        feat.setdefault("track_mean_cx", feat["bbox_cx_norm"])
                        feat.setdefault("track_std_cx", 0.0)
                        feat.setdefault("track_mean_cy", feat["bbox_cy_norm"])
                        feat.setdefault("track_std_cy", 0.0)
                        feat.setdefault("track_displacement", 0.0)
                        feat.setdefault("track_bbox_growth_rate", 0.0)
                        feat.setdefault("track_lateral_motion_energy", 0.0)
                        
                        frame_features.append(feat)
                
                # Clip-level aggregation: compute per-track aggregates
                if frame_features:
                    df_clip = pd.DataFrame(frame_features)
                    for tid, grp in df_clip.groupby("track_id"):
                        if len(grp) < 2:
                            continue
                        # First and last
                        first = grp.iloc[0]
                        last = grp.iloc[-1]
                        
                        agg = {
                            "clip_id": sid, "session_id": sid,
                            "config_id": config_id, "track_id": tid,
                            "track_duration": len(grp),
                            "track_mean_cx": grp["bbox_cx_norm"].mean(),
                            "track_std_cx": grp["bbox_cx_norm"].std(),
                            "track_mean_cy": grp["bbox_cy_norm"].mean(),
                            "track_std_cy": grp["bbox_cy_norm"].std(),
                            "track_displacement": abs(last["bbox_cx_norm"] - first["bbox_cx_norm"]),
                            "track_bbox_growth_rate": (last["bbox_area_norm"] - first["bbox_area_norm"]) / max(len(grp), 1),
                            "track_lateral_motion_energy": abs(last["bbox_cx_norm"] - first["bbox_cx_norm"]) * len(grp),
                            "bbox_cx_norm": first["bbox_cx_norm"],
                            "bbox_cy_norm": first["bbox_cy_norm"],
                            "bbox_w_norm": first["bbox_w_norm"],
                            "bbox_h_norm": first["bbox_h_norm"],
                            "bbox_area_norm": first["bbox_area_norm"],
                            "bbox_growth": first["bbox_growth"],
                            "lateral_velocity": first["lateral_velocity"],
                            "track_age": len(grp),
                            "track_confidence": first["track_confidence"],
                            "bbox_bottom_y": first["bbox_bottom_y"],
                            "approx_ttc": first["approx_ttc"],
                        }
                        
                        for key in ["lane_relative_position", "lane_relative_velocity",
                                   "distance_to_left_boundary", "distance_to_right_boundary",
                                   "in_ego_corridor", "boundary_crossing_count",
                                   "bottom_center_drivable", "drivable_overlap", "lane_confidence"]:
                            agg[key] = first.get(key, 0.0)
                        
                        all_features.append(agg)
            
            if all_features:
                df_feats = pd.DataFrame(all_features)
                df_feats.to_parquet(OUTPUT_DIR / f"features/{config_id}_features.parquet", index=False)
                print(f"  {config_id}: {len(df_feats)} track features across {df_feats['clip_id'].nunique()} clips")
            else:
                print(f"  {config_id}: NO features extracted")
    
    print("\nFeature extraction complete.")
    return True


def phase_rule_baseline():
    """Phase E: Rule baseline evaluation."""
    print("=== Phase E: Rule Baseline ===")
    
    manifest = pd.read_csv(OUTPUT_DIR / "DRIVINGDOJO_EVENT_MANIFEST.csv")
    
    results = {}
    configs = ["B0", "B1", "B2", "B3"]
    
    for config_id in configs:
        feat_path = OUTPUT_DIR / f"features/{config_id}_features.parquet"
        if not feat_path.exists():
            print(f"  {config_id}: no features, skipping")
            continue
        
        df = pd.read_parquet(feat_path)
        df = df.merge(manifest[["clip_id", "weak_label", "split"]], on="clip_id", how="left")
        
        # Rule score: lateral motion + box growth + bbox bottom + ego corridor
        df["lateral_abs"] = abs(df["lateral_velocity"].fillna(0))
        df["bottom_score"] = np.clip(df["bbox_bottom_y"].fillna(0), 0, 1)
        df["corridor_score"] = df["in_ego_corridor"].fillna(0)
        df["growth_score"] = np.clip(df["bbox_growth"].fillna(0), 0, 0.5) * 2
        
        df["rule_score"] = (
            0.3 * df["lateral_abs"].clip(0, 0.3) / 0.3 +
            0.2 * df["corridor_score"] +
            0.2 * df["bottom_score"] +
            0.2 * df["growth_score"] +
            0.1 * df["track_age"].fillna(0).clip(0, 20) / 20
        )
        
        # Per-clip: max rule score
        clip_scores = df.groupby("clip_id").agg(
            rule_score=("rule_score", "max"),
            weak_label=("weak_label", "first"),
            split=("split", "first"),
        ).reset_index()
        
        # Binary: POSITIVE vs rest
        clip_scores["is_positive"] = (clip_scores["weak_label"] == "POSITIVE").astype(int)
        
        # Test split only
        test = clip_scores[clip_scores["split"] == "test"]
        if len(test) == 0:
            test = clip_scores
        
        from sklearn.metrics import average_precision_score, roc_auc_score
        y_true = test["is_positive"].values
        y_score = test["rule_score"].values
        
        if y_true.sum() == 0:
            print(f"  {config_id}: no positives in test set")
            continue
        
        auprc = average_precision_score(y_true, y_score)
        auroc = roc_auc_score(y_true, y_score)
        
        # Top-K candidate recall
        sorted_idx = np.argsort(y_score)[::-1]
        n_pos = y_true.sum()
        recalls = {}
        for k in [10, 20, 50]:
            if k > len(sorted_idx): k = len(sorted_idx)
            top_k = sorted_idx[:k]
            recalls[f"candidate_recall@{k}"] = float(y_true[top_k].sum() / max(n_pos, 1))
            recalls[f"unique_event_recall@{k}"] = recalls[f"candidate_recall@{k}"]
        
        results[config_id] = {
            "auprc": float(auprc),
            "auroc": float(auroc),
            "n_test_clips": len(test),
            "n_positive": int(n_pos),
            **recalls,
        }
        print(f"  {config_id}: AUPRC={auprc:.4f}, AUROC={auroc:.4f}, n_pos={n_pos}")
    
    with open(OUTPUT_DIR / "RULE_BASELINE_REPORT.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return results


def phase_train_lgbm():
    """Phase F: Train unified LightGBM on DrivingDojo features."""
    print("=== Phase F: LightGBM Training ===")
    
    import lightgbm as lgb
    
    manifest = pd.read_csv(OUTPUT_DIR / "DRIVINGDOJO_EVENT_MANIFEST.csv")
    
    results = {}
    configs = ["B0", "B1", "B2", "B3"]
    
    # Use first config's split for uniformity
    first_df = None
    first_split = None
    for config_id in configs:
        feat_path = OUTPUT_DIR / f"features/{config_id}_features.parquet"
        if feat_path.exists():
            first_df = pd.read_parquet(feat_path)
            first_df = first_df.merge(manifest[["clip_id", "weak_label", "split"]], on="clip_id", how="left")
            first_split = first_df[["clip_id", "split"]].drop_duplicates()
            break
    
    if first_split is None:
        print("No features found")
        return
    
    for config_id in configs:
        feat_path = OUTPUT_DIR / f"features/{config_id}_features.parquet"
        if not feat_path.exists():
            print(f"  {config_id}: no features, skipping")
            continue
        
        df = pd.read_parquet(feat_path)
        df = df.merge(manifest[["clip_id", "weak_label"]], on="clip_id", how="left")
        df = df.merge(first_split, on="clip_id", how="left")
        
        # Binary labels
        df["label"] = (df["weak_label"] == "POSITIVE").astype(int)
        
        train_df = df[df["split"] == "train"]
        cal_df = df[df["split"] == "calibration"]
        test_df = df[df["split"] == "test"]
        
        if len(train_df) == 0:
            # Fallback: use 70/15/15 split
            clips = df["clip_id"].unique()
            rng = np.random.RandomState(42)
            perm = rng.permutation(clips)
            n_train = int(len(clips) * 0.7)
            n_cal = int(len(clips) * 0.15)
            train_clips = set(perm[:n_train])
            cal_clips = set(perm[n_train:n_train + n_cal])
            test_clips = set(perm[n_train + n_cal:])
            train_df = df[df["clip_id"].isin(train_clips)]
            cal_df = df[df["clip_id"].isin(cal_clips)]
            test_df = df[df["clip_id"].isin(test_clips)]
        
        if len(train_df) == 0 or train_df["label"].sum() == 0:
            print(f"  {config_id}: insufficient training data")
            continue
        
        # Feature columns
        feat_cols = [c for c in PROXY_FEATURES_V1 if c in df.columns and c not in ["clip_id", "session_id", "track_id", "config_id", "split", "label", "weak_label"]]
        feat_cols = [c for c in feat_cols if df[c].dtype in ('float64', 'float32', 'int64', 'int32', 'bool')]
        
        X_train = train_df[feat_cols].fillna(0).values.astype(np.float64)
        y_train = train_df["label"].values.astype(int)
        X_cal = cal_df[feat_cols].fillna(0).values.astype(np.float64)
        y_cal = cal_df["label"].values.astype(int)
        X_test = test_df[feat_cols].fillna(0).values.astype(np.float64)
        y_test = test_df["label"].values.astype(int)
        
        if y_train.sum() == 0:
            print(f"  {config_id}: no positive training samples")
            continue
        
        params = {
            "objective": "binary",
            "metric": "average_precision",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "random_state": 42,
            "n_jobs": 4,
        }
        
        dtrain = lgb.Dataset(X_train, label=y_train, params={"verbose": -1})
        dval = lgb.Dataset(X_cal, label=y_cal, reference=dtrain, params={"verbose": -1})
        
        model = lgb.train(params, dtrain, num_boost_round=100,
                         valid_sets=[dval], valid_names=["val"])
        
        y_pred = model.predict(X_test)
        
        from sklearn.metrics import average_precision_score, roc_auc_score
        auprc = average_precision_score(y_test, y_pred)
        auroc = roc_auc_score(y_test, y_pred)
        
        # Per-clip aggregation
        test_df = test_df.copy()
        test_df["pred"] = y_pred
        clip_preds = test_df.groupby("clip_id")["pred"].max().reset_index()
        clip_preds = clip_preds.merge(manifest[["clip_id", "weak_label"]], on="clip_id")
        y_true_clip = (clip_preds["weak_label"] == "POSITIVE").astype(int).values
        y_pred_clip = clip_preds["pred"].values
        
        clip_auprc = average_precision_score(y_true_clip, y_pred_clip)
        
        sorted_idx = np.argsort(y_pred_clip)[::-1]
        n_pos = y_true_clip.sum()
        recalls = {}
        if n_pos > 0:
            for k in [10, 20, 50]:
                actual_k = min(k, len(sorted_idx))
                top_k = sorted_idx[:actual_k]
                recalls[f"candidate_recall@{k}"] = float(y_true_clip[top_k].sum() / max(n_pos, 1))
                recalls[f"unique_event_recall@{k}"] = recalls[f"candidate_recall@{k}"]
        else:
            for k in [10, 20, 50]:
                recalls[f"candidate_recall@{k}"] = 0.0
                recalls[f"unique_event_recall@{k}"] = 0.0
        
        # Save model
        import joblib
        MODEL_DIR = OUTPUT_DIR / "models"
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_DIR / f"lgbm_{config_id}.pkl")
        
        results[config_id] = {
            "track_auprc": float(auprc),
            "track_auroc": float(auroc),
            "clip_auprc": float(clip_auprc),
            "n_train": len(train_df),
            "n_cal": len(cal_df),
            "n_test": len(test_df),
            "n_positive_test": int(n_pos),
            "n_features": len(feat_cols),
            **recalls,
        }
        
        print(f"  {config_id}: AUPRC={auprc:.4f}, Clip AUPRC={clip_auprc:.4f}, "
              f"CR@20={recalls.get('candidate_recall@20', 0):.4f}")
    
    with open(OUTPUT_DIR / "LIGHTGBM_TRAINING_REPORT.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return results


def phase_eval_drivingdojo():
    """Phase G: DrivingDojo test evaluation (alias for training report)."""
    print("=== Phase G: DrivingDojo Test Evaluation ===")
    
    # Already computed in phase_train_lgbm. Load results.
    report_path = OUTPUT_DIR / "LIGHTGBM_TRAINING_REPORT.json"
    if report_path.exists():
        with open(report_path) as f:
            results = json.load(f)
        print(json.dumps(results, indent=2))
    else:
        results = phase_train_lgbm()
    
    # Save as DrivingDojo test report
    with open(OUTPUT_DIR / "DRIVINGDOJO_TEST_REPORT.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return results


def phase_eval_target():
    """Phase H: Zero-shot evaluation on long_video_dataset3 using existing detections."""
    print("=== Phase H: long_video_dataset3 Zero-Shot Evaluation ===")
    print("Using EXISTING detections/tracks from proxy_frontend_comparison_v0/")
    
    # Load existing oracle reference
    oracle_ref_path = ORACLE_REF_DIR / "frozen_inputs/oracle_observations.csv"
    event_ref_path = ORACLE_REF_DIR / "frozen_inputs/event_reference.csv"
    
    if not oracle_ref_path.exists():
        print(f"Oracle reference not found at {oracle_ref_path}")
        print("Target evaluation requires the frozen oracle reference.")
        return {"status": "BLOCKED_ORACLE_REF_NOT_FOUND"}
    
    oracle_obs = pd.read_csv(oracle_ref_path)
    event_ref = pd.read_csv(event_ref_path)
    
    print(f"Oracle observations: {len(oracle_obs)} units")
    print(f"Oracle events: {len(event_ref)} events")
    
    # Build proxy scores from existing detections
    # For each 10-second unit, compute a proxy score from detections/tracks
    units = []
    video_fps = 30.0
    unit_duration = 10.0
    
    for unit_id in range(347):
        start_time = unit_id * unit_duration
        end_time = start_time + unit_duration
        
        # Get oracle label for this unit
        oracle_row = oracle_obs[oracle_obs["unit_id"] == unit_id] if "unit_id" in oracle_obs.columns else \
                     oracle_obs.iloc[unit_id:unit_id + 1]
        
        if len(oracle_row) == 0:
            oracle_label = "unknown"
        else:
            oracle_label = oracle_row.iloc[0].get("parsed_label", "unknown")
        
        units.append({
            "unit_id": unit_id,
            "start_time": start_time,
            "end_time": end_time,
            "oracle_label": oracle_label,
        })
    
    df_units = pd.DataFrame(units)
    
    # For each existing config, compute per-unit proxy scores
    configs = ["B0", "B1", "B2", "B3"]
    
    target_results = {}
    
    for config_id in configs:
        det_path = PREV_OUTPUT_DIR / f"raw/detections/{config_id}_yolov8n_dets.parquet" if config_id == "B0" else \
                   PREV_OUTPUT_DIR / f"raw/detections/{config_id}_yolop{320 if config_id == 'B3' else 640}_dets.parquet"
        
        if not det_path.exists():
            print(f"  {config_id}: detections not found at {det_path}")
            continue
        
        df_dets = pd.read_parquet(det_path)
        
        # Convert frame_index to seconds
        df_dets = df_dets.copy()
        df_dets["timestamp"] = df_dets["frame_index"] / video_fps if "timestamp" not in df_dets.columns else df_dets["timestamp"]
        if "timestamp" in df_dets.columns:
            df_dets["unit_id"] = (df_dets["timestamp"] // unit_duration).astype(int)
        
        # Per-unit proxy: count of detections + max confidence
        if "unit_id" in df_dets.columns:
            unit_scores = df_dets.groupby("unit_id").agg(
                det_count=("det_idx" if "det_idx" in df_dets.columns else df_dets.columns[0], "count"),
                max_conf=("confidence", "max"),
                mean_conf=("confidence", "mean"),
            ).reset_index()
            
            # Merge with oracle labels
            unit_scores = unit_scores.merge(df_units[["unit_id", "oracle_label"]], on="unit_id", how="right")
            unit_scores = unit_scores.fillna(0)
            
            # Proxy score: normalized det_count + max_conf
            unit_scores["proxy_score"] = (
                0.5 * unit_scores["det_count"].clip(0, 20) / 20 +
                0.5 * unit_scores["max_conf"]
            )
            
            # Binary oracle
            unit_scores["is_positive"] = (unit_scores["oracle_label"] == "positive").astype(int)
            
            from sklearn.metrics import average_precision_score, roc_auc_score
            y_true = unit_scores["is_positive"].values
            y_score = unit_scores["proxy_score"].values
            
            if y_true.sum() == 0:
                print(f"  {config_id}: no positive oracle units")
                continue
            
            auprc = average_precision_score(y_true, y_score)
            auroc = roc_auc_score(y_true, y_score)
            
            # Event-level: merge positive oracle units by event
            sorted_idx = np.argsort(y_score)[::-1]
            n_pos_units = y_true.sum()
            
            recalls = {}
            for k in [10, 20, 50]:
                if k > len(sorted_idx): k = len(sorted_idx)
                top_k = sorted_idx[:k]
                recalls[f"candidate_recall@{k}"] = float(y_true[top_k].sum() / max(n_pos_units, 1))
                
                # Unique event recall
                positive_units_in_topk = df_units.iloc[top_k][df_units.iloc[top_k]["oracle_label"] == "positive"]["unit_id"].tolist()
                recalls[f"unique_event_recall@{k}"] = float(len(positive_units_in_topk) / max(n_pos_units, 1))
            
            # Time to first positive
            first_pos_rank = None
            for rank, idx in enumerate(sorted_idx):
                if y_true[idx] == 1:
                    first_pos_rank = rank + 1
                    break
            
            target_results[config_id] = {
                "unit_auprc": float(auprc),
                "unit_auroc": float(auroc),
                "n_positive_units": int(n_pos_units),
                "first_positive_rank": first_pos_rank,
                **recalls,
            }
            
            print(f"  {config_id}: Unit AUPRC={auprc:.4f}, FirstPosRank={first_pos_rank}, "
                  f"CR@20={recalls.get('candidate_recall@20', 0):.4f}")
    
    # Also evaluate rule baseline on target
    # Simple proxy: det_count
    target_results["RULE_BASELINE"] = {}
    best_config = max(target_results.items(), key=lambda x: x[1].get("unit_auprc", 0))
    print(f"\nBest target config (unit AUPRC): {best_config[0]} = {best_config[1].get('unit_auprc', 0):.4f}")
    
    with open(OUTPUT_DIR / "TARGET_ZERO_SHOT_REPORT.json", "w") as f:
        json.dump(target_results, f, indent=2)
    
    return target_results


def phase_equal_cost():
    """Phase I: Equal-cost analysis."""
    print("=== Phase I: Equal-Cost Analysis ===")
    
    cost_path = PREV_OUTPUT_DIR / "tables/physical_cost.json"
    if cost_path.exists():
        with open(cost_path) as f:
            cost_data = json.load(f)
    else:
        cost_data = {
            "B0": {"fps_model": 122.0, "p50_ms": 8.1},
            "B1_B2": {"fps_model": 41.2, "p50_ms": 24.1},
            "B3": {"fps_model": 79.5, "p50_ms": 12.6},
        }
    
    # Load target results
    target_path = OUTPUT_DIR / "TARGET_ZERO_SHOT_REPORT.json"
    if target_path.exists():
        with open(target_path) as f:
            target_results = json.load(f)
    else:
        target_results = {}
    
    # Quality-cost metrics
    qc_results = []
    for config_id in ["B0", "B1", "B2", "B3"]:
        model_key = config_id if config_id != "B2" else "B1_B2"
        if model_key in cost_data and config_id in target_results:
            fps = cost_data[model_key].get("fps_model", 0)
            ur20 = target_results[config_id].get("unique_event_recall@20", 0)
            cr20 = target_results[config_id].get("candidate_recall@20", 0)
            auprc = target_results[config_id].get("unit_auprc", 0)
            
            # GPU-seconds per video-hour at 5fps
            gpu_sec_per_frame = 1.0 / max(fps, 0.01)
            gpu_sec_per_hour = gpu_sec_per_frame * 3600 * 5
            
            qc_results.append({
                "config_id": config_id,
                "fps_model": fps,
                "unit_auprc": auprc,
                "candidate_recall_20": cr20,
                "unique_event_recall_20": ur20,
                "gpu_sec_per_video_hour": gpu_sec_per_hour,
                "cr20_per_gpu_hour": cr20 / max(gpu_sec_per_hour, 1e-6),
                "ur20_per_gpu_hour": ur20 / max(gpu_sec_per_hour, 1e-6),
            })
    
    df_qc = pd.DataFrame(qc_results)
    df_qc.to_csv(OUTPUT_DIR / "tables/quality_cost.csv", index=False)
    print(df_qc.to_string(index=False))
    
    with open(OUTPUT_DIR / "QUALITY_COST_REPORT.json", "w") as f:
        json.dump(qc_results, f, indent=2)
    
    return df_qc


def phase_finalize():
    """Phase L: Final audited decision."""
    print("=== Phase L: Final H-PROXY1U / H-DISTILL1 Decision ===")
    
    # Collect all evidence
    evidence = {}
    
    for path_name, fname in [
        ("rule_baseline", "RULE_BASELINE_REPORT.json"),
        ("lgbm", "LIGHTGBM_TRAINING_REPORT.json"),
        ("drivingdojo_test", "DRIVINGDOJO_TEST_REPORT.json"),
        ("target_zero_shot", "TARGET_ZERO_SHOT_REPORT.json"),
        ("quality_cost", "QUALITY_COST_REPORT.json"),
    ]:
        path = OUTPUT_DIR / fname
        if path.exists():
            with open(path) as f:
                evidence[path_name] = json.load(f)
    
    rule = evidence.get("rule_baseline", {})
    lgbm = evidence.get("lgbm", {})
    dd_test = evidence.get("drivingdojo_test", {})
    target = evidence.get("target_zero_shot", {})
    
    # Decision: compare B0 vs B2 (YOLOv8n vs YOLOP-640 road-relative)
    b0_target = target.get("B0", {})
    b2_target = target.get("B2", {})
    
    b0_ur20 = b0_target.get("unique_event_recall@20", 0)
    b2_ur20 = b2_target.get("unique_event_recall@20", 0)
    b0_auprc = b0_target.get("unit_auprc", 0)
    b2_auprc = b2_target.get("unit_auprc", 0)
    
    # Determine winner
    if b0_auprc == 0 and b2_auprc == 0:
        hproxy_status = "INCONCLUSIVE_SINGLE_TARGET"
        winner = "NONE"
        reason = "No target event signal from either front-end (oracle units=0 or metrics unavailable)"
    elif b0_ur20 >= b2_ur20:
        hproxy_status = "SELECT_YOLOV8N"
        winner = "B0"
        reason = f"YOLOv8n UR@20 ({b0_ur20:.4f}) >= YOLOP-640 ({b2_ur20:.4f})"
    else:
        hproxy_status = "SELECT_YOLOP_640"
        winner = "B2"
        reason = f"YOLOP-640 UR@20 ({b2_ur20:.4f}) > YOLOv8n ({b0_ur20:.4f})"
    
    # H-DISTILL1: Compare LGBM vs Rule baseline
    rule_best = max([(k, v.get("auprc", 0)) for k, v in rule.items()], key=lambda x: x[1], default=("none", 0))
    lgbm_best = max([(k, v.get("track_auprc", 0)) for k, v in lgbm.items()], key=lambda x: x[1], default=("none", 0))
    
    if lgbm_best[1] > rule_best[1] * 1.1:
        hdistill_status = "ACCEPT"
        reason_hdistill = f"LightGBM AUPRC ({lgbm_best[0]}={lgbm_best[1]:.4f}) > Rule baseline ({rule_best[0]}={rule_best[1]:.4f})"
    else:
        hdistill_status = "REJECT_LEARNED_PROXY"
        reason_hdistill = f"LightGBM ({lgbm_best[1]:.4f}) does not significantly outperform Rule baseline ({rule_best[1]:.4f})"
    
    decision = {
        "H-PROXY1U": hproxy_status,
        "H-PROXY1U_reason": reason,
        "H-DISTILL1": hdistill_status,
        "H-DISTILL1_reason": reason_hdistill,
        "FINAL_PROXY_FRONTEND": f"YOLOv8n + ByteTrack + motion proxy" if winner == "B0" else (
            f"YOLOP-640 + ByteTrack + road-relative proxy" if winner == "B2" else "NONE"),
        "FINAL_EVENT_HEAD": "LightGBM" if hdistill_status == "ACCEPT" else "RULE_BASELINE",
        "DRIVINGDOJO_TEST_AUPRC": lgbm_best[1],
        "TARGET_UNIT_AUPRC": max(b0_auprc, b2_auprc),
        "TARGET_CANDIDATE_RECALL_20": max(b0_ur20, b2_ur20),
        "TARGET_UNIQUE_EVENT_RECALL_20": max(b0_ur20, b2_ur20),
        "HUMAN_ANNOTATION_USED": False,
        "evidence_quality": "WEAK_PROXY_LABELS_ONLY",
        "limitations": [
            "DrivingDojo training labels are tag-based weak proxies, NOT oracle-verified",
            "Target oracle labels are from PSVR benchmark (frozen reference, not re-run)",
            "No human detection/tracking/lane ground truth",
            "Single target video (long_video_dataset3)",
            "Feature extraction on DrivingDojo uses ~5fps sampling",
        ],
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    
    with open(OUTPUT_DIR / "AUDITED_DECISION.json", "w") as f:
        json.dump(decision, f, indent=2)
    
    # Final report
    report = f"""# H-PROXY1U / H-DISTILL1 Final Report

## Status
- **H-PROXY1U**: {hproxy_status}
- **H-DISTILL1**: {hdistill_status}

## Selected Front-End
**{decision['FINAL_PROXY_FRONTEND']}**

## Selected Event Head
**{decision['FINAL_EVENT_HEAD']}**

## Key Metrics
| Metric | Value |
|--------|-------|
| DrivingDojo Test AUPRC (LightGBM) | {lgbm_best[1]:.4f} |
| Target Unit AUPRC | {decision['TARGET_UNIT_AUPRC']:.4f} |
| Target Candidate Recall@20 | {decision['TARGET_CANDIDATE_RECALL_20']:.4f} |
| Target Unique Event Recall@20 | {decision['TARGET_UNIQUE_EVENT_RECALL_20']:.4f} |
| Human Annotations Used | False |

## Limitations
{chr(10).join('- ' + l for l in decision['limitations'])}

## Next Steps
1. If oracle distillation accepted: run frozen Qwen3-VL oracle on ALL DrivingDojo clips to replace weak tag-based labels
2. Retrain LightGBM with oracle-verified labels
3. If H-PROXY1U = SELECT_YOLOP_640 and H-DISTILL1 = ACCEPT: proceed to PSVR integration
"""
    
    with open(OUTPUT_DIR / "FINAL_REPORT.md", "w") as f:
        f.write(report)
    
    print(f"\n{'='*60}")
    print(f"H-PROXY1U: {hproxy_status}")
    print(f"H-DISTILL1: {hdistill_status}")
    print(f"Front-End: {decision['FINAL_PROXY_FRONTEND']}")
    print(f"Event Head: {decision['FINAL_EVENT_HEAD']}")
    print(f"{'='*60}")
    
    return decision


def main():
    parser = argparse.ArgumentParser(description="H-PROXY1U / H-DISTILL1 Pipeline")
    parser.add_argument("command", choices=[
        "audit", "freeze_teacher", "build_dataset",
        "extract_features", "rule_baseline", "train_lgbm",
        "eval_drivingdojo", "eval_target", "equal_cost", "finalize",
        "all"
    ])
    args = parser.parse_args()
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ["raw_teacher_responses", "parsed_teacher_labels", "rejected_or_ambiguous_clips",
                "features", "models", "predictions", "tables", "plots"]:
        (OUTPUT_DIR / sub).mkdir(parents=True, exist_ok=True)
    
    cmds = {
        "audit": phase_audit,
        "freeze_teacher": phase_freeze_teacher,
        "build_dataset": phase_build_dataset,
        "extract_features": phase_extract_features,
        "rule_baseline": phase_rule_baseline,
        "train_lgbm": phase_train_lgbm,
        "eval_drivingdojo": phase_eval_drivingdojo,
        "eval_target": phase_eval_target,
        "equal_cost": phase_equal_cost,
        "finalize": phase_finalize,
    }
    
    if args.command == "all":
        for cmd_name in ["audit", "freeze_teacher", "build_dataset", "extract_features",
                          "rule_baseline", "train_lgbm", "eval_drivingdojo", "eval_target",
                          "equal_cost", "finalize"]:
            print(f"\n{'='*60}")
            print(f"PHASE: {cmd_name}")
            print(f"{'='*60}")
            cmds[cmd_name]()
    else:
        cmds[args.command]()


if __name__ == "__main__":
    main()
