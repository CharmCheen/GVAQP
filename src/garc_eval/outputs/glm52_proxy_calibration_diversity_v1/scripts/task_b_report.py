#!/usr/bin/env python3
"""Task B: write proxy calibration replay report."""
from __future__ import annotations

import pandas as pd
import numpy as np
import common as C

df = C.load_data()
s = pd.read_csv(C.REPLAY / "proxy_calibration_replay_summary.csv")
freq = pd.read_csv(C.TABLES / "proxy_selection_frequency.csv")
regret = pd.read_csv(C.TABLES / "proxy_calibration_regret.csv")
base = s[s["c"].isna()]
cal = s[s["c"].notna()]


def md_table(frame: pd.DataFrame, float_fmt="%.4f") -> str:
    if frame.empty:
        return "(empty)"
    cols = list(frame.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, r in frame.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                vals.append(float_fmt % v)
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


# Baseline winners at B=80
b80 = base[base["budget"] == 80].sort_values("event_cluster_recall_mean", ascending=False)
b80_show = b80[["method", "event_cluster_recall_mean", "anchor_recall_mean", "singleton_cluster_recall_mean", "multi_anchor_cluster_recall_mean"]].head(10)

# Best calibration config per B
best_cal_rows = []
for B in C.BUDGETS:
    cb = cal[cal["budget"] == B].sort_values("event_cluster_recall_mean", ascending=False).head(1)
    if not cb.empty:
        best_cal_rows.append(cb.iloc[0])
best_cal = pd.DataFrame(best_cal_rows)[["budget", "c", "calib_policy", "selection_rule", "event_cluster_recall_mean", "anchor_recall_mean", "singleton_cluster_recall_mean", "multi_anchor_cluster_recall_mean", "top_selected_proxy", "fallback_rate"]]

# Determinism check: temporal_grid std
det = cal[(cal["budget"] == 80) & (cal["c"] == 10)][["calib_policy", "selection_rule", "event_cluster_recall_mean", "event_cluster_recall_std", "top_selected_proxy", "top_proxy_freq"]]

# Proxy selection stability for random at c=10
stab_rand = freq[(freq["c"] == 10) & (freq["calib_policy"] == "calib_uniform_random") & (freq["selection_rule"] == "calib_auroc")].sort_values("count", ascending=False).head(6)

# Fraction beating default
frac_rows = []
for B in C.BUDGETS:
    sb = regret[regret["budget"] == B]
    if sb.empty:
        continue
    frac = float((sb["regret_vs_default"] < 0).mean())
    best = float(sb["mean_event_cluster_recall"].max())
    default = float(sb["default_event_recall"].iloc[0])
    hindsight = float(sb["hindsight_best_event_recall"].iloc[0])
    frac_rows.append({"budget": B, "frac_configs_beating_default": frac, "best_calib_event_recall": best, "default_event_recall": default, "hindsight_event_recall": hindsight})
frac_df = pd.DataFrame(frac_rows)

report = f"""# 02 Proxy Calibration Replay

## Setup

- Budgets B in [20,30,40,60,80,100,150]; calibration budget c in [5,10,15,20,30] (skip c>=B).
- Execution budget = B - c; calibration anchors drawn from all anchors and excluded from execution pool.
- Calibration sampling: `calib_uniform_random`, `calib_temporal_grid`, `calib_stratified_time_blocks`.
- Proxy selection rules: `calib_auroc`, `calib_auprc`, `calib_top_quantile_positive_rate`, `calib_topk_yield`, `calib_spearman`.
- Selected proxy drives diversity prefilter (top-PB by proxy, P=2.0, linspace spread, B-c execution anchors).
- Calibration method uses seeds 0..99 (200 was too slow; per task spec reduction allowed with note).
- Random baselines use seeds 0..199. Calibration labels simulated from existing VLM oracle reference. No new VLM.
- Core calibration candidate set: {len([c for c in ['score_fusion_geometry_motion','object_count_mean','object_count_max','person_count_mean','person_count_max','bike_count_mean','bike_count_max','vehicle_count_mean','vehicle_count_max','motion_energy_mean','motion_energy_max','near_ego_vehicle_count_mean','near_ego_vehicle_count_max','motorcycle_count_mean','lateral_presence_mean','lateral_presence_max','bbox_cx_std_mean','bbox_cx_std_max','bbox_area_sum_mean','bbox_area_sum_max','center_roi_vehicle_count_mean','bottom_roi_vehicle_count_mean','score_yolo_count','score_motion','score_fusion_yolo_motion'] if c in df.columns])} distinct cheap features.
- Fallback on degenerate calibration set (all-pos/all-neg): `object_count_mean`.

## Baseline ranking at B=80 (event-cluster recall)

{md_table(b80_show)}

## Best calibration config per budget

{md_table(best_cal)}

## Key Finding 1 — `calib_temporal_grid` is deterministic and "lucky"

The temporal-grid calibration sample is seed-independent (linspace by anchor_index), so proxy
selection is fixed across all 100 seeds. Standard deviation is ~1e-16 (effectively zero):

{md_table(det)}

At c=10, temporal_grid + auprc deterministically selects `person_count_mean` and reaches
event recall 0.5556 at B=80 — matching the hindsight `person_count_max` diversity prefilter
(0.5556) and exceeding the `object_count_mean` diversity default (0.4815).

**This is a single deterministic outcome, not a distribution over 100 independent runs.**
The temporal grid happens to land on a calibration set that captures the pedestrian-heavy
positives, so AUROC/AUPRC reliably identifies the person-count proxy. This is suggestive but
not a robust deployable claim — it is one favorable sample, equivalent to a hindsight-informed
choice on this specific video.

## Key Finding 2 — random/stratified calibration at small c is unstable

At c=10, `calib_uniform_random` + `calib_auroc` selects `object_count_mean` only 33% of the
time, `person_count_mean` 20%, and scatters across 9+ other proxies:

{md_table(stab_rand.rename(columns={"selected_proxy": "proxy", "count": "seeds_selected"}))}

Mean event recall for random/stratified calibration at B=80 is ~0.40 (std ~0.09), with
max ~0.42 — **below** the `object_count_mean` diversity default (0.4815). Fallback rate is
~26% (calibration set all-positive or all-negative at c=10).

## Key Finding 3 — calibration rarely beats the deployable default

{md_table(frac_df.rename(columns={"frac_configs_beating_default": "frac_beat_default"}))}

At B=40-80, only 10-24% of (c, policy, rule) configurations beat the `object_count_mean`
diversity default. The exceptions are B=100 (where the default itself drops to 0.333 due to a
linspace/tie-breaking anomaly — see Task C) and the deterministic temporal_grid peaks.

## Proxy selection frequency highlights

- `calib_temporal_grid` c=10 + auroc → `person_count_max` 700/700 (100%).
- `calib_temporal_grid` c=10 + auprc → `person_count_mean` 700/700 (100%).
- `calib_uniform_random` c=5 + auroc → `object_count_mean` 469/700 (67%), then scattered.

Full table: `tables/proxy_selection_frequency.csv`.

## Regret vs hindsight and default

- Best calibration (temporal_grid c=10 auprc, B=80): regret_vs_hindsight = 0.0000 (matches
  hindsight person proxy diversity); regret_vs_default = -0.0741 (beats default).
- Worst calibration (temporal_grid c=5 spearman, B=80): regret_vs_default = +0.370 (picks a
  bad proxy deterministically).
- Random calibration mean regret_vs_default at B=80 ≈ +0.08 (worse than default on average).

Full table: `tables/proxy_calibration_regret.csv`.

## Answers to core questions (Task B)

1. **Can a small calibration set auto-select an effective cheap proxy?**
   Only with a *representative* calibration set. The deterministic temporal grid does, but
   realistic random sampling at c=5-15 is unstable (33-67% top-proxy agreement, 26% fallback)
   and on average does NOT beat the `object_count_mean` default.
2. **Does calibration-selected diversity beat the corrected baseline?**
   The single best deterministic config matches hindsight and beats the default, but the
   *expected* calibration outcome (random sampling) underperforms the `object_count_mean`
   diversity default at B=40-80.
3. **Is calibration stable enough to deploy?**
   No — on this single video, random calibration is too noisy at small c. The temporal_grid
   result is deterministic but equivalent to a lucky single sample, not a robust method.

## Limitations

- Single video (dataset3); calibration stability may differ on a second video.
- Calibration labels are the existing VLM pseudo-oracle, not human truth.
- Core candidate set excludes redundant duplicates but still has 25 features; small-c
  AUROC over 25 candidates is high-variance.
- The `object_count_mean` diversity default at B=100 in this replay is 0.333 (vs 0.481 in the
  codex replay) due to proxy-score tie-breaking in top-PB pool construction — a robustness
  issue for linspace spread, documented in Task C.

## Outputs

- `replay/proxy_calibration_replay_long.csv` (per-run, {len(pd.read_csv(C.REPLAY/'proxy_calibration_replay_long.csv'))} rows)
- `replay/proxy_calibration_replay_summary.csv`
- `tables/proxy_selection_frequency.csv`
- `tables/proxy_calibration_regret.csv`
- `replay/selections/proxy_calibration/...` (saved per-method selections)
"""
(C.REPORTS / "02_PROXY_CALIBRATION_REPLAY.md").write_text(report, encoding="utf-8")
print("Task B report written.")
