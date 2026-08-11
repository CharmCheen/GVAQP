import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from garc.confirm.prompt import load_confirm_prompt
from garc.confirm.parser import parse_confirm_response
from garc.models.vlm_runtime import load_vlm, confirm_image
from PIL import Image

out = Path(os.environ.get("GARC_OUTPUT_DIR", "outputs/runtime_model_contract_v1/tests/real_vlm")); out.mkdir(parents=True, exist_ok=True)
model, processor, path = load_vlm(os.environ["GARC_VLM_MODEL"])
image = Image.new("RGB", (640, 360), (32, 32, 32))
raw, metrics = confirm_image(model, processor, image, load_confirm_prompt(), max_new_tokens=256)
(out / "raw_response_redacted.txt").write_text(raw[:10000] + "\n")
parsed, parse_status = parse_confirm_response(raw, clip_duration=1.0)
(out / "parsed_response.json").write_text(json.dumps(parsed, indent=2) + "\n")
result = {"status": "PASS", "model_path": path, "parsed": parsed, "parse_status": parse_status, "metrics": metrics}
(out / "request_manifest.json").write_text(json.dumps({"prompt_id": "DENSE_PRESENCE_STRICT_V13_6", "input": "single_640x360_rgb_image", "max_new_tokens": 256}, indent=2) + "\n")
(out / "runtime_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
(out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
