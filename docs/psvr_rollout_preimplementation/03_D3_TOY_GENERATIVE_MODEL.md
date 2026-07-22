
# D3 — Toy generative model

Status: `COMPLETE_FROZEN_SPECIFICATION`; no policy-quality run is authorized or produced.

The environment is a finite-horizon SMDP. It stores full latent state, exposes only a runtime information state to policies, and separately exposes evaluator-only truth after execution. `TOY_ENVIRONMENT_SCHEMA.json` freezes these boundaries. `TOY_CONSTRUCTION_SPEC.json` freezes SplitMix64, a conformance fixture, binary64 arithmetic, seed indexing, the complete ordered draw schedule, marginal and joint laws, geometry, absolute costs, transition kernels, identifiers, canonicalization, and visibility projection. A seed therefore identifies one episode rather than an implementation-dependent family of possible episodes.

Each episode has M media regions with latent events, complete SCAN cost distributions, candidate emission, and background hard negatives. Latent locations use `UNIFORM_SPARSE`, `UNIFORM_DENSE`, or `BURSTY_CLUSTERED`; event fields include query, region membership, interval, actor, detectability, multiplicity, and CONFIRM characteristics. A witness carries immutable identity, nullable latent event ID (environment-only), query, actor/tracklet, interval, proxy vector, raw score, creation time, and CONFIRM-cost parameters. Policy projections delete `latent_event_id`.

SCAN marks one region scanned, reveals proxy evidence, emits zero or more witnesses as a function of detectability, candidate quality, hard negatives, duplicates, and activity, updates grouping, consumes its complete random cost, and never commits. Under-merge splits one event's witnesses; over-merge combines different events and can irreversibly suppress later opportunities after one group is closed. This is structural opportunity loss, not score noise.

CONFIRM emits Oracle sign, materialization success/failure, new/duplicate/false-positive result, suppression/update, and complete duration. H-ROLLOUT1A fixes perfect Oracle/materialization but the schema retains H-ROLLOUT1B error fields. Costs include SCAN, CONFIRM, variance, switching, and planning. The three cost-ratio regimes and all eight requested axes are frozen in YAML. Primary planning cost is zero; parametric planning cost is auxiliary only.

Development and held-out seed universes are fixed, disjoint, and hash-bound; their parameter distributions are separately explicit. Construction conformance requires the frozen RNG uint64 fixture and, after implementation, canonical seed-to-episode fixture hashes before any policy comparison. `TOY_NAMED_SCENARIOS.json` fixes all ten diagnostic states, costs, witnesses, groups, emissions, horizons, and invariants; they cannot enter primary inference. Parameterized draws—not selected hand cases—define held-out evidence.
