# Micro-CASQ Benchmark Protocol

## 1. Build Micro-CASQ v0

Start from `tables/micro_casq_candidate_pool_index.csv`. Draw the adjudication sample using `tables/micro_casq_adjudication_sampling_plan.csv`, then collect bounded 32B VLM and/or human results into `tables/micro_casq_adjudication_template.csv` using `schema/micro_casq_adjudication_schema.json`.

## 2. Gold-Eval Eligibility

Rows are eligible for gold evaluation only if:

- `label in {positive, negative}`;
- positives used for event-IoU metrics have `boundary_status == ok`;
- the row is not a pseudo-boundary;
- `source_video_path` exists or the video path is recoverable;
- `clip_start_time` and `clip_end_time` are present.

Ambiguous, abstain, truncated, and uncertain-boundary rows are retained for audit accounting but excluded from headline recall.

## 3. Splits

Use video-level splits:

- `candidate_dev`: may be used to choose candidate-generator hyperparameters.
- `heldout_eval`: used for final candidate recall/precision reporting only.
- `certification_sample`: fresh sample used only for final certificate calculations.

No source video may appear in multiple split roles.

## 4. Leakage Prevention

Candidate tuning cannot use heldout labels. Final certificates cannot reuse design, diagnostic, repair, pilot, or adjudication-planning samples. `event_start` and `event_end` are evaluation-only and must not be used to generate candidates.

## 5. Uncertainty Reporting

Report ambiguous/abstain counts by source, stratum, and reason. Exclude them from headline recall denominators but include them in limitations and failure analysis.

## 6. Sample Size

50-100 positive events are useful for candidate signal testing. Around 200 events may begin to help certificate tightness. Previous Phase 0.6 power simulation indicates roughly 500+ events were needed for consistently non-vacuous certificates in that simulation.

## 7. Claim Scope

Micro-CASQ v0 supports `O_enter_ego_path_v0`-specific findings only within its sampled domain. General claims require at least one additional independently sourced dataset such as DoTA or DADA/LOTVS-DADA.
