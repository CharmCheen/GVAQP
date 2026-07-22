# Latent Event Diagnostics v1 — Round 1

## 1. Executive Decision

**SYNTHETIC_SCAFFOLD_READY.** The typed data model, M0 and real-K3 adapters, six synthetic regimes, four oracle actions (including the unsafe counterexample), six planners, evaluation, lineage and 10 required tests are operational.

**K3_PATH_UNTRUSTWORTHY.** The executable path is verified and reproducible, but its latent-event semantics are not trustworthy: every binary negative is a hard barrier, `D_seg_max` is dead in K3, 12 destructive positive bridges occur, and the evaluator masks distinct segment outputs.

**BLOCKED_BY_MISSING_ARTIFACTS.** Existing real logs have no typed relation outcomes, canonical anchors, actor/schema identity or unit multiplicity. Uniform/random/top-proxy common-materializer logs were not located. Full-oracle identifiability is not testable from these artifacts.

## 2. Repository State

- Repository: `/qiuyeqing/llama_prl/G-ARC`
- Branch/commit: `main` / `1a441186a94190254b29848089bb1f6327c6796e`
- Python: 3.10.20
- Core packages: numpy 2.2.6, pandas 2.2.2, scipy 1.13.1, scikit-learn 1.7.2, pytest 9.0.3, pyyaml 6.0.3
- Initial worktree: modified empty `AGENTS.md` plus pre-existing untracked Stage 0-2 scripts/output directories. None were changed or cleaned.
- Git initially required a `safe.directory` ownership exception.
- Expensive model calls: **0**. No training, download, video processing or GPU/model execution occurred.

## 3. Verified Algorithm Paths

- K3 BB-EM: `scripts/stage0_7_minimal_operator_compression.py::construct_k_segments`.
- Stage 0.7 CLI passes each explicit variant and evaluates newly generated variant-specific CSVs; no cache alias was found.
- K3 constants: `G_max=1`, `D_core_max=40s`, `D_seg_max=60s`, `E=1`. YAML is output-only.
- MAP: q0.70 components, 60s audit windows, deterministic tie order, 80/20 low-budget and 70/30 high-budget allocation. `seed` is not consumed.
- Stage 1B: 60/20/20 high-budget confirm/audit/barrier allocation; K3 cannot distinguish barrier action semantics.
- Existing evaluation: greedy one-to-one overlap-any/tIoU. Canonical-anchor matching was absent.

These are real code/artifact facts, not synthetic conclusions.

## 4. K3 Rule Trigger Audit

Across 211 fixed-log runs: gap limit caused 957 state changes (161 changed outputs), core duration caused 106 (79 outputs), and binary-negative barrier caused 228 (75 outputs). Positive merge joined 718 pairs. New middle positives destructively merged existing partitions in 12 action prefixes.

K3 has no boundary expansion, duplicate suppression or conflict resolution. `D_seg_max` is unreachable because K3 disables expansion. K4 expansion applies 1,372 times and changes 106 run outputs; its 60s cap rejects zero. C6 proxy-valley has 708 raw condition hits but zero independent C3-to-C4 changes; duplicate suppression has zero eligible pairs.

K3/K4/C6 aggregate metrics are identical while hashes differ (prior audit: C6 vs K3 in 204 rows). Therefore identical reported results do not imply algorithm equivalence. K3 is retained only as a legacy fixed-log comparator, not a frozen latent-event baseline.

## 5. Baseline Fairness Findings

- **VERIFIED:** SUPG all-selected and confirmed-only native selected sets differ, but all 30 paired runs have identical queried IDs, anchors, K3 outputs and metrics. Collapse begins at K3's binary input projection.
- **VERIFIED:** ABae strata use public proxy/time; pilot labels drive remaining allocation and pilot samples remain in final evidence. No oracle-informed failure strata exist.
- **LIKELY risk:** ABae-inspired aggregation allocation is adapted to event discovery; it is not a native event-discovery guarantee.
- **VERIFIED:** ARC native candidate clips are replaced by K3 rematerialization, changing ARC's native boundary/coverage behavior.
- **BLOCKED_BY_MISSING_ARTIFACT:** common real-data uniform/random/top-proxy paths could not be audited.

## 6. Diagnostic Infrastructure Added

- Typed public units, observations, hypotheses, relations, materialized events and separate GT events with JSON/CSV serialization.
- M0 materializer with soft ordinary negatives and typed SAME/DISTINCT overrides.
- Real K3 adapter with explicit ignored-relation accounting; no fabricated HSMM behavior.
- Posterior materializer contract for interval/count/partition/boundary marginals.
- Six seeded timeline regimes with latent GT and unit multiplicity stored outside planner inputs.
- Typed core/relation/coverage/naive-gap simulator with per-action errors and costs.
- P0-P5 non-learning policies; P4 priority is explicitly a heuristic scaffold.
- One-to-one and canonical matching, event/count/boundary/overmerge/oversplit/cost metrics, and complete action lineage.

## 7. Synthetic Smoke Findings

**Sanity evidence only:** R2/P4 emits relation probes; M0 `DISTINCT` can split one prediction into two, add one matched event, and add no positive anchor. R3/P5 produces 140 unsafe same-event splits. R4 open coverage reaches a proxy-zero event (K3 B20 recall 1.0 versus top-prior 2/3). Six planners produce five distinct R2 seed-0/B5/M0 sequences.

**Synthetic limitation:** high-budget M0/K3 metrics can degrade through over-querying and known materializer semantics. No performance superiority is claimed.

**Still unverified:** real-oracle identifiability, real relation-probe value, posterior calibration, actor identity, and fixed-evidence superiority on new datasets.

## 8. Blocking Issues

1. Real oracle logs do not distinguish normal negative, support negative and semantic separator.
2. No SAME/DISTINCT/AMBIGUOUS real relation observations exist.
3. Reference artifacts have no canonical anchor or actor identity; unit multiplicity is absent.
4. Existing greedy evaluator masks some materializer output differences.
5. MAP's nominal seed repeats are deterministic, so uncertainty across those runs is not meaningful.
6. Missing common artifacts block uniform/random/top-proxy fairness verification.

## 9. Recommended Next Experiment

**C. Fixed-log materializer decomposition.** Use the verified ordered observations, replace binary hard-barrier semantics with typed/soft counterfactuals, and score partition/hash changes with the new evaluator before collecting or planning relation probes. Do not tune on the existing test split.

## 10. Exact Commands to Reproduce

```bash
cd /qiuyeqing/llama_prl/G-ARC
PYTHONPATH=src python -m garc_eval.latent_event_diag.audit --output-dir outputs/latent_event_diag_v1
PYTHONPATH=src pytest -q tests/latent_event_diag > outputs/latent_event_diag_v1/test_report.txt 2>&1
PYTHONPATH=src python -m garc_eval.latent_event_diag.experiment --output-dir outputs/latent_event_diag_v1 --seed-count 20 --budgets 5,10,20,40
```

## 11. Files Changed

- New package: `src/garc_eval/latent_event_diag/`
- New tests: `tests/latent_event_diag/test_latent_event_diag.py`
- New isolated outputs: `outputs/latent_event_diag_v1/`

No pre-existing source, config, data or experiment output was modified.
