# Research Roadmap from the Current State

## Stage 0 — Completed mechanism gate

Result: `IDEAL_SIGNAL_ONLY`; no real cheap-primitive engineering; exploration/counterfactual routes stopped.

This stage answers whether the algorithmic idea is worth engineering. It does not establish a paper result by itself.

## Stage 1 — One-shot public representation transfer gate

Run the frozen R0/R1 × P0/P1 S2 experiment. No new features or candidates.

### If saturation transfers

Retain only event-cell representation + saturation. Validate on multiple videos before any additional feature work.

- 1-second or multi-resolution temporal microbins;
- actor tracking;
- ego-motion compensation;
- ego-corridor transition evidence;
- optional pretrained clip embeddings.

Freeze rules on development videos. The current strict video remains test-only.

### If saturation does not transfer

Permanently stop planner work and build the BB-EM/EventRelation operator route.

## Stage 2 — Barrier-Constrained Event Partition operator

Formulate event materialization as a constrained temporal partition problem over queried anchors/barriers. Derive an exact or provably correct DP and incremental maintenance algorithm. Establish anchor coverage, barrier safety, boundedness and deterministic identity. Compare against K3/K3-safe on frozen traces.

## Stage 3 — Expand data

One long video is insufficient. Obtain:

- multiple development videos for feature/rule selection;
- held-out videos for final evaluation;
- diverse event frequency, duration and traffic conditions;
- human-adjudicated event identity for at least a validation subset.

Investigate compatibility with CoMET-Bench for multi-event external validation and ExtremeWhen-style search evaluation. Do not assume their schemas directly match the driving predicate.

## Stage 4 — Strong baseline expansion

Implement or adapt retrieval, retrieve-then-ground and CoMET-style search-and-aggregate under an equal semantic-oracle cost ledger. Keep native and shared-materializer comparisons.

## Stage 5 — Validate the event physical operator

Across videos, selectors and event types:

- compare K3-safe with original K3 and fixed-evidence optimal partition ceilings;
- report barrier triggers and output changes;
- quantify boundary, overmerge and oversplit errors;
- test sensitivity without retuning on held-out videos.

## Stage 6 — Independent audit

Define a canonical anchor protocol, split discovery/audit ledgers, pre-register inclusion probabilities and validate empirical residual-event coverage. Use certificate language only if the statistical conditions pass.

## Stage 7 — Paper freeze

Freeze code/config/data splits before final test. Report the full cost–quality curve, uncertainty across videos, modern baselines, ablations and negative results. Choose the paper route based on achieved evidence, not the original ambition.
