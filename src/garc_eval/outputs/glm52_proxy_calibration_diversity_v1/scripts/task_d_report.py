#!/usr/bin/env python3
"""Task D: write selectivity diagnostic report."""
from __future__ import annotations

import pandas as pd
import numpy as np
import common as C

bs_summary = pd.read_csv(C.TABLES / "block_selectivity_summary.csv")
diag = pd.read_csv(C.ANALYSIS / "block_selectivity_diagnostic_agg.csv")
qm = pd.read_csv(C.ANALYSIS / "query_selectivity_proxy_metrics.csv")
qs = pd.read_csv(C.ANALYSIS / "query_selectivity_replay_summary.csv")


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


# Block diag B=80 bs=300
d80 = diag[(diag["block_size"] == 300) & (diag["budget"] == 80)]
share = d80.pivot(index="method", columns="selectivity_class", values="budget_share").round(3).reset_index()
rec = d80.pivot(index="method", columns="selectivity_class", values="recall_in_cls").round(3).reset_index()

# bs=600 cold
d600_cold = diag[(diag["block_size"] == 600) & (diag["selectivity_class"] == "cold")][["method", "budget", "budget_share", "recall_in_cls", "singleton_recall_in_cls"]].round(3)

# query AUROC pivot
auc_piv = qm.pivot(index="proxy", columns="query", values="auroc").round(3).reset_index()
auc_piv = auc_piv.sort_values("all_event", ascending=False)

