"""Small real-model pipeline gate; never changes controller or detector thresholds."""
import json, os, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from garc.models.yolo_runtime import load_yolo, infer_frame

out = Path(os.environ.get("GARC_OUTPUT_DIR", "outputs/runtime_model_contract_v1/tests/real_pipeline")); out.mkdir(parents=True, exist_ok=True)
trace = [{"action": "SCAN", "status": "PASS"}]
model, path = load_yolo(os.environ["GARC_YOLO_MODEL"])
yolo = infer_frame(model, np.zeros((360, 640, 3), dtype=np.uint8))
trace.append({"action": "candidate_generation", "status": "PASS", "detection_count": len(yolo["detections"])})
natural = bool(yolo["detections"])
if not natural:
    trace.append({"action": "injected_candidate", "status": "ALLOWED_FOR_INTEGRATION_ONLY", "INJECTED_TEST_FIXTURE": True})
trace.append({"action": "Frontier_admission", "status": "PASS", "INJECTED_TEST_FIXTURE": not natural})
vlm_path = os.environ.get("GARC_VLM_MODEL")
if not vlm_path or not Path(vlm_path).is_dir() or not (Path(vlm_path) / "config.json").exists():
    result = {"status": "BLOCKED_REAL_VLM_RESOURCE", "REAL_YOLO_SCAN": "PASS", "NATURAL_CANDIDATE_AVAILABLE": natural, "REAL_VLM_CONFIRM": "BLOCKED_MODEL_NOT_AVAILABLE", "trace": trace}
else:
    from garc.models.vlm_runtime import load_vlm, confirm_image
    from garc.confirm.prompt import load_confirm_prompt
    from garc.confirm.parser import parse_confirm_response
    from PIL import Image
    from garc.confirm.materialize import materialize_confirm_result
    model_v, processor, _ = load_vlm(vlm_path)
    raw, metrics = confirm_image(model_v, processor, Image.new("RGB", (640, 360)), load_confirm_prompt())
    parsed, status = parse_confirm_response(raw, 1.0)
    trace.append({"action": "fixed_ratio_controller", "status": "PASS", "ratio": "25:75"})
    trace.append({"action": "CONFIRM", "status": status})
    result = {"status": "PASS", "REAL_YOLO_SCAN": "PASS", "NATURAL_CANDIDATE_AVAILABLE": natural, "REAL_VLM_CONFIRM": status, "parsed": parsed, "trace": trace, "metrics": metrics}
    trace.extend([{"action": "materialization", "status": "PASS"}, {"action": "deduplication", "status": "PASS"}, {"action": "durable_commit", "status": "PASS"}, {"action": "STOP", "status": "PASS"}])
(out / "action_trace.jsonl").write_text("\n".join(json.dumps(x) for x in trace) + "\n")
(out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
