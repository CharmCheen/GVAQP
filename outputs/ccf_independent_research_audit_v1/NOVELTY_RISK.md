# Novelty risk

Independent literature check (CCF Literature Searcher), focused on whether a
publishable gap remains after the closest prior work. Sources verified via
public primary pages.

## Closest-work clusters

### A. Database / AQP: proxy + expensive oracle under budget

- AQUAPRO (VLDB 2023): approximate oracle with cheaper proxy, precision-target
  and recall-target queries. This is the generic proxy+oracle budget formulation
  and directly covers the C-A/C-D "imperfect proxy creates optimization work"
  story.
- SUPG (VLDB 2020): adaptive label spending over a proxy-scored population.
- ThalamusDB (2024): prioritizes multimodal processing/labels under error and
  time objectives.

Novelty risk: HIGH for the proxy/oracle budget and ranking framing. The
"imperfect proxy under budget" question is already studied; the residual is
temporal-EventRelation materialization, which is separately weak.

### B. Adaptive video sampling / localization

- Seiden (VLDB 2023): query-agnostic oracle index plus exploration-exploitation
  sampling during query processing.
- ExSample (ICDE 2022): Thompson-style adaptive sampling of unindexed chunks.
- ARC (VLDB 2025): proxy clips plus progressive oracle refinement with
  bandit-style priority.
- DIVA (USENIX ATC 2021): cheap-to-expensive video passes with validation.
- MIRIS (SIGMOD 2020): query-specific sparse tracking/refinement.

Novelty risk: HIGH for any adaptive/bandit SCAN/VERIFY or progressive-sampling
claim. This is exactly why the controller/MAB direction is crowded.

### C. Bandit / RL action selection for video

- LAVA (ACM MM 2025): explicit multi-armed-bandit segment sampling for
  language-driven traffic-video localization. This is the closest direct
  collision for any MAB/controller claim on traffic video.
- Zeus (SIGMOD 2022), FiGO (SIGMOD 2022), Aero (SIGMOD 2025): learned/adaptive
  operator, fidelity, or predicate scheduling.

Novelty risk: VERY HIGH for learned/adaptive action selection.

### D. Event reconstruction / temporal grounding

- Moment retrieval and highlight detection (large CV/NLP literature); temporal
  localization/grounding with gap-based grouping is a standard component.

Novelty risk: HIGH for the C1 gap-constrained merge as a novel mechanism; it
is a known temporal-localization primitive.

## What is already studied vs what is not

Already studied (problem + method):
- cheap proxy + expensive oracle budget allocation (AQUAPRO, SUPG, ThalamusDB);
- adaptive video sampling under exploration-exploitation (Seiden, ExSample);
- proxy + progressive refinement (ARC);
- MAB segment sampling for traffic video (LAVA).

Not yet cleanly owned by prior work, but currently unsupported here:
- a single-physical-clock, causal-exposure, durable EventRelation contract
  (candidate creation, verification, and K3 dedup share one deadline);
- a measured demonstration that natural cheap-sensor exposure false negatives
  (not ranking) create non-rare, material, predictable action regret.

Both residual slots are systems/design in nature, and neither is currently
supported by independent evidence in this repository.

## Top novelty threats

1. LAVA (ACM MM 2025) for any MAB/bandit traffic-video sampling claim.
2. AQUAPRO / SUPG / ThalamusDB for the proxy+oracle budget and ranking claim.
3. Seiden / ExSample / ARC for adaptive progressive sampling/refinement.

## Novelty verdict

The general research area is crowded, and every headline-able mechanism
(bandit, adaptive sampling, proxy+oracle, gap-based materialization) is already
covered by a close paper. A paper-worthy gap exists only as a narrow
systems/design claim (the single-clock durable-EventRelation contract) and is
currently backed by single-source/single-event evidence and no independent
reference. Novelty is NOT established; it is contingent on a decisive result
that the existing evidence has not produced.
