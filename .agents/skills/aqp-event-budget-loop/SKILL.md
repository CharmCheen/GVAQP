---
name: aqp-event-budget-loop
description: Run constrained AQP budget simulation, proxy-guided VLM allocation, event-level scheduling, pseudo-event evaluation, temporal clustering, and VLM-defined positive recovery experiments. Use for AQP budget simulation, proxy-guided VLM allocation, event-level scheduling, pseudo-event evaluation, temporal clustering, VLM-defined positive recovery, and coverage-aware scheduling work in this repository.
---

# AQP Event Budget Loop

## Core Contract

Treat this repository as a pseudo-oracle development environment unless the user explicitly redirects the work. Read `AGENTS.md` first and follow it as the controlling project policy.

Never use conservative VLM full-scan labels for ranking, candidate cluster construction, hyperparameter selection, feature training, or learned proxy training. Use them only for final pseudo-oracle evaluation.

Do not start human audit, construct real ground truth, generate audit packages, or launch new large-scale VLM inference unless the user explicitly asks.

## Workflow

1. Read `AGENTS.md`, then inspect existing experiment directories before changing code.
2. Audit input CSVs before implementation: record file paths, schema, row counts, source video count, positive count, score columns, time metadata, existing event definitions, and leakage risks.
3. Reuse existing proxy scores, budget simulation code, temporal NMS code, VLM labels, and CSV schemas where possible.
4. Implement the smallest viable event-budget experiment in a new isolated output directory.
5. Run a smoke test first.
6. Run sanity checks before interpreting results.
7. Run the full configured experiment only after smoke and sanity checks pass.
8. Read outputs, identify anomalies, make minimal fixes, and rerun affected steps.
9. Stop only when reports, tables, figures, config, manifest, logs, sanity checks, and a `GO` / `WEAK GO` / `NO-GO` decision are complete.

Append progress checkpoints to `logs/progress.md` with timestamp, checkpoint, commands run, result, failure if any, fix applied, and next action.

## Required Outputs

For each experiment, create an independent output directory containing at least:

- `config/`
- `data_manifest/`
- `scripts/`
- `logs/`
- `tables/`
- `figures/`
- `reports/`

Write:

- input manifest
- schema mapping YAML
- experiment config YAML
- results CSV tables
- required figures
- final Markdown report
- reproducible commands
- explicit `GO`, `WEAK GO`, or `NO-GO`

## Randomness And Splits

Use fixed random seeds. Random baselines require at least 100 repeats and must report mean, standard deviation, and 95% intervals.

For learned methods, check whether train/validation/test were split by source video or original video group. If leakage is possible, keep the learned score only as a development reference and do not use it as a main conclusion.

## Event-Budget Experiments

For pseudo-event scheduling experiments:

- Define pseudo-events only from conservative positive clips and only for evaluation.
- Build candidate clusters only from clip metadata and cheap scores.
- Prefer temporal-only clustering when track-aware data is unavailable; document why.
- Compare against clip-level ranking and temporal NMS baselines using a shared budget grid.
- Ensure no selected clip is counted as multiple VLM calls.

Read `references/metric_definitions.md` when implementing or reporting clip recall, pseudo-event recall, redundant call rate, calls per new event, or event discovery curves.

## Required Sanity Checks

Fail closed: if any check fails, stop interpretation, fix the implementation, and rerun.

- 100% budget gives deterministic methods clip recall and pseudo-event recall near 1.0.
- Random mean recall curves are broadly monotonic.
- Event count does not increase when merge gap increases.
- Temporal NMS with suppression disabled degenerates to raw score ranking.
- Coverage-aware scheduling with novelty/redundancy disabled approaches the cluster representative baseline.
- Static and runtime checks confirm sorting functions do not read conservative positive labels.
- Cluster methods do not count duplicate selected clips as multiple calls.

## Reporting Language

Use `pseudo-oracle`, `VLM-defined`, or `conservative VLM label` terminology. Do not claim real risk-event retrieval, human ground truth, or final G-ARC guarantees from these experiments.
