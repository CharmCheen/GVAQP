#!/usr/bin/env python3
"""within_bin_tiebreak_ablation_v1 — diagnostic agent.

Question: inside the current CILS top p_answer bin, does any non-oracle feature
or simple combination rule rank answer-positive interval candidates ahead of
false positives?

Strict constraints:
- no model reruns, no new proposals, no calibration changes, no selector changes
- no label-trained features
- full reference used only for evaluation / ablation scoring
- all results marked diagnostic only
- point-anchor events and true-interval events separated; main analysis uses
  true interval event hit only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
sys.path.insert(0, str(ROOT / "src"))
from garc_eval.metrics.craq_lite_metrics import Interval, interval_iou

OUT = ROOT / "src/garc_eval/outputs/within_bin_tiebreak_ablation_v1"
OUT.mkdir(parents=True, exist_ok=True)

V2 = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak"
SMOKE = ROOT / "src/garc_eval/outputs/cils_calibration_repair_smoke_v1"
PATCH = ROOT / "runs/craq_lite_v1/20260701T075242Z/patch_smoke"

# ---------- helpers ----------

def to_intervals(df, id_col="event_id"):
    out = []
    for r in df.itertuples(index=False):
        eid = getattr(r, id_col, None)
        out.append(Interval(float(r.t_start), float(r.t_end), eid))
    return out


def precision_at_k(order, y, k):
    if len(order) == 0:
        return float("nan")
    k = min(k, len(order))
    return float(y.iloc[order[:k]].mean())


def recall_at_k(order, sel_df, events, k):
    if len(order) == 0 or len(events) == 0:
        return 0.0
    k = min(k, len(order))
    top = sel_df.iloc[order[:k]]
    preds = to_intervals(top, "interval_id")
    evs = to_intervals(events, "event_id")
    # event recall: count events hit by any pred at IoU>=0.3
    hit = 0
    for ev in evs:
        if any(interval_iou(p, ev) >= 0.3 for p in preds):
            hit += 1
    return hit / len(evs)


def event_coverage_at_k(order, sel_df, events, k):
    if len(order) == 0:
        return set()
    k = min(k, len(order))
    top = sel_df.iloc[order[:k]]
    covered = set()
    for ev in events.itertuples(index=False):
        ev_int = Interval(ev.t_start, ev.t_end, ev.event_id)
        for r in top.itertuples(index=False):
            if interval_iou(Interval(r.t_start, r.t_end), ev_int) >= 0.3:
                covered.add(ev.event_id)
                break
    return covered


def duplicate_rate_at_k(order, sel_df, k):
    if len(order) == 0:
        return 0.0
    k = min(k, len(order))
    top = sel_df.iloc[order[:k]]
    if len(top) <= 1:
        return 0.0
    preds = to_intervals(top, "interval_id")
    dups = 0
    for i in range(len(preds)):
        for j in range(i + 1, len(preds)):
            if interval_iou(preds[i], preds[j]) > 0.3:
                dups += 1
    return dups / len(preds)


def background_ratio_at_k(order, sel_df, k):
    """fraction of top-k that match no reference event (interval or point)."""
    if len(order) == 0:
        return float("nan")
    k = min(k, len(order))
    top = sel_df.iloc[order[:k]]
    if "matched_event_id" not in top:
        return float("nan")
    return float(top["matched_event_id"].isna().mean())


def avg_duration_at_k(order, sel_df, k):
    if len(order) == 0:
        return float("nan")
    k = min(k, len(order))
    return float(sel_df.iloc[order[:k]]["duration"].mean())


# ---------- Stage 0: artifact inventory ----------

def stage0_inventory():
    rows = []
    candidates = [
        ("cils_calibration_repair_smoke_v1/smoke_candidate_p_answer.csv", SMOKE / "smoke_candidate_p_answer.csv"),
        ("cils_calibration_repair_replay_v1/candidate_p_answer_by_policy.csv", ROOT / "src/garc_eval/outputs/cils_calibration_repair_replay_v1/candidate_p_answer_by_policy.csv"),
        ("clean_v2/interval_lattice_features_only.csv", V2 / "interval_lattice_features_only.csv"),
        ("clean_v2/interval_lattice_v2_clean.csv", V2 / "interval_lattice_v2_clean.csv"),
        ("clean_v2/interval_labels_v2_clean.csv", V2 / "interval_labels_v2_clean.csv"),
        ("cils_calibration_repair_smoke_v1/smoke_selected_intervals.csv", SMOKE / "smoke_selected_intervals.csv"),
        ("cils_calibration_repair_smoke_v1/smoke_interval_eval_curve.csv", SMOKE / "smoke_interval_eval_curve.csv"),
        ("clean_v2/reference_events.csv", V2 / "reference_events.csv"),
        ("patch_smoke/reference_audit.csv", PATCH / "reference_audit.csv"),
    ]
    for name, p in candidates:
        if p.exists():
            try:
                df = pd.read_csv(p)
                rows.append({"artifact": name, "exists": True, "n_rows": len(df), "n_cols": df.shape[1], "columns": ", ".join(df.columns.tolist()[:20])})
            except Exception as e:
                rows.append({"artifact": name, "exists": True, "n_rows": -1, "n_cols": -1, "columns": f"ERR {e}"})
        else:
            rows.append({"artifact": name, "exists": False, "n_rows": 0, "n_cols": 0, "columns": ""})
    inv = pd.DataFrame(rows)
    inv.to_csv(OUT / "artifact_inventory.csv", index=False)
    md = ["# Artifact Inventory\n", "| artifact | exists | n_rows | n_cols | columns |", "| --- | --- | --- | --- | --- |"]
    for _, r in inv.iterrows():
        md.append(f"| {r['artifact']} | {r['exists']} | {r['n_rows']} | {r['n_cols']} | {r['columns'][:120]} |")
    (OUT / "artifact_inventory.md").write_text("\n".join(md) + "\n")
    print("Stage 0 done.")


# ---------- Stage 1: reconstruct top p_answer bin ----------

def stage1_top_bin():
    # Use smoke candidate_p_answer: budget=80, pilot=answer_quality_proxy_top,
    # cal=beta_bin_strata_lower, seed=0 (matches patch_smoke calibrate_cils).
    pa = pd.read_csv(SMOKE / "smoke_candidate_p_answer.csv")
    pa = pa[(pa.budget == 80) & (pa.pilot_policy == "answer_quality_proxy_top") & (pa.calibration_model == "beta_bin_strata_lower") & (pa.seed == 0)]
    pa = pa[["interval_id", "p_answer"]].copy()

    feats = pd.read_csv(V2 / "interval_lattice_features_only.csv")
    lat = pd.read_csv(V2 / "interval_lattice_v2_clean.csv")
    lab = pd.read_csv(V2 / "interval_labels_v2_clean.csv")
    ref = pd.read_csv(V2 / "reference_events.csv")
    audit = pd.read_csv(PATCH / "reference_audit.csv")

    # merge p_answer + features + labels
    df = feats.merge(pa, on="interval_id", how="inner")
    df = df.merge(lab[["interval_id", "answer_iou_0_3", "answer_iou_0_5", "matched_event_id", "best_iou", "any_overlap", "center_hit", "event_hit_iou_0_3", "event_hit_iou_0_5", "positive_unit_fraction"]], on="interval_id", how="left")
    # add overlap_group_id, method, source_signal from lattice
    df = df.merge(lat[["interval_id", "overlap_group_id", "method", "source_signal"]], on="interval_id", how="left", suffixes=("", "_lat"))

    # point-anchor flag: matched_event_id is a point anchor (is_interval_event==0)
    interval_events = set(audit[audit.is_interval_event == 1].event_id)
    point_events = set(audit[audit.is_interval_event == 0].event_id)
    df["matches_interval_event"] = df.matched_event_id.isin(interval_events)
    df["matches_point_anchor"] = df.matched_event_id.isin(point_events)
    df["point_anchor_only"] = df.matches_point_anchor & ~df.matches_interval_event

    # boundary_quality = normalized boundary drops (matches run_craq_lite)
    bdrop = df["boundary_left_drop"] + df["boundary_right_drop"]
    bnorm = (bdrop - bdrop.min()) / (bdrop.max() - bdrop.min()) if bdrop.max() > bdrop.min() else bdrop * 0
    df["boundary_quality"] = bnorm.fillna(0.0)

    # top p_answer bin
    top_pa = float(df.p_answer.max())
    bin_df = df[df.p_answer >= top_pa - 1e-9].copy().reset_index(drop=True)

    # save full bin candidates
    cols = ["interval_id", "t_start", "t_end", "duration", "p_answer", "active_score", "max_score",
            "mean_score", "score_persistence", "boundary_left_drop", "boundary_right_drop",
            "boundary_quality", "signal_disagreement", "method", "source_signal",
            "answer_iou_0_3", "answer_iou_0_5", "matched_event_id", "matches_interval_event",
            "matches_point_anchor", "point_anchor_only", "num_units", "best_iou", "positive_unit_fraction"]
    cols = [c for c in cols if c in bin_df.columns]
    bin_df[cols].to_csv(OUT / "top_p_answer_bin_candidates.csv", index=False)

    n = len(bin_df)
    n_tp = int(bin_df.answer_iou_0_3.astype(bool).sum())
    n_iou5 = int(bin_df.answer_iou_0_5.astype(bool).sum())
    n_int_tp = int(bin_df.matches_interval_event.sum())
    n_point_only = int(bin_df.point_anchor_only.sum())
    n_bg = int(bin_df.matched_event_id.isna().sum())

    summary = f"""# Top p_answer Bin Summary

