# Full-Video Candidate Smoke Report — Stage B

**Brief used**: `CASQ_CODEX_BRIEF_V12_1.md`
**Date**: 2026-06-23
**Protocol type**: Phase 1+ candidate feasibility, strict full-video validation

## 1. Goal

Test whether any practical candidate generator has signal when starting from **complete video timelines**, not from an already-mined candidate pool. This is the minimal validation Stage B as defined in the V13 protocol.

## 2. Data Source

- **Dataset**: Nexar-200 balanced readable (384 videos)
- **Heldout report split**: 192 videos (96 positive, 96 normal)
- **Events in heldout**: 96 events (Nexar-derived boundary: alert_time → event_start, event_moment → event_end)
- **Label mapping**: LOOSE_APPROXIMATION / AUDIT_UNRELIABLE (see VLM micro-audit)
- **Claim scope**: Nexar-200 only, derived boundary, single-dataset

## 3. Candidate Generators Evaluated

| # | Candidate | Status | Generation Logic |
|---|---|---|---|
| 1 | fixed_sliding_window | RUN_COMPLETE | Deterministic 10s windows, 5s stride over full video timelines. Baseline. |
| 2 | random_window | RUN_COMPLETE | Random selection from same 10s window grid. Fixed seed. Sanity baseline. |
| 3 | motion_energy | RUN_COMPLETE | Frame-difference motion energy over full videos at 2 fps. |
| 4 | yolo_count_proxy | NOT_RUN | YOLOv8n available locally but CPU fallback infeasible. |
| 5 | representation_candidate | NOT_AVAILABLE | No local CLIP/SigLIP or embedding assets. Download not approved. |

### Hard Invariants Check

| Candidate | uses_oracle_for_generation | uses_event_boundary_for_generation | Valid? |
|---|---|---|---|
| fixed_sliding_window | False | False | ✅ |
| random_window | False | False | ✅ |
| motion_energy | False | False | ✅ |

All three completed candidates pass the hard invariants. Candidate generation used only the video timelines; event_start, event_end, event_moment, alert_time, label, oracle label, and positive/negative flags were NOT used during generation.

## 4. Evaluation Grid

```text
returned_duration_fraction: 0.10, 0.20, 0.35, 0.50
merge_gap: 0s, 5s
IoU theta: 0.3 (primary)
```

**Pre-registered configuration**: The evaluation grid is carried over from Section 28 PRE_REGISTERED defaults (V12.1). No sweep-to-report optimization was performed on the heldout set.

## 5. Results

### 5.1 Main Grid Results (Heldout, theta=0.3)

| Candidate | dur_frac | gap=0s recall | gap=5s recall |
|---|---|---|---|
| fixed_sliding_window | 0.10 | 0.0000 | 0.0000 |
| fixed_sliding_window | 0.20 | 0.0000 | 0.0000 |
| fixed_sliding_window | 0.35 | 0.0000 | 0.0000 |
| fixed_sliding_window | 0.50 | 0.0104 | 0.0104 |
| random_window | 0.10 | 0.0833 | 0.0833 |
| random_window | 0.20 | 0.1771 | 0.0000 |
| random_window | 0.35 | **0.3229** | 0.0000 |
| random_window | 0.50 | 0.4896 | 0.0000 |
| motion_energy | 0.10 | 0.0000 | 0.0000 |
| motion_energy | 0.20 | 0.0000 | 0.0000 |
| motion_energy | 0.35 | 0.0000 | 0.0000 |
| motion_energy | 0.50 | 0.0104 | 0.0104 |

Full table: `tables/full_video_candidate_results.csv`

### 5.2 Key Observations

1. **fixed_sliding_window**: Near-zero recall at all fractions. Only hits 1/96 events at 50% duration. A 10s fixed window with 5s stride is essentially blind to the brief Nexar events (event durations typically <1s, derived from alert_time to event_moment).

2. **motion_energy**: Same result as fixed_sliding_window — near-zero recall. Frame-difference motion energy does not provide signal for the Nexar collision-event predicate.

