#!/usr/bin/env python3
"""Task C: write diversity prefilter ablation report."""
from __future__ import annotations

import pandas as pd
import numpy as np
import common as C

s = pd.read_csv(C.REPLAY / "diversity_ablation_summary.csv")
factor = pd.read_csv(C.TABLES / "diversity_ablation_factor_effects.csv")
best = pd.read_csv(C.TABLES / "diversity_ablation_best_by_budget.csv")
det = s[s["temporal_strategy"] != "random_from_pool"]


def md_table(frame: pd.DataFrame, float_fmt="%.4f") -> str:
    if frame.empty:
        return "(empty)"
    cols = [str(c) for c in frame.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, r in frame.iterrows():
        vals = []
        for c in frame.columns:
            v = r[c]
            if isinstance(v, float):
                vals.append(float_fmt % v)
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


# P x proxy interaction
piv = det.groupby(["proxy", "P"])["event_cluster_recall_mean"].mean().unstack().round(4).reset_index()

# object_count_mean P=2.0 strategy comparison
strat_cmp_rows = []
for B in [40, 60, 80, 100, 150]:
    sub = det[(det["proxy"] == "object_count_mean") & (det["P"] == 2.0) & (det["budget"] == B)]
    for strat in ["linspace_spread", "greedy_maxmin_time", "score_weighted_spread_lam1.0", "block_round_robin_bs300"]:
        row = sub[sub["temporal_strategy"] == strat]
        if not row.empty:
            strat_cmp_rows.append({"budget": B, "strategy": strat, "event_recall": float(row["event_cluster_recall_mean"].iloc[0]), "singleton_recall": float(row["singleton_cluster_recall_mean"].iloc[0])})
strat_cmp = pd.DataFrame(strat_cmp_rows)
strat_piv = strat_cmp.pivot(index="budget", columns="strategy", values="event_recall").round(4).reset_index()

# best deployable per budget
dep_proxies = ["score_fusion_geometry_motion", "object_count_mean", "vehicle_count_mean", "motion_energy_mean"]
dep = det[det["proxy"].isin(dep_proxies)]
dep_best_rows = []
for B in [20, 30, 40, 60, 80, 100, 150]:
    sub = dep[dep["budget"] == B].sort_values("event_cluster_recall_mean", ascending=False).head(1)
    if not sub.empty:
        dep_best_rows.append(sub.iloc[0])
dep_best = pd.DataFrame(dep_best_rows)[["budget", "proxy", "P", "temporal_strategy", "event_cluster_recall_mean", "anchor_recall_mean", "singleton_cluster_recall_mean"]]

# factor tables
p_factor = factor[factor["factor"] == "P"][["level", "mean_event_recall", "mean_anchor_recall", "mean_singleton_recall"]].rename(columns={"level": "P"})
proxy_factor = factor[factor["factor"] == "proxy"][["level", "mean_event_recall", "mean_anchor_recall", "mean_singleton_recall"]].rename(columns={"level": "proxy"}).sort_values("mean_event_recall", ascending=False)
strat_factor = factor[factor["factor"] == "temporal_strategy"][["level", "mean_event_recall", "mean_anchor_recall", "mean_singleton_recall"]].rename(columns={"level": "strategy"}).sort_values("mean_event_recall", ascending=False)

report = f"""# 03 Diversity Prefilter Ablation

## Setup

Form: `top-PB by proxy -> select B with temporal strategy`.
Tie-breaking: top-PB pool built by `(proxy_score desc, anchor_index asc)` so count-feature
ties are broken deterministically by time order (this fixes the Task B tie-break anomaly and
makes results reproducible).

- Pool multiplier P: [1.0, 1.25, 1.5, 2.0, 3.0, 4.0]. P=1.0 = pure top-proxy.
- Proxies: score_fusion_geometry_motion, object_count_mean, person_count_max (hindsight),
  person_count_mean (hindsight), vehicle_count_mean, motion_energy_mean.
  (`bike_count_max` dropped — entirely missing in the canonical table.)
- Temporal strategies: linspace_spread, greedy_maxmin_time, temporal_nms (gap 10/20/30/60),
  block_round_robin (bs 150/300/600), random_from_pool (seeds 0..199),
  score_weighted_spread (lambda 0.25/0.5/1.0/2.0).
- Budgets B: [20,30,40,60,80,100,150]. No new VLM.

## Factor effect: P (marginal over proxy, strategy, budget)

{md_table(p_factor)}

**P=1.0 (pure top-proxy) has the highest marginal mean event recall (0.369) and it decreases
monotonically as P grows.** This is the headline ablation result: averaged over all proxies and
strategies, the diversity prefilter (P>1) *hurts*. But this marginal hides a strong interaction
with proxy strength (see below).

## Factor effect: proxy (marginal over P, strategy, budget)

{md_table(proxy_factor)}

`person_count_max` (hindsight, 0.438) and `person_count_mean` (hindsight, 0.416) dominate.
`object_count_mean` (deployable, 0.278) is the strongest deployable proxy.
`vehicle_count_mean` (0.164) is anti-predictive (AUROC 0.45).

## Factor effect: temporal strategy (marginal over proxy, P, budget)

{md_table(strat_factor)}

- `score_weighted_spread` (0.369) is marginally the best, but it is *flat* across P (see below).
- `block_round_robin` (0.350-0.355) and `greedy_maxmin_time` (0.354) are close.
- `linspace_spread` (0.342) — the current corrected method — is mid-pack, NOT the best.
- `random_from_pool` (0.323) is below all deterministic strategies (confirms diversity helps
  over random selection from the pool).
- `temporal_nms` (0.11-0.19) is much worse — over-suppresses and starves the budget.

## Interaction: proxy x P (mean event recall over deterministic strategies & budgets)

{md_table(piv)}

**Critical interaction:** P=1.0 (top-proxy) beats P=2.0 for the *strong* hindsight proxies
(person_count_max: 0.556 vs 0.416; person_count_mean: 0.529 vs 0.393) and for the *weak*
proxies (score_fusion: 0.307 vs 0.225; motion_energy: 0.307 vs 0.216). P=2.0 only helps for the
*medium* deployable proxy object_count_mean (0.333 vs 0.269).

**The corrected baseline's advantage is specific to a medium-strength proxy.** Diversity
(P=2.0) compensates for object_count_mean's moderate AUROC by spreading coverage; for a strong
proxy it discards high-score anchors and loses precision; for a weak proxy the pool is noise.

## Is P=2.0 optimal? — No.

For the deployable `object_count_mean` at B=80, linspace recall by P is non-monotonic and
peaks sharply at P=2.0 (0.481) with a dip at P=1.5 (0.296) and P=3.0 (0.296). This peak is not
robust — it is a linspace-grid artifact. With `greedy_maxmin_time` the curve is smoother and
the best P shifts (P=2.0-4.0 all ~0.44-0.52). The best deployable P is budget-dependent
(P=3.0 at B=20-30, P=4.0 at B=40-60, P=2.0 at B=80).

## Is linspace_spread sufficient? — No, greedy_maxmin_time is consistently better.

object_count_mean, P=2.0, event recall by strategy across budgets:

{md_table(strat_piv)}

`greedy_maxmin_time` >= `linspace_spread` at every budget, and fixes the B=100 linspace
anomaly (greedy_maxmin 0.481 vs linspace 0.333). `score_weighted_spread_lam1.0` is the most
*stable* (flat ~0.37 across B and P) but plateaus below the greedy_maxmin peak.
`block_round_robin_bs300` is competitive at B=40-100.

## Best deployable (non-hindsight) config per budget

{md_table(dep_best)}

At B=80 the best deployable is `object_count_mean, P=2.0, greedy_maxmin_time` with event
recall 0.5185 — beating the corrected linspace baseline (0.4815) and improving singleton
recall (0.381 vs 0.333).

## Required answers

1. **Is P=2.0 optimal?** No. P=1.0 is best for strong hindsight proxies; P=2.0-4.0 helps only
   for the medium deployable proxy object_count_mean, and the optimal P is budget-dependent.
   The P=2.0 peak under linspace is a grid artifact, not a robust optimum.
2. **Is linspace_spread sufficient?** No. `greedy_maxmin_time` is consistently >= linspace and
   fixes the B=100 anomaly. `score_weighted_spread` is more stable but plateaus lower.
3. **Does any temporal strategy stably beat linspace?** Yes — `greedy_maxmin_time` and
   `block_round_robin` both beat linspace for object_count_mean at B>=60.
4. **Corrected baseline gain: proxy or diversity?** Both, interacted. For object_count_mean
   (medium proxy), diversity (P=2.0) adds +0.11 event recall over top-proxy (P=1.0) at B=80.
   For a strong proxy (person_count_max), diversity *hurts* (-0.07). The corrected baseline's
   strength is the *combination* of a medium proxy + coverage spread, not diversity alone.
5. **Is object_count_mean still the deployable default?** Yes — it is the strongest deployable
   (non-hindsight) proxy at every budget B>=30. vehicle_count_mean occasionally wins at B=150
   by coverage saturation, but that is a high-budget artifact.
6. **Is person_count_max hindsight clearly stronger?** Yes — person_count_max top-proxy at
   B=80 is 0.630 event recall vs object_count_mean top-proxy 0.370. The hindsight gap is large.
7. **Does calibration-selected proxy approach hindsight?** Only via the deterministic
   temporal_grid calibration (Task B), which picks person_count_max/mean and matches hindsight
   diversity. Random calibration does not reliably reach hindsight.

## Limitations

- Single video; the proxy x P interaction may differ on a second video.
- The best overall configs use hindsight proxies (person_count_max/mean) and are NOT deployable
  without a calibration step that reliably selects them (which random calibration does not).
- `temporal_nms` with large gaps starves the budget; results are not competitive.
- B=150 has near-saturation behavior where coverage dominates proxy quality.

## Outputs

- `replay/diversity_ablation_long.csv` ({len(pd.read_csv(C.REPLAY/'diversity_ablation_long.csv'))} rows)
- `replay/diversity_ablation_summary.csv`
- `tables/diversity_ablation_best_by_budget.csv`
- `tables/diversity_ablation_factor_effects.csv`
- `replay/selections/diversity_ablation/...`
"""
(C.REPORTS / "03_DIVERSITY_PREFILTER_ABLATION.md").write_text(report, encoding="utf-8")
print("Task C report written.")
