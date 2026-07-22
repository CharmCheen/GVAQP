# PSTR external confirmation v5

This protocol supersedes v4 before any new external video is acquired. It incorporates the independent review and the omitted dataset3 public-proxy evidence.

Five opened domains now form the retrospective evidence set. PSTR-5:4 beats the controlled shared-K3 ARC mean in four leave-one-domain-out folds and ties in the sparse fold. On dataset3, fixed PSTR scores `0.380363` versus public-proxy top-k `0.354212` and controlled shared-K3 ARC `0.250568`, but it remains below CLIP `0.538949`, NMS `0.562378`, DASR `0.568778`, and descriptive native ARC `0.389659`. PSTR is therefore the most consistent controlled-ARC/proxy candidate on opened domains, not the unqualified strongest method.

The external test requires at least five independent videos with at least 100 full ten-second units each. The RoadCLIP `score_count` extractor, model, configuration, temporal aggregation, missing-value rule, unit grid, PSTR selection script, K3 evaluator, ARC seeds, aggregation, uncertainty calculation, and strong-baseline pass roles are all fixed in `config/frozen_external_confirmation_v5.json`.

Selections must be produced by the proxy-only label-blind sealer before labels or references are opened. Primary references must be human adjudicated. Each method receives budget `B` independently on each video; the primary statistic is the unweighted mean of per-video normalized event-F1 AUC. PSTR must exceed the strongest complete baseline family and have a positive paired-video bootstrap lower bound. Missing SUPG, DPP, or any other named comparator makes the gate incomplete rather than a pass.

No external acquisition, VLM oracle generation, or human annotation is performed by this package. Those actions require explicit budget authorization.
