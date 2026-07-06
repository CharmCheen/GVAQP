# Final Recommendation

**Primary conclusion: B. Core/Halo is a generic post-processing gain; LATE advantage is weaker**

## Evidence

- B6-core/B7-core reach 90/90 on the same segments as LATE-AQP-core: True.
- Hardest segment miss reasons: {'upstream_discovery_miss': 4}.
- 1-bin halo reaches 90/90 on hardest segment: False.
- Mean guard overhead: 29.6%.

## Secondary notes

The main benefit observed in the frontier experiment comes from applying Core/Halo release, not from LATE-AQP's discovery strategy. Future effort should either (1) improve upstream discovery so that LATE-AQP-candidate itself is richer than B6/B7, or (2) adopt Core/Halo as a generic post-processing stage across all methods.
Additionally, the hardest segment's remaining recall gap is driven by upstream discovery misses: several events are never selected by LATE-AQP's discovery/repair, so release policy alone cannot close the gap.
