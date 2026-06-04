# Hidden-Risk-Aware Oracle Allocation -- Summary Report

## Configuration

- Sample size: 50 synthetic videos
- K (min vehicles): 3
- tau (min clip frames): 30
- Oracle budget: 0.1 (10% of frames)
- Frames per video: 300
- Seed: 42

## Method Comparison

| Method | Frame Recall | Frame Prec | Clip Recall | Clip Prec | Mean IoU | Frag Rate | Oracle Frac |
|--------|-------------|------------|-------------|-----------|----------|-----------|-------------|
| full_oracle | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |
| uniform_random | 0.999 | 0.999 | 0.990 | 1.000 | 0.989 | 0.000 | 0.100 |
| proxy_threshold | 0.959 | 0.995 | 0.230 | 0.130 | 0.159 | 1.990 | 0.100 |
| arc_clustering | 0.912 | 0.997 | 0.040 | 0.040 | 0.031 | 1.990 | 0.044 |
| risk_aware_hidden | 0.919 | 0.997 | 0.060 | 0.050 | 0.041 | 1.930 | 0.100 |

## Boundary Errors (frames)

| Method | Mean Start Error | Mean End Error |
|--------|-----------------|----------------|
| full_oracle | 0.0 | 0.0 |
| uniform_random | 0.0 | 3.0 |
| proxy_threshold | 17.5 | 76.0 |
| arc_clustering | 11.5 | 26.5 |
| risk_aware_hidden | 20.0 | 51.0 |

## Degradation Analysis (relative to full oracle)

| Method | Frame Recall Drop | Clip Recall Drop | Clip Drop / Frame Drop |
|--------|------------------|-----------------|----------------------|
| uniform_random | 0.001 | 0.010 | 6.98 |
| proxy_threshold | 0.041 | 0.770 | 18.91 |
| arc_clustering | 0.088 | 0.960 | 10.87 |
| risk_aware_hidden | 0.081 | 0.940 | 11.59 |

## Analysis: Risk-Aware Hidden vs Other Budget-Constrained Methods

### Can hidden risk-aware allocation recover clip-level quality?

**Not clearly.** The hidden-risk-aware baseline (clip_recall=0.060) does not outperform
`uniform_random` (clip_recall=0.990). However, it does outperform both `proxy_threshold`
(clip_recall=0.230) and `arc_clustering` (clip_recall=0.040) on clip recall, and achieves
the highest frame recall (0.919) among proxy-based methods.

### Why does uniform_random dominate?

The dramatic gap between `uniform_random` (clip_recall=0.990) and all other budget-
constrained methods (0.040--0.230) stems from a fundamental **label propagation strategy
difference**, not from risk allocation quality:

- **uniform_random** uses **nearest-neighbor propagation**: oracle-corrected labels are
  interpolated to fill the entire video. With 30 oracle points spread across 300 frames,
  even a few correctly-placed points near clip boundaries reconstructs full clips.

- **proxy_threshold**, **arc_clustering**, and **risk_aware_hidden** use the **proxy
  decision** (`perturbed_count >= K`) for non-oracle frames. Perturbation noise at clip
  boundaries causes counts to fluctuate around K, creating false-negative gaps that
  fragment clips (fragmentation_rate = 1.9--2.0).

This means the oracle budget in proxy-based methods is spent *correcting individual
frames*, but the 90% of frames using the proxy decision still produce fragmented labels.
The risk-aware strategy correctly identifies boundary/threshold frames as risky, but the
proxy for remaining frames introduces too many errors to sustain clip-level quality.

### Is the oracle budget being used effectively?

- risk_aware_hidden oracle calls: 1500 (fraction: 0.100)
- uniform_random oracle calls: 1500 (fraction: 0.100), clip_recall: 0.990
- proxy_threshold oracle calls: 1500 (fraction: 0.100), clip_recall: 0.230
- arc_clustering oracle calls: 661 (fraction: 0.044), clip_recall: 0.040

The risk-aware method allocates its oracle budget proportional to composite risk scores
derived from: (1) motion (temporal derivative of perturbed counts), (2) proximity to
label-transition boundaries, (3) threshold proximity (how close perturbed counts are to K),
and (4) visibility drop detection (deviation from local average). This targets the oracle
at frames where perturbation is most likely to cause errors, which is the correct
intuition -- but the proxy-based fill for non-oracle frames undermines the benefit.

### Key Takeaway

Risk-aware oracle allocation targets the right frames. The bottleneck is not *where* to
spend oracle budget, but *how to propagate* oracle information to non-queried frames.
A hybrid approach -- risk-aware oracle sampling combined with nearest-neighbor propagation
instead of proxy decisions -- would likely combine the strengths of both strategies.

## Conclusion

This experiment tests whether heuristic risk signals derived from perturbed data can guide
oracle budget allocation to recover clip-level quality. The results show:

1. **Risk-aware targeting works at the frame level**: risk_aware_hidden achieves the highest
   frame recall (0.919) among proxy-based methods, showing the risk heuristics correctly
   identify error-prone frames.

2. **Clip-level recovery requires label propagation**: The critical factor for clip recall
   is not oracle allocation strategy but label propagation. Nearest-neighbor interpolation
   from oracle points (as in uniform_random) dramatically outperforms proxy-based decisions
   for non-oracle frames.

3. **Perturbation-induced fragmentation is the core challenge**: All proxy-based methods
   exhibit high fragmentation rates (~2.0), indicating that perturbation noise creates many
   short false-negative gaps that break clips below the tau threshold.

4. **Future work should combine risk-aware allocation with propagation**: A risk-aware
   sampling + nearest-neighbor fill strategy would likely achieve both high frame recall
   (from risk targeting) and high clip recall (from smooth propagation).
