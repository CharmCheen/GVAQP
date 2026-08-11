# Git Research Snapshot Report

Repository: `/qiuyeqing/llama_prl/G-ARC`  
Branch: `dspro`  
Pre-commit HEAD: `e5ccf149d63320909afdb1c7ce31c6fa6f6bc929`  
Date: `2026-07-27`

## Frozen research scope

- Code: `src/garc_eval/partial_scan_v2`, `scan_scheduler`, `scan_headroom`, `scan_confirm_controller`; related `scripts`, `tests`, and `configs`.
- Contracts and documentation: partial-SCAN, SafeCoveragePolicy, YOLO-guided scheduling, macro-region proxy, multi-fidelity preview, SCAN-CONFIRM, common utility, and selected-Frontier input calibration.
- Results: the thirteen explicitly audited output stages plus `benchmarks/partial_scan_pilot_v1`.
- Provenance: hash-bound `*.source.json` and `*.source_attestation.md`; raw media remains excluded.

Included files: 14356  
Included bytes: 159101945  
Excluded files: 21718  
Excluded bytes: 139207748707

## Large files and sensitive material

Git LFS is not installed/configured. Every file over 50 MiB is excluded from this commit and recorded with SHA-256 in `LARGE_FILE_AUDIT.csv`. Raw media, extracted images, model weights, generated arrays/caches, archives, and temporary files are excluded. Secret scan status: `PASS`; reports contain locations and types only, never values.

## Verification

Test summary status: `PASS`. Detailed counts and skipped checks are recorded in `TEST_RESULTS.json` and `CONSISTENCY_AUDIT.json`. No Oracle, VLM, GPU research run, or new method experiment is part of this snapshot task.

The inventory uses `SELF_GENERATED_NOT_SELF_HASHED` for every file under `outputs/git_research_snapshot/`; these builder outputs are deliberately not assigned stale hashes from a prior generation. Artifact entries reported as unsupported use a manifest schema not supported by the generic verifier and are not counted as verified.

## Frozen conclusions and limitations

```text
SELECTED_SCAN_POLICY = SAFE_COVERAGE_POLICY
DEFAULT_SCAN_MODE = ANYTIME_LARGEST_GAP
SELECTED_CONTROLLER = R4_FIXED_TIME_RATIO_25_75

YOLO_GUIDED_REGION_SCHEDULING = CLOSED
MYOPIC_VPS_SIGNAL = NOT_ESTABLISHED
COMMON_UTILITY_ALIGNMENT_V1 = NOT_ESTABLISHED
REGION_VALUE_PROXY_SIGNAL = NOT_ESTABLISHED
MULTI_FIDELITY_PREVIEW_SIGNAL = NOT_ESTABLISHED
RATIO_ANCHORED_CONTROLLER = BLOCKED
BANDIT = DEFERRED
SMDP = DEFERRED
RL = PROHIBITED

FORMAL_GENERALIZATION = NOT_ESTABLISHED
ADAPTIVE_CONTROL = NOT_ESTABLISHED
SELECTED_FRONTIER_CALIBRATION = BLOCKED_INPUT_INSUFFICIENT
```

This commit is a local auditable snapshot, not a new scientific evaluation.
