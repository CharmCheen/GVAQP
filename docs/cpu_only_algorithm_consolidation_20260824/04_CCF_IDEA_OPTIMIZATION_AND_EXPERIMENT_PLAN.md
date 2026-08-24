# CCF Idea Optimization and Experiment Plan

Date: 2026-08-24

Mode: idea optimization plus evidence design

Status: `PROMISING_SYSTEMS_QUESTION_INSUFFICIENT_EVIDENCE`

## 1. Optimized title

### Recommended English title

**From Unscanned Video to Durable Events: Deadline-Safe Evidence Acquisition for Open-Semantic Queries**

### Recommended Chinese title

**从未扫描视频到持久事件：面向开放语义查询的硬截止证据获取**

The previous human-event title remains suitable only if the paper returns to a measurement-first contribution. It no longer accurately describes an algorithm-first paper.

## 2. Optimized research problem

### Background

Open-semantic video queries can use a powerful semantic oracle to judge whether a candidate satisfies a natural-language predicate, but applying that oracle densely over long video is expensive. Under a hard deadline, the system must decide both where to inspect unseen video and which exposed candidates to confirm.

### Missing systems abstraction

Most neighboring systems optimize one of three easier settings:

1. a semantic index or proxy scores already exist;
2. a fixed candidate/frame population can be sampled or ranked;
3. the optimizer changes model configuration for already selected chunks.

GVAQP studies a stricter causal setting: SCAN creates candidates, VERIFY consumes exposed candidates, and only durable semantic events committed before deadline count.

### Core question

> How should an open-semantic video query engine interleave candidate discovery and semantic verification when unseen regions may contain new events, verification is expensive, and unfinished or uncommitted work has zero deadline utility?

## 3. Key insight

The current evidence does not justify a learned controller. The defensible insight is structural:

> Under weak learning support, enforce temporal exploration through deterministic breadth-first bisection, interleave discovery and verification with a fixed policy, and make deadline admission plus durable commit part of query semantics rather than implementation details.

This converts a weak “new controller” story into a sharper “new execution contract plus deadline-safe algorithm” story.

## 4. Proposed method

`DATB-SV` contains four modules:

1. **Temporal-bisection discovery:** spreads early SCAN actions across the unobserved timeline.
2. **Exposed-frontier verification:** VERIFY can consume only legally exposed candidates.
3. **Conservative deadline admission:** every action reserves worst-case execution and commit time.
4. **Durable event materialization:** confirmed duplicates collapse to stable event identities; post-deadline completions cannot alter output.

The semantic oracle is replaceable. Cached VLM output, a heavier model, or human decisions can instantiate the same interface.

## 5. Related-work positioning

