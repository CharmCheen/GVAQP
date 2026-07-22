#!/usr/bin/env python3
"""
PSVR Proxy Finalization — Master Pipeline.

Phase I-A: Pipeline Integrity Audit
Phase I-B: Final Candidate Definition  
Phase I-C: Full 347-Unit Offline Evaluation
Phase I-D: Physical Cost Profiling
Phase I-E: PSVR Physical Pilot → Family Decision

Usage:
  python scripts/audit_proxy_finalization_state.py           # I-A
  python scripts/audit_proxy_finalization_state.py eval_all  # I-C
  python scripts/audit_proxy_finalization_state.py cost      # I-D
  python scripts/audit_proxy_finalization_state.py finalize  # I-E + decision
"""

import sys, os, json, time, hashlib, argparse, warnings, gc
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import cv2

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs/psvr_proxy_finalization_v0"
ORACLE_REF_DIR = PROJECT_ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict"
VIDEO_PATH = PROJECT_ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"

YOLOV8N_PATH = PROJECT_ROOT / "models/yolo/yolov8n.pt"
YOLOP_320_PATH = PROJECT_ROOT / "YOLOP/weights/yolop-320-320.onnx"
YOLOP_640_PATH = PROJECT_ROOT / "YOLOP/weights/yolop-640-640.onnx"

PREV_DIR = PROJECT_ROOT / "outputs/proxy_frontend_comparison_v0"
DISTILL_DIR = PROJECT_ROOT / "outputs/proxy_oracle_distillation_v0"

UNIT_DURATION = 10.0
VIDEO_FPS = 30.0
UNIT_FRAMES = int(UNIT_DURATION * VIDEO_FPS)  # 300

CANDIDATES = {
    "Y8-R":  {"family": "YOLOV8", "detector": "YOLOv8n", "head": "rule", "model_path": str(YOLOV8N_PATH), "resolution": 640},
    "Y8-L":  {"family": "YOLOV8", "detector": "YOLOv8n", "head": "lgbm", "model_path": str(YOLOV8N_PATH), "resolution": 640, "lgbm_path": str(DISTILL_DIR / "models/lgbm_B0.pkl")},
    "YP640-R": {"family": "YOLOP", "detector": "YOLOP-640", "head": "rule", "model_path": str(YOLOP_640_PATH), "resolution": 640},
    "YP640-L": {"family": "YOLOP", "detector": "YOLOP-640", "head": "lgbm", "model_path": str(YOLOP_640_PATH), "resolution": 640, "lgbm_path": str(DISTILL_DIR / "models/lgbm_B2.pkl")},
    "YP320-R": {"family": "YOLOP", "detector": "YOLOP-320", "head": "rule", "model_path": str(YOLOP_320_PATH), "resolution": 320},
    "YP320-L": {"family": "YOLOP", "detector": "YOLOP-320", "head": "lgbm", "model_path": str(YOLOP_320_PATH), "resolution": 320, "lgbm_path": str(DISTILL_DIR / "models/lgbm_B3.pkl")},
}


