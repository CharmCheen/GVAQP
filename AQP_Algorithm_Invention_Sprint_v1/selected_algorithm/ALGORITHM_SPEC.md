# VERA algorithm specification

## Name and novelty

**VERA — Variable-resolution Event-Relation AQP.** VERA compiles a temporal
cover of set-valued `EVENT_ENUMERATE` calls, overlap ownership and exact
fallbacks into a minimum-GPU-cost EventRelation plan. The novelty claim is the
plan problem and relation composition, not a prompt or a longer clip.

## Reference and approximate semantics

The reference query returns every event satisfying the frozen predicate. A
reference enumeration edge returns all reference events whose canonical point
lies in its ownership core, while reading a padded window for context. The
physical edge may miss, hallucinate, abstain or mislocalize and is explicitly
approximate. Final rows retain evidence-window lineage.

## Contracts

- Inputs to planning contain timeline/public metadata and frozen operator
  profiles only; evaluator reference and unqueried dense labels are forbidden.
- Cores form an exact disjoint cover. Padding is context, never additional
  ownership.
- Parser/UNKNOWN/resource failure takes the preregistered dense-unit fallback.
- Reconciliation is deterministic and never invents a new row without a
  physical event report.
- Dense execution is always legal.

## Frozen sprint objective

Minimize synchronized GPU seconds subject to recall and F1 at least 0.80 and
cost strictly below 0.70 dense. Cold/warm/logical/frame/token costs remain
separate diagnostics.

## Pilot instantiation

The selected pilot fixes 50-second cores with 5-second margins (nominal
60-second inputs), 2 fps video sampling and chronological execution. It uses no
strict-reference locations or CLIP ranking. This fixed plan isolates the
set-valued physical operator. The general DP is evaluated in simulation and
against fixed-window ablations; its risk model is not claimed calibrated by
the single-video pilot.