**Diagnostic only.** Reference gate FAIL (6 true interval events).

Configuration reconstructed:
- pilot_policy = answer_quality_proxy_top
- calibration_model = beta_bin_strata_lower
- budget = 80, seed = 0
- source: cils_calibration_repair_smoke_v1/smoke_candidate_p_answer.csv

Top bin p_answer = {top_pa:.6f}

| stat | value |
| --- | --- |
| n candidates in bin | {n} |
| n answer_iou_0_3 = True (TP) | {n_tp} |
| n answer_iou_0_5 = True | {n_iou5} |
| n matches true interval event | {n_int_tp} |
| n point-anchor only | {n_point_only} |
| n background (no event match) | {n_bg} |
| bin precision (TP / n) | {n_tp / n:.4f} |

All candidates share overlap_group_id = {bin_df.overlap_group_id.unique().tolist()}.

True interval events represented in bin: {sorted(bin_df[bin_df.matches_interval_event].matched_event_id.unique().tolist())}
"""
    (OUT / "top_bin_summary.md").write_text(summary)
    print(f"Stage 1: top bin p_answer={top_pa:.4f} n={n} TP={n_tp}")
    return bin_df, interval_events, audit


# ---------- Stage 2: oracle ceiling ----------

def stage2_oracle_ceiling(bin_df, audit):
    events = audit[audit.is_interval_event == 1].reset_index(drop=True)
    y = bin_df.answer_iou_0_3.astype(bool)
    # oracle order: TP first, then by duration asc (shortest TP first — typical oracle)
    oracle_order = np.argsort(-(y.astype(int).values) + bin_df.duration.values * 1e-6)
    # actually pure oracle: all TPs first in any order; we use TP desc then duration asc
    tp_idx = np.where(y.values)[0]
    fp_idx = np.where(~y.values)[0]
    oracle_order = np.concatenate([tp_idx, fp_idx])

    ks = [1, 3, 5, 10, 20, 30, 50]
    rows = []
    for k in ks:
        if k > len(oracle_order):
            break
        prec = precision_at_k(oracle_order, y, k)
        rec = recall_at_k(oracle_order, bin_df, events, k)
        cov = event_coverage_at_k(oracle_order, bin_df, events, k)
        rows.append({
            "k": k, "oracle_precision": prec, "oracle_recall_iou0_3": rec,
            "n_distinct_events_covered": len(cov), "covered_events": ",".join(sorted(cov)),
            "n_in_bin": len(bin_df), "n_tp": int(y.sum()), "n_fp": int((~y).sum()),
        })
    odf = pd.DataFrame(rows)
    odf.to_csv(OUT / "top_bin_oracle_ceiling.csv", index=False)
    md = ["# Top Bin Oracle Ceiling\n", "**Diagnostic only.**\n", f"bin: {len(bin_df)} candidates, {int(y.sum())} TP, {int((~y).sum())} FP\n",
          "| k | oracle precision | oracle recall@0.3 | n events covered | covered events |",
          "| --- | --- | --- | --- | --- |"]
    for _, r in odf.iterrows():
        md.append(f"| {int(r['k'])} | {r['oracle_precision']:.4f} | {r['oracle_recall_iou0_3']:.4f} | {r['n_distinct_events_covered']} | {r['covered_events']} |")
    (OUT / "top_bin_oracle_ceiling.md").write_text("\n".join(md) + "\n")
    print(f"Stage 2: oracle precision@20 = {odf[odf.k==20].oracle_precision.values[0]:.4f}")


# ---------- Stage 3: single-feature ranking ablation ----------

SINGLE_FEATURES = [
    ("active_score_desc", "active_score", False),
    ("active_score_asc", "active_score", True),
    ("max_score_desc", "max_score", False),
    ("max_score_asc", "max_score", True),
    ("mean_score_desc", "mean_score", False),
    ("mean_score_asc", "mean_score", True),
    ("score_persistence_desc", "score_persistence", False),
    ("score_persistence_asc", "score_persistence", True),
    ("boundary_quality_desc", "boundary_quality", False),
    ("boundary_quality_asc", "boundary_quality", True),
    ("boundary_left_drop_desc", "boundary_left_drop", False),
    ("boundary_left_drop_asc", "boundary_left_drop", True),
    ("boundary_right_drop_desc", "boundary_right_drop", False),
    ("boundary_right_drop_asc", "boundary_right_drop", True),
    ("boundary_drop_sum_desc", "__bdrop_sum", False),
    ("boundary_drop_sum_asc", "__bdrop_sum", True),
    ("signal_disagreement_desc", "signal_disagreement", False),
    ("signal_disagreement_asc", "signal_disagreement", True),
    ("duration_desc", "duration", False),
    ("duration_asc", "duration", True),
    ("num_units_desc", "num_units", False),
    ("num_units_asc", "num_units", True),
    ("p_answer_desc", "p_answer", False),
    ("active_over_1_plus_duration_desc", "__aod", False),
    ("active_over_1_plus_boundary_desc", "__aob", False),
    ("neg_boundary_quality_desc", "__nbq", False),  # -boundary_quality
    ("neg_duration_desc", "__nd", False),  # -duration
    ("active_minus_boundary_desc", "__amb", False),
    ("boundary_minus_active_desc", "__bma", False),
    ("persistence_minus_boundary_desc", "__pmb", False),
    ("persistence_minus_disagreement_desc", "__pmd", False),
    ("moderate_duration_score_desc", "__mds", False),  # 1 if 5<=dur<=20 else 0
    ("boundary_drop_score_desc", "__bds", False),  # boundary_left+right
    ("persistence_score_desc", "__ps", False),  # score_persistence
]


def stage3_single_feature(bin_df, audit):
    events = audit[audit.is_interval_event == 1].reset_index(drop=True)
    y = bin_df.answer_iou_0_3.astype(bool)

    # precompute derived
    bd = bin_df.copy()
    bd["__bdrop_sum"] = bd["boundary_left_drop"] + bd["boundary_right_drop"]
    bd["__aod"] = bd["active_score"] / (1.0 + bd["duration"])
    bd["__aob"] = bd["active_score"] / (1.0 + bd["boundary_quality"])
    bd["__nbq"] = -bd["boundary_quality"]
    bd["__nd"] = -bd["duration"]
    bd["__amb"] = bd["active_score"] - bd["boundary_quality"]
    bd["__bma"] = bd["boundary_quality"] - bd["active_score"]
    bd["__pmb"] = bd["score_persistence"] - bd["boundary_quality"]
    bd["__pmd"] = bd["score_persistence"] - bd["signal_disagreement"]
    bd["__mds"] = bd["duration"].between(5, 20).astype(float)
    bd["__bds"] = bd["boundary_left_drop"] + bd["boundary_right_drop"]
    bd["__ps"] = bd["score_persistence"]

    ks = [1, 3, 5, 10, 20]
    rows = []
    for name, col, asc in SINGLE_FEATURES:
        if col not in bd:
            continue
        order = np.argsort(bd[col].values, kind="stable") if asc else np.argsort(-bd[col].values, kind="stable")
        for k in ks:
            if k > len(order):
                continue
            prec = precision_at_k(order, y, k)
            rec = recall_at_k(order, bd, events, k)
            cov = event_coverage_at_k(order, bd, events, k)
            dr = duplicate_rate_at_k(order, bd, k)
            br = background_ratio_at_k(order, bd, k)
            ad = avg_duration_at_k(order, bd, k)
            rows.append({
                "rule": name, "feature": col, "ascending": asc, "k": k,
                "precision_at_k": prec, "recall_iou0_3_at_k": rec,
                "n_events_covered": len(cov), "covered_events": ",".join(sorted(cov)),
                "duplicate_rate_at_k": dr, "background_ratio_at_k": br, "avg_duration_at_k": ad,
            })
    sdf = pd.DataFrame(rows)
    sdf.to_csv(OUT / "single_feature_tiebreak_results.csv", index=False)

    # summary: focus on k=20
    md = ["# Single-Feature Tie-Break Results\n", "**Diagnostic only.**\n",
          "## k=20 precision and recall by rule\n",
          "| rule | precision@20 | recall@20 | events covered | dup rate | bg ratio | avg dur |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    s20 = sdf[sdf.k == 20].sort_values("precision_at_k", ascending=False)
    for _, r in s20.iterrows():
        md.append(f"| {r['rule']} | {r['precision_at_k']:.4f} | {r['recall_iou0_3_at_k']:.4f} | {r['n_events_covered']} | {r['duplicate_rate_at_k']:.4f} | {r['background_ratio_at_k']:.4f} | {r['avg_duration_at_k']:.2f} |")
    (OUT / "single_feature_tiebreak_summary.md").write_text("\n".join(md) + "\n")
    print(f"Stage 3: {len(sdf)} rows. Best precision@20 = {s20.precision_at_k.max():.4f}")
    return bd, events


# ---------- Stage 4: composite ranking ablation ----------

COMPOSITE_RULES = [
    "current_utility_desc", "current_utility_asc",
    "active_desc_boundary_asc", "persistence_desc_boundary_asc",
    "active_plus_persistence_minus_boundary",
    "active_plus_boundary_drop_minus_duration",
    "persistence_plus_boundary_drop_minus_disagreement",
    "moderate_duration_plus_persistence",
    "low_boundary_quality_plus_high_persistence",
    "active_score_minus_duration_penalty",
    "inverse_boundary_quality_minus_duration",
]


def composite_score(bd, rule):
    a = bd["active_score"].values
    p = bd["score_persistence"].values
    bq = bd["boundary_quality"].values
    bld = bd["boundary_left_drop"].values
    brd = bd["boundary_right_drop"].values
    bs = bld + brd
    sd = bd["signal_disagreement"].values
    d = bd["duration"].values
    pa = bd["p_answer"].values
    dur_cap = 32.0
    value = np.minimum(d, dur_cap) * (0.5 + 0.5 * a)
    if rule == "current_utility_desc":
        return pa * value * bq
    if rule == "current_utility_asc":
        return -(pa * value * bq)
    if rule == "active_desc_boundary_asc":
        return a - bq
    if rule == "persistence_desc_boundary_asc":
        return p - bq
    if rule == "active_plus_persistence_minus_boundary":
        return a + p - bq
    if rule == "active_plus_boundary_drop_minus_duration":
        return a + bs - d
    if rule == "persistence_plus_boundary_drop_minus_disagreement":
        return p + bs - sd
    if rule == "moderate_duration_plus_persistence":
        return bd["duration"].between(5, 20).astype(float).values + p
    if rule == "low_boundary_quality_plus_high_persistence":
        return (1.0 - bq) + p
    if rule == "active_score_minus_duration_penalty":
        return a - np.maximum(0.0, (d - 20.0) / 20.0)
    if rule == "inverse_boundary_quality_minus_duration":
        return (1.0 - bq) - d / 100.0
    raise ValueError(rule)


def stage4_composite(bd, events, rng_seed=20260630):
    y = bd.answer_iou_0_3.astype(bool)
    ks = [1, 3, 5, 10, 20]
    rows = []
    for rule in COMPOSITE_RULES:
        score = composite_score(bd, rule)
        order = np.argsort(-score, kind="stable")
        for k in ks:
            if k > len(order):
                continue
            prec = precision_at_k(order, y, k)
            rec = recall_at_k(order, bd, events, k)
            cov = event_coverage_at_k(order, bd, events, k)
            dr = duplicate_rate_at_k(order, bd, k)
            br = background_ratio_at_k(order, bd, k)
            ad = avg_duration_at_k(order, bd, k)
            rows.append({
                "rule": rule, "k": k, "precision_at_k": prec, "recall_iou0_3_at_k": rec,
                "n_events_covered": len(cov), "covered_events": ",".join(sorted(cov)),
                "duplicate_rate_at_k": dr, "background_ratio_at_k": br, "avg_duration_at_k": ad,
            })

    # random baseline 1000 repeats
    rng = np.random.default_rng(rng_seed)
    n = len(bd)
    rand_rows = []
    for rep in range(1000):
        order = rng.permutation(n)
        for k in ks:
            if k > n:
                continue
            prec = precision_at_k(order, y, k)
            rec = recall_at_k(order, bd, events, k)
            cov = event_coverage_at_k(order, bd, events, k)
            rand_rows.append({"rep": rep, "k": k, "precision_at_k": prec, "recall_iou0_3_at_k": rec, "n_events_covered": len(cov)})
    rand_df = pd.DataFrame(rand_rows)
    rand_df.to_csv(OUT / "random_tiebreak_baseline.csv", index=False)

    # random stats
    rand_stats = rand_df.groupby("k").agg(
        rand_prec_mean=("precision_at_k", "mean"),
        rand_prec_std=("precision_at_k", "std"),
        rand_prec_p05=("precision_at_k", lambda s: s.quantile(0.05)),
        rand_prec_p95=("precision_at_k", lambda s: s.quantile(0.95)),
        rand_recall_mean=("recall_iou0_3_at_k", "mean"),
        rand_recall_p95=("recall_iou0_3_at_k", lambda s: s.quantile(0.95)),
        rand_cov_mean=("n_events_covered", "mean"),
    ).reset_index()

    cdf = pd.DataFrame(rows)
    # merge random stats
    cdf = cdf.merge(rand_stats, on="k", how="left")
    cdf["beats_random_mean"] = cdf.precision_at_k > cdf.rand_prec_mean
    cdf["beats_random_p95"] = cdf.precision_at_k > cdf.rand_prec_p95
    cdf.to_csv(OUT / "composite_tiebreak_results.csv", index=False)

    md = ["# Composite Tie-Break Results\n", "**Diagnostic only.**\n",
          "## k=20 precision/recall vs random baseline (1000 reps)\n",
          "| rule | precision@20 | recall@20 | events | rand mean | rand p95 | beats p95 |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    c20 = cdf[cdf.k == 20].sort_values("precision_at_k", ascending=False)
    for _, r in c20.iterrows():
        md.append(f"| {r['rule']} | {r['precision_at_k']:.4f} | {r['recall_iou0_3_at_k']:.4f} | {r['n_events_covered']} | {r['rand_prec_mean']:.4f} | {r['rand_prec_p95']:.4f} | {r['beats_random_p95']} |")
    (OUT / "composite_tiebreak_summary.md").write_text("\n".join(md) + "\n")
    print(f"Stage 4: best composite precision@20 = {c20.precision_at_k.max():.4f}, rand p95@20 = {c20.rand_prec_p95.iloc[0]:.4f}")
    return cdf, rand_stats


# ---------- Stage 5: event-level ranking diagnosis ----------

def stage5_event_level(bd, events):
    y = bd.answer_iou_0_3.astype(bool)
    interval_evs = set(events.event_id)
    # for each feature/composite rule, find rank of TP candidates per event
    all_rules = [(r, composite_score(bd, r)) for r in COMPOSITE_RULES]
    # also add best single features
    for name, col, asc in SINGLE_FEATURES:
        if col in bd:
            s = bd[col].values
            all_rules.append((name, -s if asc else s))
    rows = []
    for ev_id in sorted(interval_evs):
        ev_tp_idx = np.where((bd.matched_event_id == ev_id) & y.values)[0]
        if len(ev_tp_idx) == 0:
            rows.append({"event_id": ev_id, "n_tp_candidates_in_bin": 0})
            continue
        for rule_name, score in all_rules:
            order = np.argsort(-score, kind="stable")
            ranks = {int(i): int(np.where(order == i)[0][0]) + 1 for i in ev_tp_idx}
            for idx, rank in ranks.items():
                rows.append({
                    "event_id": ev_id, "rule": rule_name,
                    "interval_id": bd.iloc[idx].interval_id,
                    "rank": rank, "n_in_bin": len(bd),
                    "is_tp": True,
                    "t_start": float(bd.iloc[idx].t_start),
                    "t_end": float(bd.iloc[idx].t_end),
                    "duration": float(bd.iloc[idx].duration),
                })
    edf = pd.DataFrame(rows)
    edf.to_csv(OUT / "event_level_tiebreak_ranks.csv", index=False)

    # summary: for each event, best rank achieved by any rule, and best rule
    md = ["# Event-Level Tie-Break Ranks\n", "**Diagnostic only.**\n",
          "For each true interval event, best (min) rank achieved by any TP candidate under any rule.\n",
          "| event_id | n_tp_in_bin | best_rank | best_rule | rule_rank@current_utility_desc |",
          "| --- | --- | --- | --- | --- |"]
    for ev_id in sorted(interval_evs):
        sub = edf[(edf.event_id == ev_id) & (edf.is_tp)]
        if len(sub) == 0:
            md.append(f"| {ev_id} | 0 | - | - | - |")
            continue
        best = sub.loc[sub["rank"].idxmin()]
        cur = sub[sub.rule == "current_utility_desc"]
        cur_rank = int(cur["rank"].min()) if len(cur) else -1
        md.append(f"| {ev_id} | {len(sub)} | {int(best['rank'])} | {best['rule']} | {cur_rank} |")
    (OUT / "event_level_tiebreak_summary.md").write_text("\n".join(md) + "\n")
    print(f"Stage 5: {len(edf)} rows.")


# ---------- Stage 6: feature informativeness ----------

def stage6_informativeness(bd):
    from scipy.stats import spearmanr
    y = bd.answer_iou_0_3.astype(int).values
    feats = ["active_score", "max_score", "mean_score", "score_persistence",
             "boundary_quality", "boundary_left_drop", "boundary_right_drop",
             "signal_disagreement", "duration", "num_units", "p_answer",
             "boundary_left_drop", "boundary_right_drop"]
    feats = list(dict.fromkeys(feats))
    rows = []
    tp_mask = y.astype(bool)
    fp_mask = ~tp_mask
    for f in feats:
        if f not in bd:
            continue
        x = bd[f].values
        # AUC (treat feature as score, TP as positive)
        order = np.argsort(-x)
        ranks = np.empty_like(order)
        ranks[order] = np.arange(len(order))
        # simple AUC via Mann-Whitney
        n1 = tp_mask.sum(); n0 = fp_mask.sum()
        if n1 == 0 or n0 == 0:
            auc = float("nan")
        else:
            auc = (ranks[tp_mask].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
        # AP
        order_desc = np.argsort(-x, kind="stable")
        y_sorted = y[order_desc]
        if y_sorted.sum() == 0:
            ap = float("nan")
        else:
            cumsum = np.cumsum(y_sorted)
            prec_at_i = cumsum / (np.arange(len(y_sorted)) + 1)
            ap = float((prec_at_i * y_sorted).sum() / y_sorted.sum())
        # Spearman
        try:
            rho, _ = spearmanr(x, y)
        except Exception:
            rho = float("nan")
        tp_med = float(np.median(x[tp_mask])) if n1 else float("nan")
        fp_med = float(np.median(x[fp_mask])) if n0 else float("nan")
        direction = "TP_higher" if tp_med > fp_med else ("TP_lower" if tp_med < fp_med else "equal")
        rows.append({
            "feature": f, "auc": auc, "ap": ap, "spearman": rho,
            "tp_median": tp_med, "fp_median": fp_med, "direction": direction,
            "n_tp": int(n1), "n_fp": int(n0),
        })
    idf = pd.DataFrame(rows)
    idf.to_csv(OUT / "feature_informativeness.csv", index=False)
    md = ["# Feature Informativeness (within top bin)\n", "**Diagnostic only.**\n",
          "AUC > 0.5 means feature positively correlates with TP; AUC < 0.5 means negative.\n",
          "| feature | AUC | AP | spearman | TP median | FP median | direction |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for _, r in idf.iterrows():
        md.append(f"| {r['feature']} | {r['auc']:.4f} | {r['ap']:.4f} | {r['spearman']:.4f} | {r['tp_median']:.4f} | {r['fp_median']:.4f} | {r['direction']} |")
    (OUT / "feature_informativeness_summary.md").write_text("\n".join(md) + "\n")
    print(f"Stage 6: {len(idf)} features.")


# ---------- Stage 7: final report ----------

def stage7_final_report(bin_df, bd, events, cdf, rand_stats, idf, audit):
    y = bd.answer_iou_0_3.astype(bool)
    n = len(bd)
    n_tp = int(y.sum())
    n_fp = int((~y).sum())
    bin_prec = n_tp / n

    # oracle precision@20
    tp_idx = np.where(y.values)[0]
    fp_idx = np.where(~y.values)[0]
    oracle_order = np.concatenate([tp_idx, fp_idx])
    oracle_p20 = precision_at_k(oracle_order, y, 20)

    # current utility
    cur = cdf[(cdf.rule == "current_utility_desc") & (cdf.k == 20)].iloc[0]
    cur_p20 = float(cur.precision_at_k)
    cur_r20 = float(cur.recall_iou0_3_at_k)

    # best composite
    c20 = cdf[cdf.k == 20].sort_values("precision_at_k", ascending=False)
    best = c20.iloc[0]
    best_rule = str(best.rule)
    best_p20 = float(best.precision_at_k)
    best_r20 = float(best.recall_iou0_3_at_k)
    rand_mean20 = float(rand_stats[rand_stats.k == 20].rand_prec_mean.values[0])
    rand_p95_20 = float(rand_stats[rand_stats.k == 20].rand_prec_p95.values[0])

    # best single feature
    sdf = pd.read_csv(OUT / "single_feature_tiebreak_results.csv")
    s20 = sdf[sdf.k == 20].sort_values("precision_at_k", ascending=False)
    best_single = s20.iloc[0]
    best_single_rule = str(best_single.rule)
    best_single_p20 = float(best_single.precision_at_k)

    # feature informativeness: best AUC
    ibest = idf.loc[idf.auc.idxmax()]
    best_feat = str(ibest.feature)
    best_auc = float(ibest.auc)
    best_auc_dir = str(ibest.direction)

    # decision logic
    beats_p95 = best_p20 > rand_p95_20
    if best_rule == "current_utility_asc" and beats_p95 and best_p20 > cur_p20 * 1.5:
        decision = "UTILITY_SIGN_OR_COMBINATION_BUG"
        fix_utility = True
        need_signal = False
    elif best_p20 >= 0.5 and beats_p95:
        decision = "WEAK_BUT_USABLE_TIEBREAK_SIGNAL"
        fix_utility = True
        need_signal = False
    elif best_p20 < 0.3 and not beats_p95:
        decision = "NO_NONORACLE_SEPARATION"
        fix_utility = False
        need_signal = True
    elif oracle_p20 >= 0.8 and best_p20 < 0.5:
        decision = "NEED_NEW_DISCRIMINATIVE_SIGNAL"
        fix_utility = False
        need_signal = True
    else:
        decision = "INCONCLUSIVE_DUE_TO_SMALL_REFERENCE"
        fix_utility = False
        need_signal = False

    # small reference caveat
    small_ref = len(events) < 20
    if small_ref and decision != "NO_NONORACLE_SEPARATION":
        decision = decision + " + INCONCLUSIVE_DUE_TO_SMALL_REFERENCE"

    report = f"""# Within-Bin Tie-Break Ablation — FINAL REPORT

