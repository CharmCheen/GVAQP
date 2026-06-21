# ARC Moving-Camera Exploration Brief

## Goal

I want to explore whether ARC-style relevant clip query processing has a real limitation under moving-camera / dynamic-view videos.

Do not propose a final paper title yet.  
Do not write a paper.  
Do not modify code first.

The goal is to understand:
1. ARC source code structure.
2. ARC's assumptions.
3. Where moving-camera videos may break ARC.
4. Whether query-agnostic preprocessing + limited oracle calibration can replace fixed proxy-based pruning.
5. What minimal experiments should be run next.

## Current Research Direction

The broad direction is dynamic-view / moving-camera video query processing with expensive visual predicates.

The key question is not recall guarantee first.  
The key question is whether we can design a better query processing method than fixed frame-level proxy pruning.

## Hypothesis to Investigate

ARC uses a fixed proxy probability map, temporal clustering, oracle refinement, adaptive sampling, and label propagation.

In moving-camera videos, proxy score maps and temporal clustering may become unreliable because of:
- camera motion;
- object entering and leaving the field of view;
- scale changes;
- occlusion;
- short-term false negatives;
- track fragmentation;
- unstable clip boundaries.

A possible alternative direction is:
- build a query-agnostic temporal synopsis during preprocessing;
- use limited oracle calls at query time to calibrate relevance;
- perform active search / active refinement on the synopsis;
- assemble candidate clips and refine boundaries.

## Expected Analysis Output

Please produce:
1. ARC codebase map.
2. Main execution entry points.
3. Data input format and expected outputs.
4. Where proxy pruning is implemented.
5. Where candidate clip generation is implemented.
6. Where temporal clustering is implemented.
7. Where oracle refinement / sampling is implemented.
8. Where label propagation is implemented.
9. Where evaluation metrics are computed.
10. Minimal steps to run ARC on a small sample.
11. Minimal moving-camera stress test plan.
12. Go / no-go criteria for this research direction.

Important:
- Do not change code yet.
- If code paths are uncertain, state uncertainty.
- Prioritize executable next steps.
