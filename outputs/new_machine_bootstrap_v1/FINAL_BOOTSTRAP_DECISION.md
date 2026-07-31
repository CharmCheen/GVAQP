# Final bootstrap decision

The new-machine environment and the repository's replay/dry-run software chain are operational. The real YOLO/VLM stages cannot be completed honestly from this clone: no exact model identity, model path, VLM backend, or real visual CONFIRM operator exists in the local runtime. No substitute model, threshold change, Oracle call, algorithm edit, commit, or push was performed.

Completed: isolated Python 3.12 environment; PyTorch CUDA 12.1 on 8x A100; project/test install; pip check; compileall; 34 pytest passes; system media tooling; SCAN; candidate/Frontier; fixed 25:75; replay CONFIRM; materialization; utility deduplication; durable commit; STOP; two-run deterministic replay schema check.

The checked-in `verify_release.py` was run, but it scans `.venv` and rewrites the provenance file; its false failure was restored to a clean repository state and is recorded as tool-scope-only.

REPOSITORY = fresh-arcwork/G-ARC-Core
COMMIT = 6eed67d4cd0a734365eddedbee207c387385d03d
OS = Ubuntu 24.04.2 LTS
PYTHON = 3.12.3 (.venv)
GPU = NVIDIA A100-SXM4-80GB
GPU_COUNT = 8
GPU_VRAM = 80GB per GPU
NVIDIA_DRIVER = 535.129.03

ENVIRONMENT_CREATION = PASS
PYTORCH_VERSION = 2.5.1+cu121
PYTORCH_CUDA_RUNTIME = 12.1
TORCH_CUDA_AVAILABLE = true

PROJECT_INSTALL = PASS
PIP_CHECK = PASS
UNIT_TESTS = PASS (34 passed)
RELEASE_AUDIT = PARTIAL (tool scanned .venv; source audit clean)

YOLO_MODEL_ID = UNSPECIFIED_IN_CLONE
YOLO_MODEL_REVISION_OR_HASH = N/A
YOLO_DOWNLOAD = BLOCKED_MODEL_ID_UNSPECIFIED
YOLO_LOAD = BLOCKED_MODEL_ID_UNSPECIFIED
YOLO_GPU_INFERENCE = NOT_RUN
YOLO_SMOKE = BLOCKED_MISSING_RUNTIME_CHAIN

VLM_MODEL_ID = UNSPECIFIED_IN_CLONE
VLM_MODEL_REVISION = N/A
VLM_BACKEND = NOT_PRESENT
VLM_DOWNLOAD_BYTES = 0
VLM_DOWNLOAD = BLOCKED_MODEL_ID_UNSPECIFIED
VLM_LOAD = BLOCKED_MODEL_ID_UNSPECIFIED
VLM_GPU_INFERENCE = NOT_RUN
VLM_PARSE = NOT_RUN
VLM_SMOKE = BLOCKED_MISSING_RUNTIME_CHAIN

SCAN = PASS
CANDIDATE_GENERATION = PASS (replay/integration fixture)
FRONTIER = PASS
FIXED_RATIO_CONTROLLER = PASS
CONFIRM = PASS (replay adapter only)
MATERIALIZATION = PASS
DEDUPLICATION = PASS
DURABLE_COMMIT = PASS
STOP = PASS

SOFTWARE_PIPELINE_SMOKE = PASS
REAL_VLM_PIPELINE_SMOKE = BLOCKED_MISSING_MODEL_ID_AND_BACKEND
FULL_PIPELINE_SMOKE = BLOCKED_MISSING_MODEL_ID

FIXED_RATIO_ACTION_PARITY = 100% over frozen repository differential tests
DEADLINE_ADMISSION_PARITY = 100% over frozen repository differential tests
DETERMINISM = PASS for SCAN/action order/schema/durable replay; VLM not run

MODEL_WEIGHTS_TRACKED_BY_GIT = false
RAW_MEDIA_TRACKED_BY_GIT = false
SECRETS_FOUND = false

PORTABILITY_REPAIRS = none
FILES_CHANGED = outputs/new_machine_bootstrap_v1/* only (ignored); source restored clean
COMMIT_CREATED = false
PUSH_PERFORMED = false

FINAL_STATUS =
BLOCKED_MISSING_MODEL_ID

NEXT_REQUIRED_ACTION = provide the exact YOLO checkpoint ID/path and exact VLM model ID/revision plus the intended real visual CONFIRM backend/prompt/parser; then rerun only model and real-inference stages.