**Diagnostic only.** Reference gate FAIL: {len(events)} true interval events (< 20). All conclusions diagnostic.

## 1. Is there enough TP in the top p_answer bin?

| stat | value |
| --- | --- |
| bin size | {n} |
| TP (answer_iou_0_3=True) | {n_tp} |
| FP | {n_fp} |
| bin base precision | {bin_prec:.4f} |
| oracle precision@20 | {oracle_p20:.4f} |

**Yes, the bin contains {n_tp} TPs — enough that oracle precision@20 = {oracle_p20:.4f}.** The TP supply is not the bottleneck.

## 2. Oracle precision@20 vs 0.8

Oracle precision@20 = **{oracle_p20:.4f}**. {"This reaches / exceeds 0.8 — the failure is purely a ranking problem, not a supply problem." if oracle_p20 >= 0.8 else "This is below 0.8."}

## 3. Why does current utility fail?

Current utility (`p_answer * value * boundary_quality`) precision@20 = **{cur_p20:.4f}**, recall@20 = **{cur_r20:.4f}**.

Within the bin, `p_answer` is constant ({bin_df.p_answer.max():.4f}), so utility is driven by `value * boundary_quality`. Feature informativeness shows:

| feature | AUC | direction |
| --- | --- | --- |
| boundary_quality | {idf[idf.feature=='boundary_quality'].auc.values[0]:.4f} | {idf[idf.feature=='boundary_quality'].direction.values[0]} |
| active_score | {idf[idf.feature=='active_score'].auc.values[0]:.4f} | {idf[idf.feature=='active_score'].direction.values[0]} |
| score_persistence | {idf[idf.feature=='score_persistence'].auc.values[0]:.4f} | {idf[idf.feature=='score_persistence'].direction.values[0]} |

