# Local repository audit

- Repository: `/root/charm/fresh-arcwork`
- HEAD: `6eed67d4cd0a734365eddedbee207c387385d03d`
- Initial worktree: clean; remote is origin/main.
- Frozen source of truth: this local clone only.

## Runtime truth

SCAN_IMPLEMENTATION = src/garc/scan/policy.py (SafeCoveragePolicy / AnytimeLargestGap)
CANDIDATE_GENERATION = src/garc/controller/candidate.py; called by src/garc/controller/runner.py::_scan
FRONTIER_IMPLEMENTATION = src/garc/controller/frontier.py; wired by src/garc/controller/runner.py
FIXED_RATIO_CONTROLLER = src/garc/controller/fixed_ratio.py
CONFIRM_ADAPTER = src/garc/confirm/adapter.py
VLM_BACKEND = NOT_PRESENT; ConfirmAdapter accepts replay Mapping or injected callable; no VLM backend/import
MATERIALIZATION = src/garc/confirm/materialize.py
DEDUPLICATION = src/garc/controller/candidate.py, src/garc/controller/frontier.py, src/garc/controller/runner.py and src/garc/confirm/materialize.py
DURABLE_COMMIT = src/garc/confirm/commit.py; called by src/garc/controller/runner.py
END_TO_END_RUNNER = src/garc/controller/runner.py; CLI scripts/run_fixed_ratio_controller.py
FULL_PIPELINE_SUPPORT = PRESENT_FOR_REPLAY_DRY_RUN; REAL_YOLO/VLM_CHAIN_BLOCKED_MISSING_MODEL_ID_AND_BACKEND

## Model identity audit

`rg` over README, CURATION_REPORT, pyproject, requirements, configs, scripts, src, tests, docs, and provenance found no concrete YOLO checkpoint ID/path and no VLM model ID/path. Historical words “YOLO” and “VLM” occur only in closed research/history or generic audit text. Therefore no checkpoint was selected or downloaded.

## Dependency/import audit

- Declared runtime: `PyYAML>=6`; test extra: `pytest>=7`; no lock file.
- Runtime import graph is dependency-free Python plus PyYAML in the CLI. No `ultralytics`, `transformers`, `vllm`, OpenCV, or qwen-vl-utils import.
- Existing replay chain contains no Oracle client and deliberately consumes caller-supplied frozen outcomes.