| Work | Main setting | Why it does not subsume GVAQP |
|---|---|---|
| [BlazeIt](https://www.vldb.org/pvldb/vol13/p533-kang.pdf) | Declarative aggregation and limit queries using specialized NNs/control variates | Optimizes fixed frame-level query processing; does not model SCAN-created candidates and durable event commit |
| [TASTI](https://cs.stanford.edu/people/matei/papers/2022/sigmod_tasti.pdf) | Reusable semantic indexes for ML queries over unstructured data | Pays index construction and starts from indexed representatives; GVAQP targets initially unscanned, deadline-limited execution |
| [ExSample](https://oscar-moll.com/assets/pdf/Moll_ExSample_ICDE.pdf) | Adaptive sampling for object search in unindexed video | Closest discovery analogue, but its target is object instances/frames and not open-semantic candidate verification plus durable event semantics |
| [ZEUS](https://arxiv.org/abs/2104.06142) | RL changes sampling rate, segment length, and resolution for action localization | Assumes segments are sent to an action classifier and trains per-query optimization; it does not enforce the GVAQP exposure frontier or hard commit semantics |
| [FiGO](https://hparch.gatech.edu/papers/jiashen_sigmod2022.pdf) | Fine-grained model selection for video chunks under accuracy targets | Optimizes model choice over chunks, not causal discovery versus confirmation under a hard deadline |
| [Seiden](https://www.vldb.org/pvldb/vol16/p2289-kakkar.pdf) | Query-agnostic oracle-built index plus exploration/exploitation sampling | Requires prior oracle sampling/index construction and focuses on frame retrieval/aggregation; GVAQP begins without that index |
| [LAVA](https://arxiv.org/abs/2507.19821) | Language-driven traffic analytics using MAB segment localization, open-world detection, and trajectories | Most direct open-semantic competitor; its domain-specific training, equal segment arms, and trajectory pipeline differ, so GVAQP must win on deadline-safe causal execution rather than merely claiming language-driven sampling |

## 6. Novelty budget

### Potential contributions

1. A formal execution model coupling candidate discovery, semantic verification, durable materialization, and hard deadline utility.
2. A deterministic deadline-safe algorithm that remains valid when learned adaptivity is unsupported.
3. An oracle-agnostic evaluation showing which conclusions persist across cached VLM, heavy-model, and later human references.
4. A workload and metric protocol that measures independent committed events rather than positive frame/clip count.

### Claims that should not appear yet

1. “The first open-semantic video query system” without a broader novelty search.
2. “Better than ZEUS/LAVA” before common workloads and cost semantics exist.
3. “Human-aligned” before independent human-event evaluation.
4. “Adaptive controller” because the retained policy is intentionally fixed and deterministic.
5. “General” based on two production queries.

## 7. Three-party review synthesis

| Reviewer | Plan A: human-event measurement | Plan B: algorithm/controller | Suggested killer test |
|---|---:|---:|---|
| Qwen | 4.30 | 3.08 | First test B's scheduling gap |
| Seed | 3.37 | 2.49 | Annotate 30-40 exact-yield pairs |
| Claude | 3.36 | 2.62 | Annotate two workloads |

All three reviewers rank the measurement plan above the prior controller plan. Their disagreement concerns sequencing, not the weakness of the current controller evidence.

The Seed and Claude pair-level pilots conflict with the frozen statistical principle that `video x query` is the independent unit; 30-40 pairs do not create 30-40 independent samples. The integrated decision is therefore not to run a small outcome-driven human pilot, and not to resume learned control. It is to complete an oracle-agnostic deterministic system first, freeze its workloads and outputs, then conduct human external validation at workload level.

## 8. Falsifiable hypotheses

### H1: deadline-safe discovery benefit

Under equal physical cost and identical oracle outputs, DATB-SV yields more distinct committed events before deadline than linear or uniform scan baselines.

### H2: temporal spread mechanism

DATB-SV's benefit is larger when query-relevant events are temporally sparse or multimodal, and vanishes for dense/contiguous events.

### H3: oracle-source robustness

Action ordering is invariant to oracle identity given identical confirmation records, while measured utility may change when oracle judgments change.

### H4: event utility gap

At equal positive-clip yield, outputs may cover different independent human events. This remains a later external-validity hypothesis, not an input to scheduler design.

## 9. Staged experiment plan

### Stage 0: CPU contract validation - completed

Evidence: deterministic tests and synthetic replay.

Gate: no deadline violation, no post-deadline mutation, oracle-source invariance, exact event deduplication.

### Stage 1: cached real-trace replay - CPU only

Inputs must include legal candidate exposure, per-action cost provenance, and frozen oracle outcomes. Compare DATB-SV with uniform, sequential, largest-gap, and fixed-ratio policies.

Primary metric: `DistinctCommittedEvents@Deadline`.

Gate: at least six independent `video x query` workloads are recommended before inferential claims. With fewer workloads, report descriptive results only.

### Stage 2: physical cost validation - blocked now

Measure paired SCAN and VERIFY latency on the same hardware and runtime path. Do not combine the existing 2.018542-second scan pilot with the 18.694820-second cached Qwen timing as a causal ratio because their provenance is not pairable.

Gate: conservative duration bounds must retain useful admission capacity and hold at the preregistered rate.

### Stage 3: oracle robustness

Run the frozen outputs against at least two oracle implementations without changing scheduling. Separate scheduler robustness from oracle accuracy.

### Stage 4: human external validity

After algorithm, workload selection, and outputs are frozen, annotate maximal semantic events independently. Evaluate MEC and exact-yield event utility using the previously frozen human protocol.

## 10. Required result tables

1. End-to-end deadline utility by workload and deadline.
2. Anytime utility AUC and time to first event.
3. Admission failures, wasted work, and cost-bound violations.
4. Scan-order ablation.
5. SCAN/VERIFY-ratio ablation.
6. Durable-commit ablation using a diagnostic-only unsafe variant.
7. Oracle-source robustness.
8. Human MEC external validation, only after Stage 4.

## 11. Venue assessment

### Current state

The project is not submission-ready for SIGMOD or VLDB. It has a credible systems question and an executable CPU contract, but lacks broad workloads, paired physical costs, end-to-end baselines, and demonstrated effect size.

### Top-conference path

Top-conference potential exists only if the work establishes a general and material systems phenomenon:

1. candidate discovery and verification interaction changes optimal deadline execution;
2. DATB-SV or a similarly simple method wins consistently under fair common costs;
3. the effect spans diverse videos and open-semantic queries;
4. durable event semantics change conclusions relative to clip/frame yield;
5. competitors including ExSample, ZEUS, Seiden, FiGO, and LAVA are compared under clearly adapted but fair settings.

Without these results, the contribution is better framed as a rigorous negative/measurement study or a workshop/system demonstration rather than a SIGMOD/VLDB research paper.

## 12. Decision gates

| Gate | PASS | PARTIAL | FAIL |
|---|---|---|---|
| Real replay provenance | Compatible immutable manifest recovered | Partial fields with no claim-grade costs | Missing or reconstructed from outcomes |
| Algorithmic effect | Stable nontrivial gain across workloads | Heterogeneous/descriptive gain | Near-zero or baseline wins |
| Cost validity | Paired common-path measurements | Conservative simulation only | Mixed incomparable cost sources |
| Generalization | Diverse workload-level support | Few workloads | One source/query drives result |
| Human validity | MEC confirms output utility gap | Regime-specific gap | Clip yield already predicts events |

No failed gate should be rescued by training a controller, removing workloads, or tuning thresholds after outcomes.
