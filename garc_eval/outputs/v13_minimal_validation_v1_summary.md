# V13 Minimal Validation — Compact Summary

**Brief**: CASQ_CODEX_BRIEF_V12_1.md
**Date**: 2026-06-23
**Full report**: `test_vlm/outputs/v13_minimal_validation_v1/reports/V13_MINIMAL_VALIDATION_REPORT.md`
**Tables**: `test_vlm/outputs/v13_minimal_validation_v1/tables/`

---

## Stage A: Artifact Inventory

- **Nexar-200**: 384 balanced readable videos, 200 derived-boundary events
- **Micro-CASQ v1**: 38 eligible 32B-oracle positives (sampled from candidate pools, NOT full-video)
- **Label provenance**: All labels are external-label-derived or 32B-oracle-relative. **Zero human-adjudicated event boundaries exist.**
- **External label audit**: UNRELIABLE (16% positive agreement with O_enter_ego_path_v0)
- **Prior V12.1 runs**: Nexar candidate v2 (V12.1), V12.1 completion v1 (V12.1). Earlier runs used V11.

See: `tables/artifact_inventory.csv`, `reports/ARTIFACT_AUDIT.md`

## Stage B: Full-Video Candidate Smoke

**Heldout**: 192 videos, 96 events. **All candidates generated from full video timelines (no oracle/label/boundary access).**

| Candidate | Recall at ≤0.35 frac | Recall at 0.50 frac |
|---|---|---|
| fixed_sliding_window | 0.00 | 0.01 |
| motion_energy | 0.00 | 0.01 |
| random_window | **0.32** | 0.49 |
| yolo_count_proxy | NOT_RUN | NOT_RUN |
| representation_candidate | NOT_AVAILABLE | NOT_AVAILABLE |

**Hard invariants**: All pass (no oracle/boundary leakage).

**Decision**: `FULL_VIDEO_CANDIDATE_FLAT` — No candidate reaches 0.50 recall at ≤35% returned duration.

See: `tables/full_video_candidate_results.csv`, `tables/full_video_candidate_per_video.csv`, `reports/FULL_VIDEO_CANDIDATE_SMOKE_REPORT.md`

## Stage C: Certificate Feasibility

```
CERTIFICATE_STAGE_SKIPPED_DUE_TO_WEAK_FULL_VIDEO_CANDIDATE
```

Not run. Stage B did not pass.

## Final Decision

```
FINAL_DECISION: FULL_VIDEO_CANDIDATE_FLAT_TRY_REPRESENTATION_CANDIDATE
```

**What this means**:
- Cheap handcrafted candidates (fixed windows, motion energy) produce near-zero recall from full videos on Nexar-200.
- Pipeline, mapping, and video access work correctly — the failure is in candidate generator quality.
- A representation-based candidate (CLIP/SigLIP) is the next step before any conclusion about full-video candidate feasibility.
- Certificate simulation is not justified until full-video candidate recall improves substantially.

## Key Caveats

1. Labels are LOOSE_APPROXIMATION / UNRELIABLE — not oracle-relative, not human truth
2. Single dataset (Nexar-200) — cannot generalize per Section 30
3. No human-adjudicated event boundaries exist anywhere in the project
4. REPRESENTATION_CANDIDATE_NOT_AVAILABLE — limits conclusion scope to cheap handcrafted only
5. Only 96 events in heldout — below power simulation thresholds for non-vacuous certificates