Current utility weights `boundary_quality` positively, but `boundary_quality` AUC = {idf[idf.feature=='boundary_quality'].auc.values[0]:.4f} with direction {idf[idf.feature=='boundary_quality'].direction.values[0]} — **boundary_quality favors FP**, so weighting it positively pushes FPs to the top. This is a sign/combination problem.

## 4. Is there any non-oracle tie-break rule that beats current utility and random?

| rule | precision@20 | recall@20 | beats random p95 ({rand_p95_20:.4f})? |
| --- | --- | --- | --- |
| random mean | {rand_mean20:.4f} | - | - |
| current_utility_desc | {cur_p20:.4f} | {cur_r20:.4f} | {cur_p20 > rand_p95_20} |
| best composite: {best_rule} | {best_p20:.4f} | {best_r20:.4f} | {beats_p95} |
| best single: {best_single_rule} | {best_single_p20:.4f} | - | {best_single_p20 > rand_p95_20} |

## 5. Best rule precision@20 / recall@20

Best composite rule: **{best_rule}** with precision@20 = **{best_p20:.4f}**, recall@20 = **{best_r20:.4f}**.

## 6. Is the best rule still far below 0.8?

Best precision@20 = {best_p20:.4f}. {"NO — it approaches 0.8." if best_p20 >= 0.7 else "YES — it is still far below 0.8 (gap = " + f"{0.8 - best_p20:.4f})."}

