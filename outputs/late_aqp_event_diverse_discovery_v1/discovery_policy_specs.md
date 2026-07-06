# Discovery Policy Specifications — Upstream Event-Diverse Discovery Redesign

This document defines the discovery policies evaluated in this experiment. All policies reuse the existing Core/Halo release implementation and (except D3-norepair-core) the existing LATE audit/repair implementation. No policy uses `event_id` or ground-truth event intervals for runtime selection.

---

## Common setup

- **Atomic unit**: 10 s bin.
- **Segment list**: `realcartest_0_1570`, `realcartest_2000_3200`, `realcartest_3200_3830`, `dataset3_0_1200`, `dataset3_1200_2400`, `dataset3_2400_3462`.
- **Budget grid**: `sorted(unique(round(N * ratio_grid) + absolute_grid clipped to [1,N]))` where
  - `ratio_grid = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00]`
  - `absolute_grid = [5, 10, 20, 40, 60, 80, 100, 120]`
- **Seeds**: 5 trials per `(segment, method, budget)` using `np.random.default_rng(RANDOM_SEED_BASE + seed_offset)` with `RANDOM_SEED_BASE=20260705` and `seed_offset in {0,1,2,3,4}`.
- **Core/Halo release**: reused from `outputs/late_aqp_core_halo_attribution_v1/run_attribution_analysis.py` (`perform_guards`, `compute_guard_need`, `MAX_GUARDS_PER_SIDE=3`).
- **LATE audit/repair**: reused from `run_late_aqp_core_halo(...)` in the same file.
- **Deduplication/merging**: reused `merge_bins(...)` from `outputs/late_aqp_frozen_cross_segment_v1/run_frozen_cross_segment.py`.

---

## D0: current LATE discovery (control)

- **Full method name**: `LATE-D0-core`
- **Discovery logic**: directly call `run_late_aqp_core_halo(...)` from the existing codebase.
- **Repair**: enabled (existing audit-triggered local envelope repair).
- **Core/Halo**: enabled.
- **Why included**: baseline to measure whether D1/D2/D3 improve upon the current LATE-AQP discovery ledger.

---

## D1: Temporal-NMS Prior Discovery

- **Full method names**: `LATE-D1-core-radius10`, `LATE-D1-core-radius20`, `LATE-D1-core-radius30`
- **Discovery logic**:
  1. Sort all unqueried candidate bins by `prior_score_max` descending.
  2. Iteratively pick the highest-score bin that is not within `radius` seconds of any already-selected bin.
  3. After picking bin at time `t`, suppress the temporal neighborhood `[t - radius, t + radius]` (in seconds).
  4. Suppression depends only on time distance and prior rank; it does **not** use oracle labels or `event_id`.
  5. If all remaining candidates are suppressed, fall back to the next unselected layer (i.e., continue picking the highest-priority unsuppressed bin; if none exist, the neighborhood is widened implicitly by returning to the globally highest remaining prior bin).
- **Radius candidates** (all reported): `10 s`, `20 s`, `30 s`.
- **Main configuration** (pre-registered): `radius = 20 s`.
- **Repair**: existing LATE repair enabled.
- **Core/Halo**: enabled.
- **Note**: D1 replaces only the prior-ranked discovery step inside the LATE pipeline; audit and repair remain unchanged.

---

## D2: Component-Level Prior Proposal Discovery

