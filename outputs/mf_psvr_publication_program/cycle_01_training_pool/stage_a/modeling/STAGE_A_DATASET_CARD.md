# MF-PSVR Stage-A candidate-value dataset card

## Scope

- Semantic samples: 192 query-aligned verification keys from 96 physical generic calls.
- Source datasets: 1.
- Source/provider sessions: 91.
- One row is one `(source_dataset, session_id, query_id, unit_id)` outcome. Q1/Q2 projections of one physical call are distinct semantic tasks; physical repeats never create rows.

## Label distribution

- Q1/abstain: 10
- Q1/negative: 76
- Q1/positive: 10
- Q2/abstain: 10
- Q2/negative: 72
- Q2/positive: 14

## Frozen split coverage

- model_calibration/Q1: 16
- model_calibration/Q2: 16
- model_train/Q1: 64
- model_train/Q2: 64
- pool_audit/Q1: 16
- pool_audit/Q2: 16

## Feature provenance

The dataset joins the frozen unit score, pre-label witness-track aggregates, independently materialized raw YOLO confidence and fixed-length trajectories, and the frozen oracle projection. The aggregate model has 61 runtime-visible numeric features after a label-free, intercept-aware rank pruning of 72 candidates. Source/session/call/unit/anchor/event identifiers and all oracle fields are excluded from model inputs. Raw `witness_class_id` is metadata only; aggregate models use categorical class indicators, while temporal models use a 9-way one-hot code.

## Limitations

- Stage A is deliberately enriched by preregistered strata; its class fraction is not population prevalence.
- All current rows come from one dataset family, so leave-one-dataset-out is unidentifiable at this stage.
- Most provider sessions contribute one unit and no session contributes more than two; exact leave-one-session-out predictions can be pooled, but per-session AUPRC is undefined for a one-row test fold.
- Oracle abstentions and parse failures are retained but excluded from binary training and scoring.
- The witness track is label-blind scheduling provenance. The unit label must not be interpreted as a verified track label.
- Temporal trajectories required a bounded replay of the exact frozen 96 units because the full-pool extractor discarded per-frame observations; no new unit, anchor, label, or oracle call was added.

## Intended use

Train and compare query-conditioned candidate-value ranking models under grouped source/session evaluation before deciding whether to enter the MF-PSVR physical pilot. Do not use this enriched sample to estimate natural-road prevalence.
