#!/usr/bin/env python3
"""Evidence-only recovery package for V7 runtime and V3 scan/proxy contract.

No model weights are loaded and no scan/inference is started.  The only replay
evidence recorded here is the already performed processor-only hash check.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/v3_runtime_recovery_v1"
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
V7 = BASE / "full_grid_preregistration_staged_v7_review_corrections"
MODEL = ROOT / "models/Qwen3-VL-32B-Instruct-FP8"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path): return json.loads(path.read_text())
def write_json(path: Path, value): path.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")
def write_csv(path: Path, rows: list[dict]):
    with path.open("w", newline="") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def version(name: str) -> str:
    try: return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: return "NOT_INSTALLED"

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    proc=load(V7/"FULL_GRID_PROCESSED_INPUT_MANIFEST.json")
    prereg=load(V7/"FULL_GRID_PREREGISTRATION.json")
    frozen=proc["processor_environment"]
    current={
      "python": platform.python_version(), "torch": version("torch"),
      "transformers":version("transformers"), "qwen_vl_utils":version("qwen-vl-utils"),
      "numpy":version("numpy"), "pillow":version("pillow"), "opencv":version("opencv-python"),
    }
    # cv2's runtime version is authoritative for this runner rather than its distribution label.
    import cv2
    current["opencv"]=cv2.__version__
    model_hashes={n:sha(MODEL/n) for n in ["config.json","generation_config.json","preprocessor_config.json","video_preprocessor_config.json","tokenizer_config.json","tokenizer.json","chat_template.json"]}
    replay=[
      {"video_id":"DALI","unit_id":"DALI_u0000","expected_tensor_hash":"9d46f7b1553945c07d67deb4ceaa0191b4f84915120b6ac6b668a3b8bde97b24","observed_tensor_hash":"9d46f7b1553945c07d67deb4ceaa0191b4f84915120b6ac6b668a3b8bde97b24","match":True},
      {"video_id":"HANGZHOU","unit_id":"HANGZHOU_u0000","expected_tensor_hash":"72352c99cd34526da9d909fb0bc80713aa17ca818d6788945a93f0f8db5a6a94","observed_tensor_hash":"72352c99cd34526da9d909fb0bc80713aa17ca818d6788945a93f0f8db5a6a94","match":True},
      {"video_id":"WUHAN","unit_id":"WUHAN_u0000","expected_tensor_hash":"9798aea1efd745540f9856298119881cad4b1c775dfdbc212f5089759bb2abd6","observed_tensor_hash":"9798aea1efd745540f9856298119881cad4b1c775dfdbc212f5089759bb2abd6","match":True},
    ]
    rows=[]
    for key in ["python","torch","transformers","qwen_vl_utils","numpy","pillow","opencv"]:
      value=frozen[key]; observed=current[key]; match=value==observed
      rows.append({"component":key,"frozen_value":value,"current_value":observed,
        "status":"EXACT_MATCH" if match else "VERSION_MISMATCH_PROCESSOR_HASH_COMPATIBLE_ON_3_UNITS",
        "material_to_output?":"OUTPUT_CRITICAL","evidence":"V7 FULL_GRID_PROCESSED_INPUT_MANIFEST.json; runner runtime_environment_identity(); processor-only tensor-hash replay"})
    for pkg in ["torchvision","tokenizers","accelerate","safetensors","flash-attn","decord","av"]:
      rows.append({"component":pkg,"frozen_value":"UNKNOWN_FROM_REPOSITORY","current_value":version(pkg),"status":"UNKNOWN","material_to_output?":"UNKNOWN_IMPACT","evidence":"not included in V7 runtime_environment_identity() and no V7 package lock/pip-freeze was found"})
    rows += [
      {"component":"cuda_runtime","frozen_value":"INFERRED_FROM_ARTIFACT: cu129 from torch 2.10.0+cu129","current_value":"12.9","status":"INFERRED_MATCH","material_to_output?":"UNKNOWN_IMPACT","evidence":"V7 processor manifest + nvidia-smi"},
      {"component":"cuda_driver","frozen_value":"UNKNOWN_FROM_REPOSITORY","current_value":"535.129.03","status":"UNKNOWN","material_to_output?":"UNKNOWN_IMPACT","evidence":"no V7 driver snapshot found"},
      {"component":"ffmpeg","frozen_value":"UNKNOWN_FROM_REPOSITORY","current_value":"UNKNOWN_NOT_CAPTURED","status":"UNKNOWN","material_to_output?":"UNKNOWN_IMPACT","evidence":"V7 uses OpenCV decode and stores frame hashes; no ffmpeg identity is bound"},
    ]
    write_csv(OUT/"V7_RUNTIME_DIFF.csv",rows)
    runtime={"status":"RECOVERED_SEMANTIC_PROCESSOR_IDENTITY_BUT_NOT_FULL_PACKAGE_LOCK","frozen_processor_environment":frozen,"current_processor_environment":current,"processor_class":proc["processor_class"],"processor_loading":{"class":"transformers.AutoProcessor","trust_remote_code":True,"local_files_only":True},"model":{"local_path":"models/Qwen3-VL-32B-Instruct-FP8","content_hash":prereg["model"]["content_hash"],"model_repo_revision":"UNKNOWN_FROM_REPOSITORY","model_files":model_hashes,"generation_override":prereg["decoding"]},"prompt":{"path":prereg["bindings"]["prompt"]["path"],"sha256":prereg["bindings"]["prompt"]["sha256"]},"replay":{"kind":"processor_only_no_checkpoint_no_generation","all_tensor_hashes_match":True,"cells":replay,"conclusion":"CURRENT_RUNTIME_OUTPUT_COMPATIBLE_FOR_FROZEN_PROCESSOR_INPUTS_ON_THREE_CHECKED_UNITS; semantic generation compatibility remains UNVERIFIED"},"runner_gate":"CURRENT_V7_RUNNER_REJECTS_VERSION_MISMATCH_BEFORE_MODEL_LOAD","full_lock_available":False,"unknown_packages":["torchvision","tokenizers","accelerate","safetensors","flash-attn","decord","av","cuda_driver","ffmpeg"]}
    write_json(OUT/"V7_RUNTIME_RECOVERY.json",runtime)
    (OUT/"environment_v7_frozen.yml").write_text("""# Evidence-derived V7 processor identity; not a complete dependency lock.\nname: gvaqp-v7-processor\nchannels:\n  - pytorch\n  - nvidia\n  - conda-forge\n  - pip\ndependencies:\n  - python=3.13.2\n  - pip\n  - pip:\n      - torch==2.10.0+cu129\n      - transformers==5.9.0\n      - qwen-vl-utils==0.0.14\n      - numpy==2.4.6\n      - pillow==12.1.1\n      - opencv-python==4.13.0\n# Exact pins above are V7 runtime_environment_identity fields.  No evidence\n# pins torchvision/tokenizers/accelerate/safetensors/decoder stack, so this\n# file must not be represented as a complete historical environment lock.\n""")
    scan={"status":"FROZEN_V3_SCAN_PROXY_PROTOCOL_NOT_RECOVERED","videos":["DALI","HANGZHOU","WUHAN"],"required_fields":{},"evidence":{"only_v3_status":"outputs/accelerated_event_query_v1/scan_candidates/STATUS.md = NOT_RUN — FROZEN_SCAN_EXECUTION_PENDING","historical_nontransferable_configs":["configs/runtime_models.yaml (general YOLOv8n model config)","scripts/run_partial_scan_pilot.py (different cut-in query/reference/protocol)","scripts/run_mfrp_previews.py (different historical preview experiment)"],"prohibited_promotion":"Historical YOLO artifacts are explicitly not promoted as new-query scan candidates."},"missing_frozen_fields":["scan sampling rate/temporal stride","input resolution/batch size","candidate construction/coverage rule","proxy feature schema and normalization","tracking applicability/configuration","output schema/finalizer","randomness/seeds","source commit and V3 scan manifest"],"decision":"NO_REPO_EVIDENCE_OF_A_FROZEN_V3_SCAN_PROXY_EXECUTION_CONTRACT"}
    write_json(OUT/"FROZEN_V3_SCAN_PROXY_PROTOCOL.json",scan)
    scans=[]
    for v,n in [("DALI",567),("HANGZHOU",561),("WUHAN",347)]: scans.append({"video_id":v,"expected_v3_units":n,"state":"NOT_FOUND","state_class":"NO_FROZEN_V3_CONTRACT_OR_EXECUTION_FOUND","candidate_table":"NOT_FOUND","proxy_table":"NOT_FOUND","historical_outputs":"NOT_REUSABLE_FOR_V3","validation_class":"NOT_FOUND","reason":"scan_candidates/STATUS.md declares execution pending; no V3 config/manifest/table exists"})
    write_csv(OUT/"SCAN_PROXY_STATE_AUDIT.csv",scans)
    evidence=f"""# V7 Runtime Evidence\n\n## Verified processor identity\n\nThe sealed V7 manifest binds Python {frozen['python']}, torch {frozen['torch']}, transformers {frozen['transformers']}, qwen-vl-utils {frozen['qwen_vl_utils']}, NumPy {frozen['numpy']}, Pillow {frozen['pillow']}, and OpenCV {frozen['opencv']}.  These are exactly the fields returned by `runtime_environment_identity()` and fail-closed by the V7 runner.\n\n## Current compatibility evidence\n\nCurrent versions differ only for transformers, NumPy and OpenCV among those fields.  A processor-only replay of unit zero from each independent video reconstructed the exact frozen tensor SHA-256 in all three cases.  This verifies decoded-frame identity, prompt rendering, processor class, token IDs/tensor bytes for three cells; it does **not** verify generated semantic text because no checkpoint was loaded.\n\n## Model / processor\n\nThe bound local checkpoint is `models/Qwen3-VL-32B-Instruct-FP8`, content hash `{prereg['model']['content_hash']}`. `AutoProcessor.from_pretrained(..., trust_remote_code=True, local_files_only=True)` is used.  Processor/tokenizer/chat-template hashes are in `V7_RUNTIME_RECOVERY.json`. No Hugging Face repository revision is recorded for this local FP8 copy; model repo/revision is therefore `UNKNOWN_FROM_REPOSITORY`.\n\n## Package-lock limit\n\nNo V7 requirements lock, conda lock, Docker image digest, pip-freeze, or frozen CUDA driver record was found. The V7 semantic processor identity is fully recorded; the complete installation dependency graph is not. `environment_v7_frozen.yml` is an evidence-derived isolated specification, not a claim of a complete historical lock.\n\n## Scan/proxy evidence\n\nThe only V3 scan artifact is `scan_candidates/STATUS.md`, created with the explicit state `NOT_RUN — FROZEN_SCAN_EXECUTION_PENDING`. The repository contains historical YOLO configurations, but their own provenance is for other queries/references and the V3 status explicitly forbids promoting them. Thus no frozen V3 scan/proxy contract can be recovered.\n"""
    (OUT/"V7_RUNTIME_EVIDENCE.md").write_text(evidence)
    decision={"decision":"TRUE_USER_INPUT_REQUIRED","V7_frozen_runtime":"SEMANTIC_PROCESSOR_IDENTITY_RECOVERED","current_runtime_compatibility":"PROCESSOR_INPUT_COMPATIBLE_ON_3_CHECKED_UNITS_BUT_SEALED_RUNNER_REJECTS_VERSION_STRING_MISMATCH","V3_scan_proxy_protocol":"NOT_RECOVERABLE_FROM_REPOSITORY","exactly_what_is_missing":"Frozen V3 scan/proxy execution contract (parameters, candidate/proxy schema, manifest and finalizer binding) for DALI/HANGZHOU/WUHAN","why_repo_cannot_recover_it":"Only an explicit NOT_RUN status exists; historical YOLO artifacts are documented as non-promoted and use different protocols.","minimum_user_input":"Provide/authorize a preregistered V3 scan/proxy contract, or explicitly authorize creation of one before execution. No V3 scan may be inferred from historical configurations.","user_input_required":"YES","v3_reference_release_can_resume":"NO","next_entrypoint":"After a frozen V3 scan contract exists, create an isolated environment from outputs/v3_runtime_recovery_v1/environment_v7_frozen.yml and validate V7 processor tensors before launch."}
    write_json(OUT/"RECOVERY_DECISION.json",decision)
    (OUT/"RECOVERY_DECISION.md").write_text("# V3 Runtime / Config Recovery Decision\n\nDecision:\nTRUE_USER_INPUT_REQUIRED\n\nMissing item:\nFrozen V3 scan/proxy execution contract.\n\nRepository search result:\nOnly `NOT_RUN — FROZEN_SCAN_EXECUTION_PENDING`; historical YOLO assets are explicitly non-promoted.\n\nWhy it cannot be recovered:\nNo V3 config, manifest, execution output, candidate/proxy schema, or finalizer binding exists.\n\nMinimum user input:\nProvide or authorize a preregistered V3 scan/proxy contract.\n\nV3 reference release can resume:\nNO\n")
    report="""# Final Runtime / Config Recovery Report\n\n1. **V7 frozen runtime:** semantic processor identity is exactly recovered from V7: Python 3.13.2, torch 2.10.0+cu129, transformers 5.9.0, qwen-vl-utils 0.0.14, NumPy 2.4.6, Pillow 12.1.1, OpenCV 4.13.0.\n2. **Current difference:** transformers 5.5.4, NumPy 2.2.6, OpenCV 5.0.0 differ; the other four identity fields match.\n3. **Output impact:** these three are output-critical by V7's own gate, but three cross-video processor tensor checks matched exactly. Generation semantics remain unverified without loading the model.\n4. **Runtime reconstruction:** the processor identity can be specified locally; a complete dependency lock cannot be reconstructed because no V7 lock/pip-freeze/container digest exists.\n5. **Old processor:** the sealed runner requires its identity strings; current processor behavior is compatible on checked inputs but cannot bypass that gate.\n6. **Scan config:** DALI/HANGZHOU/WUHAN do not have a frozen V3 scan configuration.\n7. **Scan execution:** it was never run under V3; it was not merely missing finalization.\n8. **Remaining compute:** V7 oracle remains 1,475 fresh calls (V7 estimate 16.593 A100 GPU-hours); V3 scan/proxy unit count/config/cost is unknown because no contract exists.\n9. **User input:** required only for the missing frozen V3 scan/proxy contract, not for model identity or source videos.\n10. **Resume:** no; reference release cannot legally resume until that contract is provided/authorized.\n"""
    (OUT/"FINAL_RECOVERY_REPORT.md").write_text(report)
    print(json.dumps(decision,indent=2,sort_keys=True))
if __name__=="__main__": main()
