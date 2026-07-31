# G-ARC-Core curation report

```text
SOURCE_REPOSITORY = /qiuyeqing/llama_prl/G-ARC
SOURCE_COMMIT = 5047241b0561b911b9a519b18e8e7591c0074e70
TARGET_REPOSITORY = /qiuyeqing/llama_prl/G-ARC-Core

SOURCE_FILES_REVIEWED = 135846 (full frozen tree inventory; focused content audit on decision and dependency closure)
FILES_MIGRATED = 17 unique source artifacts represented by 17 curated target files
FILES_OMITTED = 135829 source files
FILES_REWRITTEN = 17 target files
FILES_COPIED_UNCHANGED = 0

CODE_FILES = 34
TEST_FILES = 14
DOCUMENT_FILES = 23
RESULT_FILES = 6

RESULT_TOTAL_SIZE = 3334 bytes
RAW_MEDIA_INCLUDED = false
MODEL_WEIGHTS_INCLUDED = false
FILES_OVER_50_MIB_INCLUDED = false
SECRET_SCAN = PASS

SAFE_COVERAGE_ACTION_PARITY = 100% (1013/1013 enumerated public states)
FIXED_RATIO_ACTION_PARITY = 100% (1296/1296 state/cost combinations)
FRONTIER_SELECTION_PARITY = 100%
DEADLINE_ADMISSION_PARITY = 100% (20/20 frozen valid-domain combinations)

PYTEST_PASSED = 34
PYTEST_FAILED = 0
PYTEST_SKIPPED = 0

CURRENT_SCAN_POLICY = SAFE_COVERAGE_POLICY / ANYTIME_LARGEST_GAP
CURRENT_CONTROLLER = R4_FIXED_TIME_RATIO_25_75
ACTIVE_RESEARCH_BLOCKER = BLOCKED_INSUFFICIENT_INDEPENDENT_VIDEOS (3 additional qualifying videos missing)

NEW_REPOSITORY_BRANCH = main
NEW_REPOSITORY_COMMIT = HEAD (the local initial commit; resolve with git rev-parse HEAD)
PUSH_PERFORMED = true (explicitly authorized by the user after the original curation request)
```

## Strongest supported conclusion

The frozen snapshot supports a small current system: deterministic public-state `AnytimeLargestGap` for SCAN and fixed realized-wall-clock 25:75 SCAN–CONFIRM allocation with a bounded frozen Frontier. It does not support reviving adaptive region-value or learned controller branches. This extraction reproduces the frozen decision semantics and removes the old runner's dataset-specific dependency graph.

The initial curation was not SCAN-only, but its completeness claim was too strong. The post-SCAN audit found and repaired missing frozen candidate-generation, explicit result/materialization failure, causal q90 fallback, transactional commit-order, and durable final-STOP semantics. Decisive evidence is now direct parity against literal frozen reference rules, the 34-test suite, the dependency/import audit, and the frozen final decision artifacts; see `POST_SCAN_CHAIN_AUDIT.md`. The main competing explanation is that replay event IDs can conceal failures in the physical Oracle/K3 path. Physical hard-deadline safety and cross-video generalization remain unestablished. A parity mismatch or a measured physical-adapter contradiction would trigger revision.

## Migrated core modules

- Coverage state, `AnytimeLargestGap`, and three explicitly evaluation-only baselines.
- Fixed R4 actual-time controller, complete-action admission, fallback, and STOP.
- Frontier admission, unit-level deduplication, retention, aging, deterministic selection, and terminalization.
- Replay CONFIRM adapter, public materialization, cost accounting, distinct utility, and atomic durable commit.
- Selected-Frontier candidate registration, probe/full decode, deterministic seek, source provenance, capture-session and pairwise overlap checks, and input Gate.
- Replay metrics, two benchmark CLIs, two runnable CLIs, artifact/leakage/release audits, examples, and focused tests.

## Major exclusions and replacements

| Excluded source branch/artifact | Reason | Replacement |
|---|---|---|
| YOLO-guided region schedulers | Failed static observability Gates | `garc.scan.SafeCoveragePolicy`; `docs/research-history/YOLO_REGION_SCHEDULING.md` |
| P0/P1/P2/P3 multi-fidelity search | Proxy Gate failed; P3 unauthorized | `docs/research-history/MULTI_FIDELITY_PREVIEW.md` |
| Myopic-VPS/posterior/offline allocator | Preregistered benefit Gate failed | R4 controller; `docs/research-history/MYOPIC_VPS.md` |
| Common-utility and Ratio-Anchored code | Static alignment failed; replay unauthorized | R4 controller; `docs/research-history/COMMON_UTILITY_ALIGNMENT.md` |
| Bandit/SMDP/RL drafts | Deferred or outside current system | Status only in `results/current_decisions.json` |
| Raw action/frame traces, predictions, Parquet, caches | Not needed to understand or verify current conclusions | `results/key_metrics.csv` and artifact manifest |
| Raw media and model weights | Excluded by scope and release policy | Caller-owned manifests; provenance documentation |
| Dataset-specific legacy replay runner | Hard-coded source outputs and large dependency closure | Portable `garc.controller.runner.ReplayControllerRunner` |

The prefix-level omission rationale and scientific preservation locations are exhaustive at the major subsystem/artifact-class level in `provenance/omitted_legacy_manifest.csv`.

## Potential future migrations

If the input Gate is later satisfied, the frozen calibration contract and additional minimal aggregate calibration tables may be migrated. A production physical adapter may also be added after its API, cost measurement, failure atomicity, and deadline behavior are validated. Neither change is currently authorized evidence for a new algorithm. Raw historical traces, old schedulers, and Oracle implementations should remain in the source archive unless a new dependency audit demonstrates necessity.

## Verification and reproduction

```bash
python -m compileall -q src scripts
pytest -q
PYTHONPATH=src python scripts/verify_release.py
PYTHONPATH=src python scripts/benchmark_scan_policy.py --video-manifest examples/example_video_manifest.json --max-actions 5
PYTHONPATH=src python scripts/benchmark_fixed_ratio_controller.py --video-manifest examples/example_video_manifest.json --budgets-sec 30 60 120 240 --output /tmp/fixed-ratio.json
```

Runnable dry/replay commands are in `README.md` and `docs/REPRODUCTION.md`. No command in the curation process invoked an Oracle. The final `main` branch was pushed only after explicit user authorization.