- **Full method names**: `LATE-D2-core-q{20,30,50}-s{mass,max}-r{highest,center}`
- **Discovery logic**:
  1. Normalize prior scores to `[0, 1]` per segment (min-max over `prior_score_max`).
  2. Build candidate components from all bins whose normalized prior score is above a fixed quantile threshold:
     - thresholds: top-20%, top-30%, top-50% (all reported).
  3. Merge candidate bins into components if they are temporally contiguous or separated by at most **1 bin** (i.e., gap <= 10 s).
  4. For each component compute:
     - `max_prior`: maximum prior score among member bins.
     - `mean_prior`: mean prior score among member bins.
     - `duration`: total temporal span of the component.
     - `prior_mass`: sum of prior scores over member bins.
  5. Component ranking score:
     - `score = prior_mass` (reported as `score_mass`).
     - `score = max_prior` (reported as `score_max`).
  6. Representative bin sampling:
     - `highest`: the highest-prior bin in the component.
     - `center`: the geometric center bin of the component.
  7. Sampling rule: every component must be sampled at least once before any component is sampled twice. Components are visited in rank order; the first sample from each component is its representative bin. After all components have one sample, additional samples are taken from the same ranked components (next-best representative) if budget remains.
- **Quantile candidates** (all reported): `20%`, `30%`, `50%`.
- **Score candidates** (all reported): `prior_mass`, `max_prior`.
- **Representative candidates** (all reported): `highest`, `center`.
- **Main configuration** (pre-registered): quantile=30%, score=prior_mass, representative=highest.
- **Repair**: existing LATE repair enabled.
- **Core/Halo**: enabled.

---

## D3: Chunk-Bandit LATE Discovery

- **Full method names**: `LATE-D3-core-chunk{30,60,120}`
- **Discovery logic**:
  1. Divide the time axis into non-overlapping chunks of size `chunk_size` seconds.
  2. Each chunk `c` maintains:
     - `n_c`: number of sampled calls in the chunk.
     - `N1_c`: number of singleton-positive seed calls in the chunk (bins sampled exactly once and labeled positive).
  3. Thompson sampling: draw `theta_c ~ Gamma(N1_c + 0.1, n_c + 1)` for every chunk.
  4. Select the chunk with largest `theta_c`; within that chunk pick an unqueried bin uniformly at random.
  5. Update `n_c` and `N1_c` after observing the oracle label.
  6. If a chunk is fully sampled, set its `theta_c = -inf`.
  7. Discovery never switches back to prior-ranked selection and never uses `event_id`.
- **Chunk size candidates** (all reported): `30 s`, `60 s`, `120 s`.
- **Main configuration** (pre-registered): `chunk_size = 60 s`.
- **Repair**: existing LATE repair enabled.
- **Core/Halo**: enabled.

### D3-norepair-core

- **Full method names**: `D3-norepair-core-chunk{30,60,120}`
- **Discovery logic**: identical to D3 (chunk-bandit Thompson sampling).
- **Repair**: **disabled**. After chunk-bandit discovery returns its selected bins, candidate intervals go directly to Core/Halo release without triggering audit-triggered local envelope repair.
- **Core/Halo**: enabled.
- **Purpose**: isolate the marginal value of repair on top of a strong chunk-bandit discovery backbone.

---

## Baselines

- **B6-core**: existing `run_b6(...)` + Core/Halo release.
- **B7-core**: existing `run_b7(...)` + Core/Halo release.
- Both are `posthoc_eval` because their upstream selection uses `event_id` for per-chunk singleton counting.

---

## Method naming summary

| Method | Discovery | Repair | Release | Strict/Posthoc |
|--------|-----------|--------|---------|----------------|
| B6-core | B6 chunk-bandit | No | Core/Halo | posthoc_eval |
| B7-core | B7 chunk-bandit + expansion | No | Core/Halo | posthoc_eval |
| LATE-D0-core | current LATE prior-ranked | Yes | Core/Halo | strict_replay |
| LATE-D1-core-* | Temporal-NMS prior | Yes | Core/Halo | strict_replay |
| LATE-D2-core-* | Component proposals | Yes | Core/Halo | strict_replay |
| LATE-D3-core-* | Chunk-bandit | Yes | Core/Halo | strict_replay |
| D3-norepair-core-* | Chunk-bandit | **No** | Core/Halo | strict_replay |

*All `LATE-*` methods keep the existing LATE audit phase; only discovery (and optionally repair) is varied. Audit calls are still counted inside the total budget.*
