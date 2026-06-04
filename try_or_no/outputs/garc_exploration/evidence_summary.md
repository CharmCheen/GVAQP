# Evidence Summary for G-ARC

## 1. What evidence supports frame-level AQP not transferring to clip-level quality?

**Strongest evidence (synthetic, audit-validated):**

The audit-confirmed synthetic experiments show that clip-level degradation is **5-20x larger** than frame-level degradation across 240 parameter combinations (4 tau x 4 budget x 3 K x 5 seeds). Specifically:

- **proxy_threshold method:** Clip recall drop is 19.5x larger than frame recall drop, in 100% of cases (48/48 combinations)
- **arc_clustering method:** Clip recall drop is 11.7x larger than frame recall drop, in 100% of cases
- **uniform_random method:** Clip recall drop is 7.2x larger than frame recall drop, in 69% of cases

This is the core motivation: even when frame-level recall is 95%+, clip-level recall can drop to 30-60% because boundary errors cause IoU to fall below threshold.

**Supporting mechanism:** The perturbation ablation shows that proxy noise (which causes frame-level label errors at clip boundaries) is the dominant failure source, causing 20-27x amplification from frame to clip level.

## 2. Which evidence is synthetic only?

The following experiments use synthetic data exclusively:
- smoke_test (synthetic videos with synthetic perturbation)
- audit (agent_a through agent_e, all synthetic)
- factorial_ablation (synthetic videos)
- hard_synthetic (synthetic videos with 5 perturbation regimes)

**Limitation:** The synthetic perturbation model may not represent real-world proxy noise patterns. The synthetic clips have simple structure (~1 long clip per video), which may not generalize to real videos with multiple short clips.

## 3. Which evidence uses real continuous video?

- **real_mvp_uadetrac:** UA-DETRAC 60 sequences, 83K frames, real bounding box annotations. Shows frame-to-clip gap on real continuous video. **But:** fixed camera, no ego motion, independent sequences.
- **real_kinematic_uadetrac:** UA-DETRAC 2D, real annotations. Shows boundary-aware advantage (0.103 F1). **But:** 2D only, small advantage, parameter-sensitive.
- **nuscenes_feasibility / nuscenes_audit:** nuScenes mini, real 3D geometry. Shows baselines degrade meaningfully (fixed_rate_k10: 0.81-0.88 ClipF1). **But:** Only smoke baselines, no guarantee method tested yet.

## 4. Which evidence is strong enough for motivation?

**For paper motivation (Figure 1 / Introduction):**
- The 5-20x clip-vs-frame degradation (audit_agent_c) is strong enough. It is audit-validated, stable across parameters, and clearly demonstrates the problem.
- The nuScenes baseline degradation (fixed_rate_k10: 0.81-0.88 ClipF1 at 12% oracle) is strong enough to show the task is non-trivial on real data.

**For technical contribution (method section):**
- The factorial ablation (propagation dominates allocation) guides algorithm design.
- The hard_synthetic results (NN fails on regime_shift, mixed_hard) show where simple methods break down.

**For evaluation (experiments section):**
- Need real-data guarantee violation rates. Currently not available. This is the main gap.

## 5. Which evidence should NOT be used as main paper evidence?

1. **BDD100K results:** Synthetic proxy over real labels, K=3 too easy (94.86% positive). Can be mentioned as supplementary but not main evidence.

2. **Single-perturbation synthetic results:** The smoke_test and audit show that proxy_noise dominates. This is useful for understanding but may not generalize. Should not claim that proxy_noise is the only real-world failure mode.

3. **UA-DETRAC 2D results for moving-camera claims:** UA-DETRAC is fixed-camera. The 2D results (boundary_only advantage) cannot validate moving-camera geometry-aware claims.

4. **Nearest-neighbor near-perfect results on easy synthetic:** The factorial ablation shows NN achieves 0.996 clip recall on easy synthetic data. This makes the problem look trivially easy. Should not present this as the main result — instead, use the hard_synthetic results where NN fails.

## Summary Table

| Evidence | Dataset | Credibility | Use in Paper |
|----------|---------|-------------|--------------|
| 5-20x clip degradation | Synthetic (audit) | High | **Motivation** (Figure 1) |
| Proxy noise dominance | Synthetic (audit) | High | Technical insight |
| NN fails on hard regimes | Synthetic | High | Motivation for robust methods |
| Frame-to-clip gap (real) | UA-DETRAC | Medium | Supporting evidence |
| Baselines degrade (real 3D) | nuScenes | High | **Non-triviality** (Table) |
| Guarantee violation rates | **NOT YET** | — | **Must be produced** |

## Critical Gap

**No real-data guarantee violation rate exists yet.** The strongest version of the paper needs:
- On nuScenes: run a G-ARC method, measure Pr[Clip-Recall < gamma] over multiple seeds
- Show that simple baselines (uniform, fixed-rate) violate the guarantee at realistic budget levels
- Show that G-ARC achieves the target violation rate delta
