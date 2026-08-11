# GVAQP Long-Horizon Evidence Convergence Report

## 1. Reference recovery

V9 did not produce a single-seal release because its frozen cost envelope stopped at 1454/1475 terminal units. The post-runtime-failure V10 multi-seal amendment did not alter source videos, unitization, VLM, processor, prompt, parser, or K3 reference configuration. Its outcome-blind 9-unit cross-seal shadow passed; Seal B completed the frozen 21-unit missing set. The formal reference is `1475/1475` in `outputs/v10_multiseal_reference_v1/REFERENCE_MANIFEST.json`.

## 2. P0 controlled matrix

`outputs/p0_materializer_validation_v3/` contains the first current-V3 controlled result: 3 independent source videos × 3 deterministic comparable selectors × 6 query budgets × K0/K3. All 54 pairs have identical candidate universe, queried IDs, order, semantic outcomes, oracle count, and matcher. K3 is better/equal/worse in `40/14/0`; mean/median ΔF1 are `+0.1840/+0.1457`, with mean bootstrap 95% CI `+0.1405,+0.2286`.

Per-video median ΔF1 is DALI `+0.1377`, HANGZHOU `+0.1441`, WUHAN `+0.1675`. Strict improvements are not universal at low budget or with TemporalCoverage, but no regression occurs. The primary result is query-budget replay, not physical wall-clock/hard-deadline evidence.

## 3. Mechanism attribution

The explanatory C0–C3 lineage ablation is decisive for interpretation. All-positive global span → 10-second gap-limited grouping supplies mean/median `+0.1738/+0.1377`; duration adds median `0`; queried-negative barriers add median `0`; current-K3 extras after C3 have mean `−0.00034` and median `0`. Thus the P0 mechanism is local temporal continuity, not negative-barrier semantics or a distinctive full-K3 gain.

## 4. Selector interaction

The median materializer absolute difference (`0.1457`) exceeds median pairwise selector difference at fixed K3 (`0.0982`), but the median three-selector spread (`0.1596`) exceeds it. StaticProxyRank is much stronger than TemporalCoverage. Existing evidence supports “materialization is a major downstream source of error in a defined sparse regime,” not “materialization dominates selection.”

## 5. Circularity and label boundary

All reference unit outcomes are Qwen model-relative. The reference EventRelation is constructed from full-grid outcomes using frozen current-V3 K3 grouping. Therefore P0 measures reconstruction of that K3-defined model-relative relation. It is legitimate as a conditional mechanism experiment and invalid as independent proof of human event-boundary or universal K3 superiority.

## 6. Historical and alternative directions

Historical Stage-0’s `0.3669 → 0.9756` one-video replay is retained as discovery evidence only. It anticipated global overmerge but does not validate current V3. MAB/controller evidence is negative: the repository direction freeze records zero immediate improvements across 18 probes, only one timing-only conversion among seven continuations, weak state predictability, and close adaptive-video prior art. Deadline-aware temporal bisection has one repeatable Guangzhou physical example but remains single-source/single-event exploratory evidence.

## 7. Scientific decision

`MATERIALIZATION_MAINLINE_DECISION = REVISE` for a broad K3/negative-barrier paper: the current controlled result is positive, but its actually supported mechanism is a simple gap constraint and the reference is circularity-qualified.

`PAPER_MAINLINE_DECISION = WEAK_CURRENTLY`: the right next decision experiment is an independently frozen human/non-K3-defined event-continuity validation. If it fails, materialization should not be the paper center. If it passes, the more modest problem/operator story can be upgraded, followed by one predicate/domain replication.

See `outputs/research_contribution_convergence_v1/` for the evidence map, literature matrix, scorecard, reviewer attacks, and final thesis.
