# Minimal Experimental Validation Plan for G-ARC (2 Weeks)

## Overview

Validate that clip-level guarantees are non-trivially achievable and that simple baselines violate them under realistic conditions.

---

## Week 1: Synthetic Validation + Guarantee Prototype

### Day 1-2: Guarantee Definition and Simple Algorithm

**Goal:** Formalize the simplest possible G-ARC guarantee and implement a prototype.

**Algorithm (Conservative Clip Retrieval):**
1. Run SUPG-style frame-level importance sampling with budget B
2. Construct clips from oracle-labeled frames using nearest-neighbor reconstruction
3. Estimate clip-level recall lower bound using Hoeffding-style bound on clip hits
4. Return clips only if the lower bound >= gamma

**Dataset:** Existing synthetic infrastructure (smoke, factorial)
- 100 videos, K=3, tau=30, budget=0.1
- 5 seeds

**Metrics:**
- Clip recall, clip precision, mIoU
- Guarantee violation rate: fraction of runs where clip recall < gamma
- Oracle calls

**Baselines:**
- full_oracle (upper bound)
- uniform_random (10% budget)
- fixed_rate (10% budget)
- proxy_threshold (10% budget)
- SUPG frame-level selection + clip construction (naive clip extension)

**Success criteria:**
- Guarantee violation rate <= delta for G-ARC method
- Simple baselines (uniform, fixed-rate) have violation rate > delta at same budget
- G-ARC returns fewer clips than "return everything" baseline

**Kill criteria:**
- All baselines achieve violation rate = 0 at 10% budget (guarantee is trivially satisfied)
- G-ARC cannot achieve violation rate <= delta at any reasonable budget

### Day 3-4: Ablation on Synthetic Data

**Goal:** Understand which components of the guarantee algorithm matter.

**Experiments:**
- Vary gamma (0.7, 0.8, 0.9, 0.95)
- Vary delta (0.01, 0.05, 0.1)
- Vary tau (10, 20, 30, 60)
- Vary budget (0.05, 0.1, 0.2, 0.4)
- Compare: Hoeffding bound vs bootstrap CI vs conformal prediction

**Metrics:** Same as above, plus:
- Bound tightness: how close is the estimated lower bound to true recall?
- Oracle efficiency: oracle calls per unit of recall guarantee

### Day 5: Hard Synthetic Validation

**Goal:** Test on hard_synthetic regimes where NN fails.

**Dataset:** hard_synthetic (regime_shift, mixed_hard)

**Question:** Does the guarantee hold on hard cases? Is the bound still valid?

---

## Week 2: Real-Data Validation

### Day 6-7: nuScenes Mini Validation

**Goal:** Validate on real 3D driving video data.

**Dataset:** nuScenes mini (already available)
- Query table: `outputs/nuscenes_mini_feasibility/real_3d_query_table.csv` (18,538 rows)
- Ground truth clips: `outputs/nuscenes_mini_feasibility/ground_truth_clips.jsonl` (4,507 clips)
- Queries: in_fov, within_30m, ego_front
- tau: 2, 3, 5 (nuScenes keyframes are sparse, ~2 Hz)
- Budget: 10%, 20%, 30%, 50% of frames

**Baselines:**
- naive_oracle (upper bound, already = 1.0)
- fixed_rate_k2, k5, k10 (already computed)
- linear_interp (already computed)
- const_vel_k5 (already computed)
- **NEW:** SUPG frame-level selection + clip construction
- **NEW:** G-ARC conservative clip retrieval

**Metrics:**
- Clip recall, clip precision, mIoU
- Guarantee violation rate (over 5 seeds)
- Boundary error
- Oracle calls

**Success criteria:**
- G-ARC achieves violation rate <= delta (e.g., 5%)
- Simple baselines have violation rate > delta at same budget
- G-ARC is more oracle-efficient than "sample everything near boundaries"

**Kill criteria:**
- All baselines achieve violation rate = 0 at 20% budget (task is too easy)
- G-ARC cannot achieve violation rate <= delta at 50% budget (task is too hard)

### Day 8-9: UA-DETRAC Validation

**Goal:** Validate on real continuous video with higher frame rate.

**Dataset:** UA-DETRAC (already available)
- 60 sequences, 83K frames
- Queries: in_image, in_front, count_ge_K
- tau: 5, 10, 20, 30
- Budget: 5%, 10%, 20%

**Baselines:** Same as nuScenes

**Metrics:** Same as nuScenes

**Note:** UA-DETRAC is fixed-camera, so this validates temporal clip guarantees but not ego-relative geometry.

### Day 10: Analysis and Write-up

**Goal:** Compile results, identify key findings, draft paper outline.

**Tasks:**
1. Create budget-quality curves (clip recall vs oracle budget) for all methods
2. Create guarantee violation rate plots (violation rate vs budget) for G-ARC vs baselines
3. Identify the "zone" where G-ARC provides value (budget range where baselines violate but G-ARC doesn't)
4. Draft paper outline with key figures and tables

---

## Summary

| Phase | Dataset | Query | tau | Budget | Days |
|-------|---------|-------|-----|--------|------|
| Synthetic validation | Synthetic (smoke) | count_vehicle_K | 30 | 10% | 1-2 |
| Synthetic ablation | Synthetic (smoke) | count_vehicle_K | 10-60 | 5-40% | 3-4 |
| Hard synthetic | Synthetic (hard) | count_vehicle_K | 10-60 | 5-20% | 5 |
| Real 3D validation | nuScenes mini | in_fov/within_30m/ego_front | 2-5 | 10-50% | 6-7 |
| Real continuous | UA-DETRAC | in_image/in_front/count_ge_K | 5-30 | 5-20% | 8-9 |
| Analysis | All | All | All | All | 10 |

## Required Baselines (All Phases)

1. **full_oracle** — Oracle at every frame (upper bound)
2. **uniform_random** — Uniform random frame sampling
3. **fixed_rate_k** — Oracle every k frames (k=2,3,5,10)
4. **SUPG frame-level** — SUPG importance sampling + threshold selection, applied to frames, then clips constructed from selected frames
5. **proxy_threshold** — Top-B frames by proxy score, construct clips
6. **nearest_neighbor_reconstruction** — Oracle at sampled frames, NN interpolation for others
7. **segment_window_sampling** — Sample temporal windows, oracle all frames in window
8. **ARC-style baseline** — Proxy pruning + time-domain clustering + MAB sampling (if feasible; otherwise skip)

## Required Metrics (All Phases)

- **Frame-level:** frame recall, frame precision
- **Clip-level:** clip recall, clip precision, mIoU
- **Boundary:** boundary error (start, end, max), mean boundary error
- **Structure:** fragmentation rate, merge error
- **Guarantee:** violation rate (Pr[clip recall < gamma] over seeds)
- **Cost:** oracle calls, oracle call ratio

## Kill Criteria (Overall)

1. If on nuScenes, all baselines achieve violation rate = 0 at 20% budget → problem is too easy for real data
2. If G-ARC cannot achieve violation rate <= delta at 50% budget on nuScenes → guarantee is too conservative
3. If the "zone of value" (budget range where G-ARC beats baselines) is < 5% of budget → contribution is marginal
4. If the guarantee requires assumptions that clearly don't hold in real data → theory is not applicable
