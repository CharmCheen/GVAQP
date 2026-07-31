import json, os
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUT = ROOT / "outputs/runtime_model_contract_v1/audits"
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = Path(os.environ.get("GARC_SOURCE_WORKTREE", "/tmp/garc_runtime_contract_source"))
COMMIT = "5047241b0561b911b9a519b18e8e7591c0074e70"

def write(name, text):
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")

write("MODEL_IDENTITY_EVIDENCE.md", "# Runtime model identity evidence\n\n" +
      "SOURCE_REPOSITORY_REQUESTED: /qiuyeqing/llama_prl/G-ARC\n" +
      f"SOURCE_REPOSITORY_USED: {SOURCE} (local repository /root/charm/GVAQP, exact commit, remote differs)\n" +
      f"SOURCE_COMMIT: {COMMIT}\n\n" +
      "- YOLO: `yolov8n.pt`; formal proxy code uses Ultralytics; SHA-256 `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`.\n" +
      "- VLM: `Qwen3-VL-32B-Instruct`; the tracked physical model manifest records content hash `c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210`.\n" +
      "- Earlier `test_vlm` Qwen3-VL-8B references are test/legacy evidence and do not override the formal physical chain.\n" +
      "- HF revision `0cfaf48183f594c314753d30a4c4974bc75f3ccb` was accepted only after all available small files matched the source manifest byte-for-byte.\n")
write("BACKEND_EVIDENCE.md", "# Backend evidence\n\n" +
      "Formal source uses `Qwen3VLForConditionalGeneration.from_pretrained`, `AutoProcessor`, `torch.bfloat16`, `device_map=auto`, `trust_remote_code=True`, greedy generation, and `max_new_tokens=256`. Visual messages use RGB PIL video frames at 2 FPS.\n\n" +
      "YOLO uses Ultralytics `YOLO(path).predict(imgsz=640, conf=0.25, iou=0.45, device=\"cuda\")` with classes `[0,1,2,3,5,7]`.\n")
write("MODEL_REFERENCE_INVENTORY.csv", "component,candidate,source_path,evidence_level,status,conflict\nYOLO,yolov8n.pt,scripts/run_psvr_two_video_proxy.py,E1,EVIDENCE_MATCH,YOLOv8x is alternate\nVLM,Qwen3-VL-32B-Instruct,AQP_Algorithm_Invention_Sprint_v1/physical/MODEL_MANIFEST.csv,E2,EVIDENCE_MATCH,Qwen3-VL-8B is legacy test-only\nVLM_PROVIDER,Qwen/Qwen3-VL-32B-Instruct,external snapshot validation,E2+external,IDENTITY_HASH_VALIDATED,source did not record provider\n")
write("PROMPT_AND_PARSER_INVENTORY.csv", "component,source_path,evidence_level,hash,status\nprompt,Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/oracle/oracle_prompt.txt,E2,12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33,EVIDENCE_MATCH\nparser,src/garc_eval/aqp_invention_v1/contract.py and frozen parse_response binding,E1/E2,c02b545c0c5d2969508eea9a5470f0cb67d71282b25059948106504f9f4edd31,SEMANTICS_RECOVERED\n")
print(OUT)
