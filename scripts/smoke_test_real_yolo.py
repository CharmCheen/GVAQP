import json, os, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from garc.models.yolo_runtime import load_yolo, infer_frame
from garc.models.manifest import sha256_file

out = Path(os.environ.get("GARC_OUTPUT_DIR", "outputs/runtime_model_contract_v1/tests/real_yolo")); out.mkdir(parents=True, exist_ok=True)
path = Path(os.environ["GARC_YOLO_MODEL"])
model, path = load_yolo(path)
frame = np.zeros((360, 640, 3), dtype=np.uint8)
r = infer_frame(model, frame)
result = {"status": "PASS", "model_path": str(path), "sha256": sha256_file(path), "input_shape": list(frame.shape), **r}
(out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
