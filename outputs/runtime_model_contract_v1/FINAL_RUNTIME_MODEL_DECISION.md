# FINAL RUNTIME MODEL DECISION

The frozen source path `/qiuyeqing/llama_prl/G-ARC` was absent. A read-only detached worktree from `/root/charm/GVAQP` at the exact requested source commit was used as a same-commit local evidence copy; its remote differs and this is recorded in the audit.

Runtime contract is established for YOLO and VLM identity, prompt, and parser semantics. The exact VLM snapshot was externally validated on small files, but its 66.7 GB download could not complete because HF/Xet metadata and transfer throughput were not usable on this machine. ModelScope was probed but not substituted.

YOLO real smoke passed with zero detections on the blank legal frame; zero is valid for this smoke. Existing curated SCAN, candidate, Frontier, fixed 25:75 controller, replay CONFIRM, materialization, deduplication, durable commit, STOP, and determinism tests remained passing. The new contract tests bring pytest to 36 passed.

SOURCE_REPOSITORY = /qiuyeqing/llama_prl/G-ARC (requested; absent)
SOURCE_COMMIT = 5047241b0561b911b9a519b18e8e7591c0074e70
TARGET_REPOSITORY = /root/charm/fresh-arcwork
TARGET_BASE_COMMIT = 6eed67d4cd0a734365eddedbee207c387385d03d

YOLO_IDENTITY = yolov8n.pt / YOLOv8n
YOLO_IDENTITY_EVIDENCE_LEVEL = E1_E2
YOLO_CONFIG_SOURCE = scripts/run_psvr_two_video_proxy.py; physical manifests
YOLO_MODEL_HASH = f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36
YOLO_DOWNLOAD = PASS
YOLO_LOAD = PASS
YOLO_GPU_INFERENCE = PASS
YOLO_SMOKE = PASS

VLM_IDENTITY = Qwen/Qwen3-VL-32B-Instruct
VLM_REVISION = 0cfaf48183f594c314753d30a4c4974bc75f3ccb
VLM_IDENTITY_EVIDENCE_LEVEL = E2_PLUS_EXTERNAL_HASH_VALIDATION
VLM_BACKEND = Transformers Qwen3VLForConditionalGeneration
VLM_PROMPT_SOURCE = strict oracle/oracle_prompt.txt, SHA-256 12187489e65828f1a5af829b649877e8e60927eff269c19278704f858781cf33
VLM_PARSER_SOURCE = frozen parse_response binding c02b545c...; semantics recovered in src/garc/confirm/parser.py
VLM_MODEL_HASH_OR_SNAPSHOT = source content c8104bb1b008e0ad876e4fd6c63bc44ab1a3631e04cb13220b9f9d736f1aa210; HF snapshot fixed
VLM_DOWNLOAD = BLOCKED_NETWORK_THROUGHPUT_OR_XET_METADATA
VLM_LOAD = NOT_RUN
VLM_GPU_INFERENCE = NOT_RUN
VLM_PARSE = UNIT_FIXTURES_PASS_ONLY
VLM_SMOKE = BLOCKED_REAL_VLM_RESOURCE

PROMPT_TEMPLATE_PARITY = PASS_SHA256
PARSER_PARITY = PASS_SOURCE_FAILURE_POLICY_FIXTURES
MATERIALIZATION_PARITY = PASS_EXISTING_34_TESTS

REAL_YOLO_SCAN = PASS
NATURAL_CANDIDATE_AVAILABLE = false_on_blank_smoke_frame
REAL_VLM_CONFIRM = BLOCKED_MODEL_NOT_AVAILABLE
REAL_NATURAL_END_TO_END = NOT_RUN
REAL_MODELS_WITH_INJECTED_CANDIDATE = BLOCKED_REAL_VLM
DURABLE_COMMIT = PASS_EXISTING_REPLAY_TEST
STOP = PASS_EXISTING_REPLAY_TEST

PYTEST = 36 PASSED
RELEASE_AUDIT = PASS_AFTER_EXCLUDING_ISOLATED_VENV
MODEL_WEIGHTS_TRACKED = false
RAW_MEDIA_TRACKED = false
SECRETS_FOUND = false

FILES_CHANGED =
configs/runtime_models.yaml
configs/runtime_models.example.yaml
configs/prompts/confirm_visual.yaml
configs/schemas/confirm_response.schema.json
src/garc/models/__init__.py
src/garc/models/resolver.py
src/garc/models/manifest.py
src/garc/models/yolo_runtime.py
src/garc/models/vlm_runtime.py
src/garc/confirm/prompt.py
src/garc/confirm/parser.py
scripts/audit_runtime_model_contract.py
scripts/download_runtime_models.py
scripts/smoke_test_real_yolo.py
scripts/smoke_test_real_vlm.py
scripts/smoke_test_real_pipeline.py
scripts/verify_release.py
docs/RUNTIME_MODELS.md
docs/REAL_MODEL_SETUP.md
tests/test_runtime_contract.py
COMMIT_CREATED = false
PUSH_PERFORMED = false

FINAL_STATUS = PARTIAL_PASS_YOLO_ONLY

NEXT_REQUIRED_ACTION = Resume the same fixed HF snapshot into an external writable cache, verify all 26 files against the source manifest, then run real VLM smoke and the real-model injected-candidate pipeline. Do not substitute a model or change the contract.
