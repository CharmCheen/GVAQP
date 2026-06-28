# REPORTING_CONVENTIONS.md

## Purpose

Defines mandatory reporting conventions for all GLM/Qwen cascade experiments in this project.
All reports under `garc_eval/outputs/prompt_tuning_v1/heldout_cascade_eval_v1/` must follow these rules.

---

## 1. Candidate Pool Size N

Every table or chart that reports budget/recall/cost numbers must include:

- `N = <pool size>` in the table title or as a footnote
- The source of the pool (e.g., "123-sample pilot" or "clean pool N=100, tuning overlap removed")
- Whether B is absolute or relative to N

Example:
```
Table: Recall at B=40 (N=100, clean pool, 28 Qwen-positives)
```

Do NOT present N=100 and N=123 results side-by-side without explicitly labeling which pool each number comes from.

---

## 2. Tuning Overlap Disclosure

Any report that includes results from the 123-pilot must state whether the pool includes tuning-set overlap:

- `OVERLAP_INCLUDED`: Original 123-pilot, 23/123 anchors overlap with prompt tuning sets
- `OVERLAP_REMOVED`: Clean pool, 23 overlap anchors excluded, N=100

Numbers from `OVERLAP_INCLUDED` pools must carry the caveat: "upper bound, possibly inflated by tuning set familiarity (~4.4pp)".

---

## 3. Decision Labels

Decision labels must be one of:

| Label | Meaning |
|-------|---------|
| `USE_GLM_AS_ROUTER` | GLM can replace Qwen for most calls, minimal recall loss |
| `USE_GLM_AS_BOOSTER` | GLM positive boosts priority; GLM negative cannot be discarded |
| `USE_GLM_AS_BOOSTER_WEAKENED` | Direction holds but lift magnitude significantly reduced on clean data |
| `USE_GLM_AS_DISAGREEMENT_AUDIT_SIGNAL` | GLM/proxy disagreement enriches missed positives for audit |
| `DO_NOT_USE_GLM_IN_AQP_PLAN` | GLM provides no meaningful benefit |
| `BOOSTER_CANDIDATE_PENDING_CLEAN_REVALIDATION` | Temporary label: original结论 under revalidation |
| `GLM_NOT_USEFUL_AFTER_CLEAN_REVALIDATION` | Lift disappears or reverses on clean data |
| `STOP_GLM_CASCADE_ROUTE` | Gate failed, stop all GLM cascade work |

---

## 4. Reproducibility

Every experiment report must include:

- Random seed count (e.g., "500 seeds per (strategy, B) combination")
- Whether the strategy is deterministic (std=0) or stochastic (report mean ± std)
- GLM decoding config: `temperature=0.0, do_sample=False, max_new_tokens=2048`
- Script path used to produce the results

---

## 5. Scope Separation

Reports must explicitly distinguish:

- **Cost-reduction axis**: "Can a cheaper model reduce oracle calls?" (this task)
- **Candidate generation axis**: "Is there a new AQP mechanism?" (separate work, not addressed here)

Decision labels from the cost-reduction axis must NOT be cited as AQP algorithmic contributions.

---

## 6. Negative Results

Failed hypotheses and limitations must be documented explicitly, not omitted.

---

*Created 2026-06-27. Based on AGENTS.md reporting requirements.*