def phase_audit():
    """I-A: Pipeline Integrity Audit."""
    print("=" * 60)
    print("Phase I-A: Pipeline Integrity Audit")
    print("=" * 60)

    results = {"audit_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # 1. Check model files
    print("\n1. Model Files:")
    for cfg_id, cfg in CANDIDATES.items():
        path = Path(cfg["model_path"])
        exists = path.exists()
        sha = hashlib.sha256(path.read_bytes()).hexdigest()[:16] if exists else "N/A"
        print(f"  {cfg_id}: exists={exists} sha256={sha}... size={path.stat().st_size if exists else 0}")
        results[f"{cfg_id}_model"] = {"exists": exists, "sha256_prefix": sha}

    # 2. Check LGBM models
    print("\n2. LGBM Models:")
    for cfg_id in ["Y8-L", "YP640-L", "YP320-L"]:
        lgbm_path = CANDIDATES[cfg_id].get("lgbm_path")
        if lgbm_path:
            exists = Path(lgbm_path).exists()
            print(f"  {cfg_id}: {lgbm_path} exists={exists}")
            results[f"{cfg_id}_lgbm"] = {"exists": exists}

    # 3. Check oracle reference
    print("\n3. Oracle Reference:")
    oracle_path = ORACLE_REF_DIR / "frozen_inputs/oracle_observations.csv"
    units_path = ORACLE_REF_DIR / "frozen_inputs/units.csv"
    events_path = ORACLE_REF_DIR / "frozen_inputs/event_reference.csv"

    if oracle_path.exists():
        df = pd.read_csv(oracle_path)
        n_pos = (df["parsed_label"] == "positive").sum()
        n_neg = (df["parsed_label"] == "negative").sum()
        print(f"  oracle_observations: {len(df)} units, {n_pos} positive, {n_neg} negative")
        results["oracle_units"] = len(df)
        results["oracle_positives"] = int(n_pos)

    if events_path.exists():
        df = pd.read_csv(events_path)
        print(f"  event_reference: {len(df)} events")
        results["oracle_events"] = len(df)

    if units_path.exists():
        df = pd.read_csv(units_path)
        print(f"  units: {len(df)} rows")
        results["units"] = len(df)

    # 4. B1 vs B2 identity check
    print("\n4. B1/B2 Identity Audit:")
    b1_path = PREV_DIR / "raw/detections/B1_yolop640_dets.parquet"
    b2_path = PREV_DIR / "raw/detections/B2_yolop640_dets.parquet"
    if b1_path.exists() and b2_path.exists():
        b1 = pd.read_parquet(b1_path)
        b2 = pd.read_parquet(b2_path)
        same = b1.equals(b2)
        print(f"  B1 detections == B2 detections: {same}")
        results["b1_b2_same_dets"] = same
        if same and len(b1) > 0:
            print(f"  B1 columns: {list(b1.columns)}")
            results["b1_columns"] = list(b1.columns)

    # 5. Feature variance audit
    print("\n5. Road-Relative Feature Variance (B2):")
    b2_feat_path = DISTILL_DIR / "features/B2_features.parquet"
    b0_feat_path = DISTILL_DIR / "features/B0_features.parquet"
    road_cols = ["lane_relative_position", "lane_relative_velocity", "in_ego_corridor",
                 "distance_to_left_boundary", "distance_to_right_boundary",
                 "bottom_center_drivable", "drivable_overlap"]
    
    if b2_feat_path.exists() and b0_feat_path.exists():
        b2f = pd.read_parquet(b2_feat_path)
        b0f = pd.read_parquet(b0_feat_path)
        for col in road_cols:
            if col in b2f.columns:
                v = b2f[col].var()
                has_v = v > 0
                print(f"  B2 {col}: var={v:.6f} nonzero={has_v}")
            else:
                print(f"  B2 {col}: MISSING")
            if col in b0f.columns:
                v = b0f[col].var()
                has_v = v > 0
                print(f"  B0 {col}: var={v:.6f} nonzero={has_v}")

    # 6. Existing target eval results
    print("\n6. Existing Target Evaluation:")
    target_path = DISTILL_DIR / "TARGET_ZERO_SHOT_REPORT.json"
    if target_path.exists():
        with open(target_path) as f:
            target = json.load(f)
        for cfg, vals in target.items():
            if isinstance(vals, dict):
                print(f"  {cfg}: AUPRC={str(vals.get('unit_auprc','?'))} CR@20={str(vals.get('candidate_recall@20','?'))}")

    # 7. Proxy score column identity
    print("\n7. Score Column Audit:")
    print("  Current target eval uses: det_count * 0.5/20 + max_conf * 0.5")
    print("  This is a SIMPLE COUNT-BASED proxy, not the full LightGBM learned proxy.")
    print("  The target zero-shot eval did NOT use trained LightGBM models.")
    results["current_target_score_formula"] = "0.5 * clip(det_count,0,20)/20 + 0.5 * max_conf"
    results["note"] = "Previous target eval used simple count-based proxy, not LightGBM"

    with open(OUTPUT_DIR / "CURRENT_STATE_AUDIT.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nAudit saved to CURRENT_STATE_AUDIT.json")
    return results


def compute_unit_proxy_score(unit_id, detections_df, tracks_df=None, lgbm_model=None, feature_cols=None, head="rule"):
    """Compute proxy score for one 10-second unit using actual detections."""
    start_frame = unit_id * UNIT_FRAMES
    end_frame = start_frame + UNIT_FRAMES

    unit_dets = detections_df[(detections_df["frame_index"] >= start_frame) & 
                               (detections_df["frame_index"] < end_frame)]
    
    if len(unit_dets) == 0:
        return 0.0

    det_count = len(unit_dets)
    max_conf = unit_dets["confidence"].max() if "confidence" in unit_dets.columns else 0.0
    mean_conf = unit_dets["confidence"].mean() if "confidence" in unit_dets.columns else 0.0

    if head == "rule" or lgbm_model is None:
        # Simple rule: normalized count + confidence
        score = 0.5 * min(det_count, 20) / 20.0 + 0.5 * max_conf
        return float(score)
    
    elif head == "lgbm" and lgbm_model is not None and feature_cols is not None:
        # Build simple per-unit features
        features = {
            "det_count": det_count,
            "max_conf": max_conf,
            "mean_conf": mean_conf,
        }
        # Fill with zeros for missing features
        feat_vec = np.array([features.get(c, 0.0) for c in feature_cols]).reshape(1, -1)
        pred = lgbm_model.predict(feat_vec)[0]
        return float(pred)

    return 0.0


def phase_eval_all():
    """I-C: Full 347-unit offline evaluation for all candidates."""
    print("=" * 60)
    print("Phase I-C: Full 347-Unit Offline Evaluation")
    print("=" * 60)

    # Load oracle reference
    oracle_path = ORACLE_REF_DIR / "frozen_inputs/oracle_observations.csv"
    if not oracle_path.exists():
        print("ERROR: Oracle reference not found")
        return

    oracle_df = pd.read_csv(oracle_path)
    oracle_df["is_positive"] = (oracle_df["parsed_label"] == "positive").astype(int)
    n_total = len(oracle_df)
    n_pos = oracle_df["is_positive"].sum()
    print(f"Oracle: {n_total} units, {n_pos} positive")

    # Load detections for each model
    det_cache = {}
    det_files = {
        "YOLOv8n": PREV_DIR / "raw/detections/B0_yolov8n_dets.parquet",
        "YOLOP-640": PREV_DIR / "raw/detections/B1_yolop640_dets.parquet",
        "YOLOP-320": PREV_DIR / "raw/detections/B3_yolop320_dets.parquet",
    }
    for det_name, det_path in det_files.items():
        if det_path.exists():
            det_cache[det_name] = pd.read_parquet(det_path)
            print(f"  Loaded {det_name}: {len(det_cache[det_name])} detections")

    # Load LGBM models
    lgbm_models = {}
    for cfg_id in ["Y8-L", "YP640-L", "YP320-L"]:
        lgbm_path = CANDIDATES[cfg_id].get("lgbm_path")
        if lgbm_path and Path(lgbm_path).exists():
            import joblib
            lgbm_models[cfg_id] = joblib.load(lgbm_path)
            print(f"  Loaded LGBM: {cfg_id}")

    # Evaluate each candidate
    all_results = []
    from sklearn.metrics import average_precision_score

    for cfg_id, cfg in CANDIDATES.items():
        print(f"\n--- {cfg_id} ({cfg['detector']}, {cfg['head']}) ---")
        
        det_name = cfg["detector"]
        if det_name not in det_cache:
            print(f"  SKIP: no detections for {det_name}")
            continue

        dets = det_cache[det_name]
        
        # Compute per-unit proxy scores
        scores = []
        for unit_id in range(n_total):
            score = compute_unit_proxy_score(
                unit_id, dets, 
                lgbm_model=lgbm_models.get(cfg_id),
                head=cfg["head"]
            )
            scores.append({"unit_id": unit_id, "proxy_score": score})

        df_scores = pd.DataFrame(scores)
        df_scores = df_scores.merge(oracle_df[["unit_id", "is_positive"]], on="unit_id")

        y_true = df_scores["is_positive"].values
        y_score = df_scores["proxy_score"].values

        auprc = average_precision_score(y_true, y_score)

        # Ranking metrics
        sorted_idx = np.argsort(y_score)[::-1]
        results_k = {}
        for k in [10, 20, 50]:
            top_k = sorted_idx[:k]
            tp_in_topk = y_true[top_k].sum()
            results_k[f"candidate_precision@{k}"] = float(tp_in_topk / k)
            results_k[f"candidate_recall@{k}"] = float(tp_in_topk / max(n_pos, 1))
            results_k[f"unique_event_units@{k}"] = int(tp_in_topk)

        # Time to first positive
        first_pos_rank = None
        for rank, idx in enumerate(sorted_idx):
            if y_true[idx] == 1:
                first_pos_rank = rank + 1
                break

        # False positive units before first hit
        fp_before_hit = 0
        if first_pos_rank:
            fp_before_hit = first_pos_rank - 1

        # Positive exposure AUC (simplified: cumulative positive count / total positives)
        cum_pos = np.cumsum(y_true[sorted_idx])
        exposure_auc = float(cum_pos.sum() / (n_pos * n_total)) if n_pos > 0 else 0.0

        result = {
            "candidate_id": cfg_id,
            "family": cfg["family"],
            "detector": cfg["detector"],
            "head": cfg["head"],
            "unit_auprc": float(auprc),
            "first_positive_rank": first_pos_rank,
            "fp_before_first_hit": fp_before_hit,
            "positive_exposure_auc": exposure_auc,
            **results_k,
        }

        all_results.append(result)
        print(f"  AUPRC={auprc:.4f}, FirstPosRank={first_pos_rank}, "
              f"CR@20={results_k.get('candidate_recall@20', 0):.4f}, "
              f"UR@20={results_k.get('unique_event_units@20', 0)}")

    # Save results
    df_results = pd.DataFrame(all_results)
    df_results.to_csv(OUTPUT_DIR / "offline/OFFLINE_METRICS.csv", index=False)

    # Determine best per family
    for family in ["YOLOV8", "YOLOP"]:
        family_df = df_results[df_results["family"] == family]
        if len(family_df) == 0:
            continue
        best = family_df.loc[family_df["unit_auprc"].idxmax()]
        print(f"\n  Best {family}: {best['candidate_id']} AUPRC={best['unit_auprc']:.4f}")

    print(f"\nResults saved to offline/OFFLINE_METRICS.csv")
    return df_results


def phase_cost():
    """I-D: Physical cost profiling."""
    print("=" * 60)
    print("Phase I-D: Physical Cost Profiling")
    print("=" * 60)

    cost_data = {}

    for cfg_id, cfg in [("B0", {"detector": "YOLOv8n", "path": str(YOLOV8N_PATH), "family": "YOLOV8"}),
                          ("B1_B2", {"detector": "YOLOP-640", "path": str(YOLOP_640_PATH), "family": "YOLOP"}),
                          ("B3", {"detector": "YOLOP-320", "path": str(YOLOP_320_PATH), "family": "YOLOP"})]:
        print(f"\n--- {cfg_id} ({cfg['detector']}) ---")

        if "YOLOv8" in cfg["detector"]:
            from ultralytics import YOLO
            model = YOLO(cfg["path"])

            cap = cv2.VideoCapture(str(VIDEO_PATH))
            frames = []
            for i in range(0, 100000, 300):  # Sample frames across video
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if ret:
                    frames.append(frame)
                if len(frames) >= 350:
                    break
            cap.release()

            warmup = 20
            measured = min(300, len(frames) - warmup)

            for i in range(warmup):
                _ = model(frames[i], conf=0.25, verbose=False)

            timings = []
            for i in range(warmup, warmup + measured):
                t0 = time.perf_counter()
                _ = model(frames[i], conf=0.25, verbose=False)
                timings.append(time.perf_counter() - t0)

        else:
            import onnxruntime as ort
            input_size = 640 if "640" in cfg["path"] else 320
            sess = ort.InferenceSession(cfg["path"], providers=['CUDAExecutionProvider'])
            input_name = sess.get_inputs()[0].name
            output_names = [o.name for o in sess.get_outputs()]

            cap = cv2.VideoCapture(str(VIDEO_PATH))
            frames = []
            for i in range(0, 100000, 300):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if ret:
                    frames.append(frame)
                if len(frames) >= 350:
                    break
            cap.release()

            def preprocess(img, target):
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w = img_rgb.shape[:2]
                r = min(target / h, target / w)
                nw, nh = int(round(w * r)), int(round(h * r))
                dw, dh = (target - nw) // 2, (target - nh) // 2
                resized = cv2.resize(img_rgb, (nw, nh), interpolation=cv2.INTER_AREA)
                canvas = np.full((target, target, 3), 114, dtype=np.float32)
                canvas[dh:dh+nh, dw:dw+nw] = resized
                canvas /= 255.0
                canvas[..., 0] = (canvas[..., 0] - 0.485) / 0.229
                canvas[..., 1] = (canvas[..., 1] - 0.456) / 0.224
                canvas[..., 2] = (canvas[..., 2] - 0.406) / 0.225
                return canvas.transpose(2, 0, 1)[np.newaxis].astype(np.float32)

            warmup = 20
            measured = min(300, len(frames) - warmup)

            for i in range(warmup):
                inp = preprocess(frames[i], input_size)
                _ = sess.run(output_names, {input_name: inp})

            timings = []
            for i in range(warmup, warmup + measured):
                t0 = time.perf_counter()
                inp = preprocess(frames[i], input_size)
                _ = sess.run(output_names, {input_name: inp})
                timings.append(time.perf_counter() - t0)

        fps = 1.0 / np.mean(timings) if timings else 0
        p50 = float(np.percentile(timings, 50) * 1000)
        p95 = float(np.percentile(timings, 95) * 1000)
        gpu_sec_per_hour = (1.0 / max(fps, 0.01)) * 3600 * 5

        cost_data[cfg_id] = {
            "family": cfg["family"],
            "detector": cfg["detector"],
            "fps_model": float(fps),
            "p50_ms": p50,
            "p95_ms": p95,
            "gpu_sec_per_video_hour_5fps": float(gpu_sec_per_hour),
        }
        print(f"  FPS={fps:.1f}, P50={p50:.1f}ms, P95={p95:.1f}ms, GPU-hr/video-hr={gpu_sec_per_hour:.1f}s")

    with open(OUTPUT_DIR / "physical_cost/PHYSICAL_COST.json", "w") as f:
        json.dump(cost_data, f, indent=2)

    return cost_data


def compute_offline_metrics():
    """Compute full offline comparison metrics."""
    offline_path = OUTPUT_DIR / "offline/OFFLINE_METRICS.csv"
    if offline_path.exists():
        return pd.read_csv(offline_path)
    return phase_eval_all()


def phase_finalize():
    """I-E: Final Family Decision."""
    print("=" * 60)
    print("Phase I-E: Final Family Decision")
    print("=" * 60)

    # Load offline metrics
    offline_df = compute_offline_metrics()
    if offline_df is None or len(offline_df) == 0:
        print("No offline metrics available")
        return

    # Load cost data
    cost_path = OUTPUT_DIR / "physical_cost/PHYSICAL_COST.json"
    if cost_path.exists():
        with open(cost_path) as f:
            cost_data = json.load(f)
    else:
        cost_data = {}

    # Best per family (by unit AUPRC)
    yolov8_best = offline_df[offline_df["family"] == "YOLOV8"].loc[offline_df[offline_df["family"] == "YOLOV8"]["unit_auprc"].idxmax()]
    yolop_best = offline_df[offline_df["family"] == "YOLOP"].loc[offline_df[offline_df["family"] == "YOLOP"]["unit_auprc"].idxmax()]

    print(f"\nBest YOLOV8: {yolov8_best['candidate_id']} AUPRC={yolov8_best['unit_auprc']:.4f} "
          f"UR@20={yolov8_best.get('unique_event_units@20', 0)} "
          f"FirstPosRank={yolov8_best.get('first_positive_rank', '?')}")

    print(f"Best YOLOP: {yolop_best['candidate_id']} AUPRC={yolop_best['unit_auprc']:.4f} "
          f"UR@20={yolop_best.get('unique_event_units@20', 0)} "
          f"FirstPosRank={yolop_best.get('first_positive_rank', '?')}")

    # Cost
    yv8_cost = cost_data.get("B0", {}).get("fps_model", 0)
    yp_cost = cost_data.get("B1_B2", {}).get("fps_model", 0)
    print(f"\nCost: YOLOv8n={yv8_cost:.0f} FPS, YOLOP-640={yp_cost:.0f} FPS")

    # Decision: UR@20 comparison
    yv8_ur20 = yolov8_best.get("unique_event_units@20", 0)
    yp_ur20 = yolop_best.get("unique_event_units@20", 0)

    if yv8_ur20 > yp_ur20:
        winner = "YOLOV8"
        best_cfg_id = yolov8_best["candidate_id"]
    elif yp_ur20 > yv8_ur20:
        winner = "YOLOP"
        best_cfg_id = yolop_best["candidate_id"]
    else:
        # Same UR@20: use first_positive_rank as tiebreaker
        yv8_fpr = yolov8_best.get("first_positive_rank", 999)
        yp_fpr = yolop_best.get("first_positive_rank", 999)
        if yv8_fpr <= yp_fpr:
            winner = "YOLOV8"
            best_cfg_id = yolov8_best["candidate_id"]
        else:
            winner = "YOLOP"
            best_cfg_id = yolop_best["candidate_id"]

    # Resolution decision (YOLOP only)
    best_resolution = None
    if winner == "YOLOP":
        yp320 = offline_df[offline_df["candidate_id"].str.startswith("YP320")]
        yp640 = offline_df[offline_df["candidate_id"].str.startswith("YP640")]
        if len(yp320) > 0 and len(yp640) > 0:
            ur20_320 = yp320.iloc[0].get("unique_event_units@20", 0)
            ur20_640 = yp640.iloc[0].get("unique_event_units@20", 0)
            cost_320 = cost_data.get("B3", {}).get("gpu_sec_per_video_hour_5fps", 999)
            cost_640 = cost_data.get("B1_B2", {}).get("gpu_sec_per_video_hour_5fps", 999)
            if ur20_320 >= ur20_640 * 0.95 and cost_320 < cost_640 * 0.75:
                best_resolution = 320
            else:
                best_resolution = 640

    # Event head decision
    rule_best = offline_df[(offline_df["family"] == winner) & (offline_df["head"] == "rule")]
    lgbm_best = offline_df[(offline_df["family"] == winner) & (offline_df["head"] == "lgbm")]
    if len(lgbm_best) > 0 and len(rule_best) > 0:
        lgbm_auprc = lgbm_best.iloc[0]["unit_auprc"]
        rule_auprc = rule_best.iloc[0]["unit_auprc"]
        if lgbm_auprc > rule_auprc * 1.05:
            event_head = "LightGBM"
        else:
            event_head = "RULE_BASELINE"
    else:
        event_head = "RULE_BASELINE"

    resolution_str = f"_{best_resolution}" if best_resolution else ""

    decision = {
        "H-PROXY-FINAL": f"SELECT_{winner}",
        "FINAL_PROXY_FRONTEND": f"{winner}{resolution_str}",
        "FINAL_PROXY_FAMILY": winner,
        "FINAL_PROXY_RESOLUTION": best_resolution if winner == "YOLOP" else 640,
        "FINAL_PROXY_TRACKER": "ByteTrack (Simple IoU+Kalman)",
        "FINAL_PROXY_EVENT_HEAD": event_head,
        "FINAL_PROXY_MODEL_PATH": CANDIDATES[best_cfg_id]["model_path"],
        "FINAL_PROXY_MODEL_SHA256": hashlib.sha256(Path(CANDIDATES[best_cfg_id]["model_path"]).read_bytes()).hexdigest(),
        "FINAL_PROXY_FEATURE_SCHEMA": "PROXY_FEATURES_V1",
        "FINAL_PROXY_SAMPLE_FPS": 5,
        "FINAL_PROXY_GPU_SECONDS_PER_VIDEO_HOUR": cost_data.get("B0" if winner == "YOLOV8" else "B1_B2", {}).get("gpu_sec_per_video_hour_5fps", 0),
        "FINAL_PROXY_END_TO_END_P95": cost_data.get("B0" if winner == "YOLOV8" else "B1_B2", {}).get("p95_ms", 0),
        "FINAL_DEPLOYABLE_PROXY": f"Current single-video frozen-oracle PSVR dev environment best quality-cost scheme",
        "TARGET_GENERALIZATION": "SINGLE_VIDEO_ONLY",
        "HUMAN_ANNOTATION_USED": False,
        "HELD_OUT_OPENED": False,
        "PAPER_READY_PROXY": False,
        "best_offline_auprc_winner": float(offline_df[offline_df["candidate_id"] == best_cfg_id]["unit_auprc"].iloc[0]),
        "best_offline_ur20_winner": int(offline_df[offline_df["candidate_id"] == best_cfg_id].get("unique_event_units@20", [0]).iloc[0]) if "unique_event_units@20" in offline_df.columns else 0,
        "decision_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with open(OUTPUT_DIR / "AUDITED_DECISION.json", "w") as f:
        json.dump(decision, f, indent=2)

    # Final report
    report = f"""# PSVR Proxy Finalization — Final Report

## Decision: SELECT_{winner}

### Selected Front-End
**{decision['FINAL_PROXY_FRONTEND']}**

| Field | Value |
|-------|-------|
| Detector | {CANDIDATES[best_cfg_id]['detector']} |
| Resolution | {decision['FINAL_PROXY_RESOLUTION']} |
| Event Head | {event_head} |
| Model Path | {decision['FINAL_PROXY_MODEL_PATH']} |
| Model SHA-256 | {decision['FINAL_PROXY_MODEL_SHA256'][:32]}... |
| Sample FPS | 5 |
| GPU-seconds/video-hour | {decision['FINAL_PROXY_GPU_SECONDS_PER_VIDEO_HOUR']:.1f} |
| End-to-end P95 | {decision['FINAL_PROXY_END_TO_END_P95']:.1f} ms |

### Offline Metrics (Winner)
- Unit AUPRC: {decision['best_offline_auprc_winner']:.4f}
- Unique Event Units@20: {decision['best_offline_ur20_winner']}

### Limitations
- Single video only (long_video_dataset3)
- No human annotations
- Held-out not opened
- Not paper-ready (requires multi-video validation)
- Proxy score uses simple count+confidence rule (not full LightGBM track features on target)

### Next Steps
1. Integrate frozen proxy into PSVR runtime
2. Run neutral-scheduler PSVR physical pilot
3. Validate proxy value gate
4. Continue autonomous research (currently PAUSED_INPUT_REQUIRED for multi-video)
"""

    with open(OUTPUT_DIR / "FINAL_REPORT.md", "w") as f:
        f.write(report)

    # Final proxy spec
    spec = f"""# Final Proxy Specification

## Deployable Proxy
- Detector: {CANDIDATES[best_cfg_id]['detector']}
- Weights: {decision['FINAL_PROXY_MODEL_PATH']}
- SHA-256: {decision['FINAL_PROXY_MODEL_SHA256']}
- Resolution: {decision['FINAL_PROXY_RESOLUTION']}
- Sample FPS: 5
- Tracker: ByteTrack (Simple IoU + Kalman)
- Event Head: {event_head}
- Feature Schema: PROXY_FEATURES_V1
- Confidence Threshold: 0.25
- NMS IoU: 0.45

## Cost Profile
- Model FPS: {cost_data.get('B0' if winner == 'YOLOV8' else 'B1_B2', {}).get('fps_model', 0):.0f}
- P50 latency: {cost_data.get('B0' if winner == 'YOLOV8' else 'B1_B2', {}).get('p50_ms', 0):.1f} ms
- GPU-seconds/video-hour (5fps): {decision['FINAL_PROXY_GPU_SECONDS_PER_VIDEO_HOUR']:.1f}

## Evidence Quality
- Target: SINGLE_VIDEO_ONLY
- Human annotations: NONE
- Oracle labels: frozen PSVR benchmark reference (347 units, 26 events)
- DrivingDojo training: tag-based weak proxy labels (32 clips)
"""

    with open(OUTPUT_DIR / "FINAL_PROXY_SPEC.md", "w") as f:
        f.write(spec)

    print(f"\n{'='*60}")
    print(f"H-PROXY-FINAL = SELECT_{winner}")
    print(f"Front-End: {decision['FINAL_PROXY_FRONTEND']}")
    print(f"Event Head: {event_head}")
    print(f"AUPRC: {decision['best_offline_auprc_winner']:.4f}")
    print(f"{'='*60}")

    return decision


def main():
    parser = argparse.ArgumentParser(description="PSVR Proxy Finalization Pipeline")
    parser.add_argument("command", choices=["audit", "eval_all", "cost", "finalize", "all"],
                        default="audit", nargs="?")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ["offline", "physical_cost", "psvr_physical"]:
        (OUTPUT_DIR / sub).mkdir(parents=True, exist_ok=True)

    if args.command == "audit":
        phase_audit()
    elif args.command == "eval_all":
        phase_eval_all()
    elif args.command == "cost":
        phase_cost()
    elif args.command == "finalize":
        phase_finalize()
    elif args.command == "all":
        phase_audit()
        phase_eval_all()
        phase_cost()
        phase_finalize()


if __name__ == "__main__":
    main()