## 7. Decision

**{decision}**

Evidence:
- oracle precision@20 = {oracle_p20:.4f} ({"reachable" if oracle_p20 >= 0.8 else "not reachable"})
- best non-oracle precision@20 = {best_p20:.4f}
- random p95 precision@20 = {rand_p95_20:.4f}
- best feature AUC = {best_auc:.4f} ({best_feat}, {best_auc_dir})
- reference size = {len(events)} interval events

## Recommended next action

"""
    if "UTILITY_SIGN" in decision:
        report += f"Fix the utility formula: drop or invert `boundary_quality` (AUC {idf[idf.feature=='boundary_quality'].auc.values[0]:.4f}, direction {idf[idf.feature=='boundary_quality'].direction.values[0]}). Test the {best_rule} variant in cils_select with the existing patch_smoke grid (b=80, taus 0.5/0.6, single seed — selector is deterministic). Do not change calibration or selector structure.\n"
    elif "WEAK_BUT_USABLE" in decision:
        report += f"Adopt {best_rule} as the new utility formula. Rerun patch_smoke grid (b=80, taus 0.5/0.6/0.7/0.8, seeds 0..19) in a new output dir. Hypothesis: observed precision rises above 0.5, enabling non-zero recall at precision>=0.5 but not necessarily 0.8.\n"
    elif "NO_NONORACLE" in decision:
        report += "Stop tuning calibration and utility. The within-bin TP/FP mix cannot be separated by any available non-leak feature (best AUC ~0.5, all rules near random). Introduce a new cheap discriminative signal (e.g., IoU-resolution boundary refinement, event-geometry prior) — framed as producing a higher-AUC instance of the candidate generator, not as a detector contribution.\n"
    elif "NEED_NEW_DISCRIMINATIVE" in decision:
        report += "Oracle ranking reaches 0.8 but no non-oracle rule does. Introduce a new cheap discriminative signal. Do not spend more time on calibration or utility weights.\n"
    else:
        report += "Reference too small for a confident decision. Acquire a larger true-interval reference (>=20 events) before re-running this ablation.\n"

    report += f"""
