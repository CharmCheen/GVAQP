#!/usr/bin/env python3
"""Phase 1: Input discovery. Check all assets before proceeding."""
import json, os, sys, yaml, torch

ROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1"
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.makedirs(f"{ROOT}/logs", exist_ok=True)

with open(f"{ROOT}/config/model_paths.yaml") as f:
    paths = yaml.safe_load(f)

report = {"checks": [], "blockers": [], "warnings": [], "assets": {}}

def check(desc, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    report["checks"].append({"check": desc, "status": status, "detail": detail})
    if not condition:
        report["blockers"].append(desc)

# 1. Canonical table
canon_path = paths["canonical_table"]
exists = os.path.isfile(canon_path)
check("Canonical dataset3 table exists", exists, canon_path)
if exists:
    import pandas as pd
    df = pd.read_csv(canon_path)
    report["assets"]["n_anchors"] = len(df)
    report["assets"]["n_positive"] = int(df["is_positive"].sum())
    report["assets"]["n_negative"] = int((~df["is_positive"].astype(bool)).sum())
    report["assets"]["n_clusters"] = int(df["event_cluster_id"].nunique())
    report["assets"]["n_singleton_clusters"] = int(df[df["is_singleton_cluster"]==True]["event_cluster_id"].nunique()) if "is_singleton_cluster" in df.columns else None
    report["assets"]["has_proxy_scores"] = "object_count_mean" in df.columns and "score_fusion_geometry_motion" in df.columns
    report["assets"]["has_oracle_labels"] = "oracle_label" in df.columns or "label" in df.columns
    report["assets"]["has_cluster_ids"] = "event_cluster_id" in df.columns
    report["assets"]["has_time_columns"] = "start_time_s" in df.columns and "end_time_s" in df.columns
    report["assets"]["columns"] = list(df.columns[:20])
    print(f"  Anchors: {len(df)}, positives: {report['assets']['n_positive']}, negatives: {report['assets']['n_negative']}, clusters: {report['assets']['n_clusters']}")

# 2. Source video
video_path = paths["source_video"]
video_exists = os.path.isfile(video_path)
check("Source video exists", video_exists, video_path)
if video_exists:
    report["assets"]["video_size_gb"] = round(os.path.getsize(video_path) / (1024**3), 2)

# 3. GLM-4.1V model
glm_path = paths["glm41v"]
glm_exists = os.path.isdir(glm_path) and os.path.isfile(f"{glm_path}/config.json")
check("GLM-4.1V model directory exists", glm_exists, glm_path)
if glm_exists:
    import json as _json
    with open(f"{glm_path}/config.json") as f:
        glm_cfg = _json.load(f)
    report["assets"]["glm_model_type"] = glm_cfg.get("model_type")
    report["assets"]["glm_arch"] = glm_cfg.get("architectures", [None])[0]

# 4. Qwen3-VL-32B model
qwen_path = paths["qwen32b"]
qwen_exists = os.path.isdir(qwen_path) and os.path.isfile(f"{qwen_path}/config.json")
check("Qwen3-VL-32B model directory exists", qwen_exists, qwen_path)
report["assets"]["qwen32b_available"] = qwen_exists

# 5. Try loading GLM processor
if glm_exists:
    try:
        from transformers import Glm4vProcessor
        proc = Glm4vProcessor.from_pretrained(glm_path, local_files_only=True)
        report["assets"]["glm_processor_loaded"] = True
        check("GLM-4.1V processor loads OK", True, f"type={type(proc).__name__}")
    except Exception as e:
        report["assets"]["glm_processor_loaded"] = False
        check("GLM-4.1V processor loads OK", False, str(e))

# 6. Try loading Qwen processor
if qwen_exists:
    try:
        from transformers import AutoProcessor
        proc = AutoProcessor.from_pretrained(qwen_path, trust_remote_code=True, local_files_only=True)
        report["assets"]["qwen_processor_loaded"] = True
        check("Qwen3-VL-32B processor loads OK", True, f"type={type(proc).__name__}")
    except Exception as e:
        report["assets"]["qwen_processor_loaded"] = False
        check("Qwen3-VL-32B processor loads OK", False, str(e))

# 7. GPU
gpu_avail = torch.cuda.is_available()
check("GPU available", gpu_avail)
if gpu_avail:
    report["assets"]["gpu_name"] = torch.cuda.get_device_name(0)
    report["assets"]["gpu_memory_gb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
    report["assets"]["cuda_version"] = torch.version.cuda

# 8. Dependencies
for mod in ["transformers", "torch", "cv2", "PIL", "numpy", "pandas"]:
    try:
        __import__(mod.replace("cv2","cv2"))
        if mod == "cv2":
            import cv2; report.setdefault("deps",{})[mod] = cv2.__version__
        elif mod == "PIL":
            from PIL import Image; report.setdefault("deps",{})[mod] = Image.__version__
        else:
            report.setdefault("deps",{})[mod] = "available"
    except:
        report.setdefault("deps",{})[mod] = "MISSING"
        report["warnings"].append(f"Dependency {mod} not found")

# Decision
n_blockers = len(report["blockers"])
if n_blockers == 0:
    decision = "PROCEED"
    report["summary"] = f"All {len(report['checks'])} checks passed. Ready to proceed."
else:
    decision = "BLOCKED"
    report["summary"] = f"{n_blockers} blocker(s) found. Cannot proceed."

report["decision"] = decision

with open(f"{ROOT}/logs/input_discovery.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print(f"\n{'='*60}")
print(f"Input Discovery: {decision}")
print(f"  Checks: {len(report['checks'])} total, {n_blockers} failed")
if decision == "BLOCKED":
    for b in report["blockers"]:
        print(f"  BLOCKER: {b}")
    print(f"\nDECISION: INPUT_ASSETS_MISSING_BLOCKED")
else:
    print(f"  Anchors: {report['assets'].get('n_anchors')}")
    print(f"  Positives: {report['assets'].get('n_positive')}")
    print(f"  Video: {report['assets'].get('video_size_gb', 'N/A')} GB")
    print(f"  GPU: {report['assets'].get('gpu_name', 'N/A')} ({report['assets'].get('gpu_memory_gb', 0)} GB)")
    print(f"\nDECISION: PROCEED")