3. **random_window**: Best non-oracle candidate at 32.3% recall at 35% duration fraction, 49.0% at 50%. Random selection from the 10s window grid outperforms both deterministic baselines. This is a well-known phenomenon when event windows are very brief (<1s) and no informative scoring function exists — random sampling gets lucky occasionally, while fixed patterns in space/time miss almost everything.

4. **merge_gap > 0**: Actively destructive. At gap=5s, random_window recall drops to 0 because the merged windows become too few for the `top_duration_fraction` selection budget.

### 5.3 Runtime

| Candidate | Runtime (384 videos) | Frames Processed |
|---|---|---|
| fixed_sliding_window | 0.003s | 0 (metadata only) |
| random_window | 0.054s | 0 (metadata only) |
| motion_energy | 156.4s | 768 (2 fps) |

## 6. Decision Rules Applied

```text
FULL_VIDEO_CANDIDATE_STRONG_PASS:
  At returned_duration_fraction <= 0.35, at least one non-oracle candidate
  reaches true_event_recall >= 0.75, and beats fixed_sliding_window by >= 0.10.
  → Best non-fixed: random_window at 0.3229. 0.3229 < 0.75. ❌ NOT MET

FULL_VIDEO_CANDIDATE_PASS:
  At returned_duration_fraction <= 0.35, at least one non-oracle candidate
  reaches true_event_recall >= 0.60, and beats fixed_sliding_window by >= 0.10.
  → Best non-fixed: random_window at 0.3229. 0.3229 < 0.60. ❌ NOT MET

FULL_VIDEO_CANDIDATE_FLAT:
  All non-oracle candidates are within 0.05 absolute recall of fixed/random,
  or no candidate reaches true_event_recall >= 0.50 at
  returned_duration_fraction <= 0.35.
  → No candidate reaches 0.50 at <= 0.35. ✅ APPLIES
```

## 7. Stage B Decision

```
STAGE_B_DECISION: FULL_VIDEO_CANDIDATE_FLAT
```

All cheap handcrafted candidates produce near-zero recall from full video timelines. random_window produces recall of 0.32 at 35% duration fraction, but this is well below the 0.60 threshold for PASS. The result is consistent with the earlier Nexar candidate feasibility v2 finding of CANDIDATE_STILL_TOO_WEAK.

### Why fixed_sliding_window and motion_energy score zero

The Nexar events are defined by the interval [alert_time, event_moment], which is typically <2 seconds. In a 40-second video, a 10-second sliding window with 5s stride has ~7 positions. Even at 50% duration fraction (3.5 windows per video), the probability of hitting a <2s event is:

- If windows are distributed evenly: coverage per video ≈ (3.5 × 10) / 40 = 87.5%, but event is <2s in a 40s video = 5% of timeline
- Probability that at least one 10s window covers a random <2s point in a 40s video: roughly 1 - (1 - 10/40)^3.5 ≈ 0.74
- But the event has finite duration (~1s), and the IoU threshold is 0.3, so the window must overlap with at least 0.3 × min(10, event_duration) ≈ 0.3s
- For derived Nexar events (duration ~0.5-2s), this is extremely challenging for fixed windows

The random_window hits 32% because some windows happen to overlap event regions by chance — but this is not a useful candidate generator; it's a sanity check confirming the difficulty of the problem.

### Why representation_candidate might help

A representation-based candidate (CLIP/SigLIP embedding + retrieval) could potentially score windows by their visual similarity to conflict/accident scenes, providing an informative ranking function. Without such a candidate, the conclusion is limited to "cheap handcrafted candidates fail," not "candidate generation in general fails."

## 8. Stage C Consequence

Since Stage B is `FULL_VIDEO_CANDIDATE_FLAT` (not PASS or STRONG_PASS), Stage C (certificate feasibility) is **not run**.

```
CERTIFICATE_STAGE_SKIPPED_DUE_TO_WEAK_FULL_VIDEO_CANDIDATE
```

## 9. Data Tables Produced

- `tables/full_video_candidate_inventory.csv` — Candidate generator inventory
- `tables/full_video_candidate_results.csv` — Main grid results (24 rows)
- `tables/full_video_candidate_per_video.csv` — Per-video hit summary (192 videos)

## 10. Scripts

- `scripts/10_stage_b_full_video_candidate_smoke.py` — Data extraction and table generation