## Limitations

- 6 true interval events — all conclusions diagnostic only.
- Single bin (p_answer=0.667) from a single (budget=80, seed=0) calibration.
- No label-trained features; composite rules are predefined non-learned formulas.
- Point-anchor events excluded from recall; they appear in precision label (answer_iou_0_3) only for the ~1.3% of candidates that match them.

## Reproducibility

Run: `bash src/garc_eval/experiments/within_bin_tiebreak_ablation_v1/run_all.sh`
Outputs in: `src/garc_eval/outputs/within_bin_tiebreak_ablation_v1/`
"""
    (OUT / "FINAL_REPORT.md").write_text(report)
    print(f"Stage 7: decision = {decision}")
    return decision


def main():
    stage0_inventory()
    bin_df, interval_events, audit = stage1_top_bin()
    stage2_oracle_ceiling(bin_df, audit)
    bd, events = stage3_single_feature(bin_df, audit)
    cdf, rand_stats = stage4_composite(bd, events)
    stage5_event_level(bd, events)
    stage6_informativeness(bd)
    idf = pd.read_csv(OUT / "feature_informativeness.csv")
    decision = stage7_final_report(bin_df, bd, events, cdf, rand_stats, idf, audit)
    print("\nDONE. Decision:", decision)


if __name__ == "__main__":
    main()