report = f"""# 04 Selectivity Diagnostic

## 6.1 Block-level selectivity

Block classification by positive rate: hot (>=20%), medium (5-20%), cold (<5%).

{md_table(bs_summary)}

At block_size=300 there is 1 hot block (30 anchors, 11 positives, 36.7% rate), 9 medium blocks
(257 anchors, 29 positives), and 2 cold blocks (60 anchors, **0 positives**). At block_size=600
the single cold block has 2 positives (3.3% rate) — the only cold-block positives in the video.

### Budget share by selectivity class (bs=300, B=80)

{md_table(share)}

Proxy-based methods (top_proxy, diversity, best_calibration) put ~75% of budget in medium
blocks, ~14-19% in hot, ~6-12% in cold. uniform_random/temporal_grid put ~17% in cold (wasted,
since cold blocks at bs=300 have 0 positives) and only ~9% in hot.

### Recall by selectivity class (bs=300, B=80)

{md_table(rec)}

- All methods get **0 recall in cold blocks** at bs=300 (cold blocks have 0 positives — a
  coverage ceiling, not a method failure).
- Proxy methods get 0.455 hot-block recall and 0.34-0.38 medium recall.
- uniform methods get only 0.17-0.27 hot recall — they under-allocate to the dense hot block.

### Cold-block recall at bs=600 (the only cold block with positives)

{md_table(d600_cold)}

This is the key high/low-selectivity tradeoff:
- `top_proxy_object_count_mean` and `diversity_prefilter_object_count_mean` get **0 cold-block
  recall at every budget** — they rank the 2 cold-block positives low and never examine them.
- `best_calibration_selected_diversity` (person_count_mean proxy) gets 0.50 cold recall at
  B=40 and B=150 (the cold-block positives are pedestrian, which the person proxy ranks high),
  but 0 at B=80.
- `uniform_random` catches 0.24-0.45 of cold positives by chance; `uniform_temporal_grid`
  catches all 2 at B=150 (full coverage).

**Interpretation:** proxy methods maximize hot/medium recall but sacrifice cold coverage.
Uniform methods catch some cold positives but waste budget on empty cold blocks and lose hot
recall. The best_calibration (person proxy) is the only proxy method that recovers cold-block
positives, and only because those positives happen to be pedestrian. This is query/proxy-
dependent, not a general cold-block recovery mechanism.

### Singleton recall in cold blocks

At bs=150 (cold blocks have 0 positives) and bs=300, singleton recall in cold is 0 for all
methods (no cold positives exist). At bs=600, singleton cold recall equals cold recall (the 2
cold positives are singletons). No method improves cold singleton recall beyond the cold recall
pattern above.

See `analysis/block_selectivity_diagnostic.csv`, `analysis/block_selectivity_diagnostic_agg.csv`,
`tables/block_selectivity_summary.csv`.

## 6.2 Query-level selectivity

Sub-queries by `involved_object` (field present in canonical table): all_event (40 positives),
pedestrian_event (25), cyclist_event (11), vehicle_event (4), non_vehicle_event (36).

### Per-query proxy AUROC

{md_table(auc_piv)}

**The best proxy changes by query:**
- pedestrian / non_vehicle / cyclist: `person_count_max`/`person_count_mean` dominate
  (AUROC 0.78-0.84). `lateral_presence_max` is a strong second for non_vehicle (0.74).
- vehicle: **no proxy is strong**. Best is `score_fusion_geometry_motion` (0.585),
  `motion_energy_mean` (0.551), `object_count_mean` (0.509). person proxies are weak (0.535).
- `object_count_mean` is mediocre-but-stable across all queries (0.509-0.638).
- `vehicle_count_mean` is anti-predictive for every query (AUROC 0.43-0.48).

### Per-query replay (best deployable)

{md_table(qs)}

- For pedestrian/cyclist/non_vehicle, the hindsight person proxies dominate; the deployable
  fallback is `object_count_mean` (top or diversity).
- For **vehicle_event**, the best method (including hindsight) is
  `diversity_prefilter_object_count_mean` — person proxies are weak for vehicles, so the
  object-count diversity prefilter is the deployable winner AND the overall winner. No hindsight
  proxy improves on it for the vehicle query.

## Required answers

1. **Does the best proxy change by query selectivity?** Yes, strongly. person proxies win for
   pedestrian/cyclist/non_vehicle; score_fusion/motion win weakly for vehicle; object_count_mean
   is the stable mediocre default.
2. **Do pedestrian/cyclist queries depend more on person/bike/object count?** Yes —
   person_count proxies have AUROC 0.78-0.84 for pedestrian/cyclist/non_vehicle.
3. **Does vehicle query depend more on vehicle/motion/geometry proxy?** Partially — vehicle
   is the hardest query (only 4 positives, max AUROC 0.585). No proxy is genuinely strong;
   score_fusion and motion_energy edge out vehicle_count (which is anti-predictive).
4. **Does this support proxy calibration?** Yes — in principle. Different queries need
   different proxies, so a single fixed default is suboptimal. BUT on this single video the
   deployable `object_count_mean` remains the safest single default because it is mediocre-but-
   stable, while person proxies are excellent for non-vehicle but useless for vehicle. A
   query-aware calibration that picks person proxies for non-vehicle and object_count for
   vehicle would be the ideal, but the vehicle query is too small (4 positives) to calibrate
   reliably.

## Limitations

- Vehicle query has only 4 positives — AUROC/replay for it is high-variance and not generalizable.
- Cold-block analysis depends on block size; at bs=300 cold=0 positives, at bs=600 cold=2.
- Single video; the hot/cold split is specific to this video's event distribution.
- Labels are VLM-oracle-relative, not human truth.

## Outputs

- `analysis/block_selectivity_diagnostic.csv`, `analysis/block_selectivity_diagnostic_agg.csv`
- `analysis/block_selectivity_blocks_bs{150,300,600}.csv`
- `tables/block_selectivity_summary.csv`
- `analysis/query_selectivity_proxy_metrics.csv`
- `analysis/query_selectivity_replay_long.csv`, `analysis/query_selectivity_replay_summary.csv`
"""
(C.REPORTS / "04_SELECTIVITY_DIAGNOSTIC.md").write_text(report, encoding="utf-8")
print("Task D report written.")
