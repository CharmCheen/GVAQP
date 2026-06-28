# Codex Analysis Prompt — CASQ / G-ClipAQP

You are analyzing the research status of the CASQ / G-ClipAQP project at `/qiuyeqing/llama_prl/G-ARC`.

## Instructions

Read the following files in this audit package (in order):

1. `EVIDENCE_PACK.md` — current research status, validated findings, failures, uncertainties
2. `EXPERIMENT_LINEAGE.md` — chronological dependency chain, superseded conclusions
3. `DECISION_LOG.md` — all extracted final decision strings with validity status
4. `KEY_RESULTS_TABLE.csv` — quantitative metrics across all experiments
5. `OPEN_QUESTIONS_AND_RISKS.md` — methodological, metric, dataset, oracle, and AQP risks

## Questions to Answer

### 1. Current Research Status Assessment

Based on the evidence, what is the strongest defensible claim the project can currently make? What is the weakest link in the evidence chain?

### 2. Separate Valid from Tentative Conclusions

Which conclusions are supported by unbiased full-oracle evaluation (V13.8/V13.9/V13.10)? Which are based on biased subsets (V13.7 labeled subset) or unreliable labels (Nexar-200 derived-boundary)? Distinguish clearly.

### 3. Strongest AQP/Database Contribution Angle

The project's stated contribution is: "proxy-agnostic statistical guarantee layer for clip-level approximate selection queries." Given the current evidence:

- Is the proxy-agnostic claim defensible with only YOLO+motion proxies tested?
- Would the statistical guarantee layer (block/event audit, LCB/UCB bounds) be the strongest contribution to emphasize?
- Or would the center10 anchor construction efficiency (2× call reduction, 0% abstain) be a more defensible near-term contribution?

### 4. Next 2-3 Experiments

Given the current state, recommend the next 2-3 experiments in priority order. For each, state:

- What question it answers
- What inputs it needs (which must already exist or be easily obtainable)
- What success looks like
- What failure looks like
- Whether it requires new VLM calls, new data, or only CPU analysis

### 5. Which Technical Direction?

Choose among these options and justify your choice with evidence from the audit:

- **ego-path-conditioned geometric proxy**: Estimate ego-lane from video, compute object-trajectory intersection
- **8B VLM cascade**: Use Qwen3-VL-8B as cheap first-pass scorer, 32B for top-ranked refinement
- **RoI-SigLIP / CLIP representation scorer**: Compute embeddings for center10 anchors, score by similarity to known conflict
- **adaptive query execution**: Revisit adaptive search with better base scores (only after fixing proxy quality)
- **metric reconciliation**: No further work needed — V13.9/V13.10 definitions reconciled
- **broader benchmark construction**: Second video + human-adjudicated labels before any general claim

### 6. How to Avoid Video Understanding Engineering Drift

The project's risk section warns against drifting into "better driving-event proxy design." For each of your recommended experiments, explain how it serves the DB/AQP contribution rather than becoming pure perception engineering.

## Output Format

Provide your analysis in structured markdown with these sections:

```markdown
# CASQ / G-ClipAQP Research Analysis

## 1. Current Status
## 2. Valid vs Tentative Conclusions
## 3. Strongest Contribution Angle
## 4. Recommended Experiments (2-3, in priority order)
## 5. Technical Direction Decision
## 6. Anti-Drift Safeguards
```

## Important Caveats (Read Before Answering)

- All VLM labels are `VLM_ORACLE_RELATIVE`, not human truth. Do not claim human-truth recall.
- All V13.x results are from a single 66-minute dashcam video. Do not generalize.
- The V13.9 event_recall numbers were confirmed by V13.10 reconciliation — no semantic difference in event-hit definitions exists.
- V13.7 labeled-subset results are biased (25% high-YOLO samples) and superseded by V13.9 full-oracle results.
- The V13.8 oracle is the single source of truth for all V13.9/V13.10 analyses.
- Certificate simulation has never been run on a valid oracle — the AQP statistical guarantee layer is untested.
- The master protocol is `CASQ_CODEX_BRIEF_V12_1.md`.
