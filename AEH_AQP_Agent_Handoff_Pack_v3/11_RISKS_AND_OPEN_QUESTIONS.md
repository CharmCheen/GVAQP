# Risks and Open Questions

## Scientific blockers

### R1 — Single video

Current strict evidence cannot establish cross-video generalization or venue-level robustness. Mitigation: acquire multiple development and held-out videos or adapt compatible external datasets.

### R2 — Candidate recall ceiling

Six of 26 strict events are absent from the legal universe. A better ranker cannot retrieve missing actions. Mitigation: schema-derived public search primitives and multi-resolution proposals.

### R3 — Weak public separability

Blocked-CV AUROC ~0.548 means the current public signal barely separates useful actions. Mitigation: actor tracks, ego-motion compensation, corridor-transition features, microbins and pretrained semantic embeddings—tested on development videos, not tuned on strict test labels.

### R4 — Planner mechanism may be illusory

Real-data BCM never activated intended actions. The controlled gate found only ideal/event-aligned saturation benefit; exploration was harmful and counterfactual gain negligible. A one-shot public event-cell transfer test is the final planner-related gate.

### R5 — Materializer overmerge/oversplit

BB-EM is bounded and barrier-aware but not necessarily optimal. Mitigation: fixed-evidence materializer ceilings and selector-agnostic cross-video tests.

### R6 — Oracle-relative validity

The user’s AQP abstraction may treat the oracle as exact. The empirical benchmark still uses a VLM-defined oracle and cannot prove real-world semantics. Keep the distinction explicit; add human adjudication for a paper claim if possible.

### R7 — Audit identifiability

Without unique canonical anchors and independent inclusion probabilities, residual event count is not identifiable. Use “empirical audit” until coverage is validated.

### R8 — Novelty compression

Coarse-to-fine search, multi-event search-and-aggregate and event graphs already exist. The contribution must be their integration under explicit oracle budget with event materialization and independent audit.

## Operational risks

- A800/A100 numerical differences or interrupted partial files.
- Hidden source changes between runs.
- Reusing a failed/provenance-incompatible artifact.
- Aggregate-only validation masking trace bugs.
- Agent silently expanding scope after a GO.

## Open questions for the next research phase

1. Can public event-cell ownership make saturation transfer to frozen S2 without adding information?
2. Can public schema-derived search reach candidate coverage ≥0.9 across videos?
3. Does BB-EM improve multiple selectors and event types at matched traces?
4. Does an independent audit ledger estimate residual events with calibrated empirical coverage?
5. Can typed actions improve the entire budget curve, especially B≤20?
6. Is the method competitive with CoMET-style and retrieve-then-ground baselines at equal semantic-oracle cost?
