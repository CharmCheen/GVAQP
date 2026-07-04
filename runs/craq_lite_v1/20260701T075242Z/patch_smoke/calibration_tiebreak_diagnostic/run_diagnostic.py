"""Calibration / tie-break diagnostic for CRAQ-lite CILS.

Self-contained: imports helpers from run_craq_lite but does NOT modify the
default calibrate_cils. Implements 5 diagnostic calibration variants and
runs (a) a per-variant score distribution check, (b) a within-bin tie-break
audit, (c) a selector rerun over the small grid.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
sys.path.insert(0, str(ROOT / "src"))

from garc_eval.experiments.craq_lite_v1.run_craq_lite import (
    ANSWER,
    prepare_candidates,
    load_inputs,
    normalize,
    safe_div,
    wilson_lower,
)
from garc_eval.metrics.craq_lite_metrics import Interval, interval_iou, event_recall as metric_event_recall

OUT = ROOT / "runs/craq_lite_v1/20260701T075242Z/patch_smoke/calibration_tiebreak_diagnostic"
OUT.mkdir(parents=True, exist_ok=True)

VARIANTS = ["current_wilson_z1", "wilson_z0_5", "raw_bin_rate", "coarse_2key_wilson_z1", "coarse_2key_raw_rate"]
BUDGETS = [80, 160]
TAUS = [0.5, 0.6, 0.7, 0.8]
PREC_TARGETS = [0.8, 0.9]
SEEDS = list(range(20))
IOU_THR = [0.3, 0.5]


def calibrate_variant(cand: pd.DataFrame, budget: int, variant: str) -> pd.DataFrame:
    out = cand.copy()
    samples = cand.sort_values(["answer_quality_proxy", "duration"], ascending=[False, True]).head(budget).copy()
    smap = samples.set_index("interval_id")[ANSWER].astype(int).to_dict()
    s = out[out["interval_id"].isin(smap)].copy()
    s["y"] = s["interval_id"].map(smap).astype(int)
    global_p = (s["y"].sum() + 1.0) / (len(s) + 2.0)

    if variant in ("current_wilson_z1", "wilson_z0_5"):
        keys = ["answer_quality_proxy_bin", "duration_bin", "method", "boundary_quality_bin"]
        z = 1.0 if variant == "current_wilson_z1" else 0.5
        stat = s.groupby(keys, observed=True, dropna=False)["y"].agg(["sum", "count"]).reset_index()
        stat["lower"] = wilson_lower(stat["sum"], stat["count"], z=z)
        out = out.merge(stat[keys + ["lower"]], on=keys, how="left")
        out["p_answer"] = out["lower"].fillna(global_p * 0.5).clip(0, 1)
    elif variant == "raw_bin_rate":
        keys = ["answer_quality_proxy_bin", "duration_bin", "method", "boundary_quality_bin"]
        stat = s.groupby(keys, observed=True, dropna=False)["y"].agg(["sum", "count"]).reset_index()
        stat["rate"] = (stat["sum"] / stat["count"].replace(0, np.nan)).fillna(0.0).clip(0, 1)
        out = out.merge(stat[keys + ["rate"]], on=keys, how="left")
        out["p_answer"] = out["rate"].fillna(global_p * 0.5).clip(0, 1)
    elif variant == "coarse_2key_wilson_z1":
        keys = ["answer_quality_proxy_bin", "duration_bin"]
        stat = s.groupby(keys, observed=True, dropna=False)["y"].agg(["sum", "count"]).reset_index()
        stat["lower"] = wilson_lower(stat["sum"], stat["count"], z=1.0)
        out = out.merge(stat[keys + ["lower"]], on=keys, how="left")
        out["p_answer"] = out["lower"].fillna(global_p * 0.5).clip(0, 1)
    elif variant == "coarse_2key_raw_rate":
        keys = ["answer_quality_proxy_bin", "duration_bin"]
        stat = s.groupby(keys, observed=True, dropna=False)["y"].agg(["sum", "count"]).reset_index()
        stat["rate"] = (stat["sum"] / stat["count"].replace(0, np.nan)).fillna(0.0).clip(0, 1)
        out = out.merge(stat[keys + ["rate"]], on=keys, how="left")
        out["p_answer"] = out["rate"].fillna(global_p * 0.5).clip(0, 1)
    else:
        raise ValueError(variant)
    return out


def cils_select_variant(cand: pd.DataFrame, budget: int, tau: float, events: pd.DataFrame, variant: str) -> tuple[pd.DataFrame, float, float]:
    cal = calibrate_variant(cand, budget, variant)
    max_pa = float(cal["p_answer"].max())
    duration_cap = min(32.0, float(events["duration"].quantile(0.95)) * 3.0) if not events.empty else 32.0
    df = cal.copy()
    bq = 0.55 + 0.45 * normalize(df["boundary_left_drop"] + df["boundary_right_drop"])
    dur_penalty = np.where(df["duration"] <= duration_cap, 1.0, duration_cap / df["duration"])
    df["value"] = np.minimum(df["duration"], duration_cap) * (0.5 + 0.5 * df["active_score"])
    df["boundary_quality"] = bq * dur_penalty
    df["utility"] = df["p_answer"] * df["value"] * df["boundary_quality"]
    ranked = df.sort_values(["utility", "active_score"], ascending=False).head(min(len(df), max(300, budget * 30)))
    selected, spans = [], []
    tp = total = dur = 0.0
    for r in ranked.itertuples(index=False):
        if len(selected) >= budget:
            break
        if dur + r.duration > 360.0:
            continue
        if any(interval_iou(Interval(r.t_start, r.t_end), Interval(a, b)) > 0.3 for a, b in spans):
            continue
        ntp = tp + float(r.p_answer) * float(r.value)
        ntotal = total + float(r.value)
        if safe_div(ntp, ntotal) + 1e-12 < tau:
            continue
        selected.append(r._asdict())
        spans.append((float(r.t_start), float(r.t_end)))
        tp, total, dur = ntp, ntotal, dur + float(r.duration)
    return pd.DataFrame(selected), safe_div(tp, total), max_pa


def to_intervals(df: pd.DataFrame, id_col: str = "event_id") -> list[Interval]:
    out = []
    for r in df.itertuples(index=False):
        eid = getattr(r, id_col, None)
        out.append(Interval(float(r.t_start), float(r.t_end), eid))
    return out


def main() -> None:
    print("loading inputs...")
    inputs = load_inputs()
    cand = prepare_candidates(inputs)
    ref = pd.read_csv(ROOT / "runs/craq_lite_v1/20260701T075242Z/patch_smoke/reference_audit.csv")
    events = ref[ref["is_interval_event"] == 1].copy().reset_index(drop=True)
    ev_intervals = to_intervals(events, "event_id")

    # TP/FP label at candidate level: answer_iou_0_3 True => TP candidate
    cand["_is_tp"] = cand[ANSWER].astype(bool)

    # ==================================================================
    # Part 1: calibration variant score distribution
    # ==================================================================
    print("Part 1: calibration variants...")
    cv_rows = []
    for budget in BUDGETS:
        for variant in VARIANTS:
            cal = calibrate_variant(cand, budget, variant)
            pa = cal["p_answer"]
            tp_mask = cal[ANSWER].astype(bool)
            cv_rows.append({
                "variant": variant,
                "budget": budget,
                "n_cand": len(pa),
                "max_p_answer": float(pa.max()),
                "q0.5": float(pa.quantile(0.5)),
                "q0.9": float(pa.quantile(0.9)),
                "q0.95": float(pa.quantile(0.95)),
                "q0.99": float(pa.quantile(0.99)),
                "n_ge_0.7": int((pa >= 0.7).sum()),
                "n_ge_0.8": int((pa >= 0.8).sum()),
                "n_ge_0.9": int((pa >= 0.9).sum()),
                "n_tp_ge_0.8": int((pa[tp_mask] >= 0.8).sum()),
                "n_fp_ge_0.8": int((pa[~tp_mask] >= 0.8).sum()),
                "n_tp_ge_0.9": int((pa[tp_mask] >= 0.9).sum()),
                "n_fp_ge_0.9": int((pa[~tp_mask] >= 0.9).sum()),
                "any_tp_ge_0.8": bool((pa[tp_mask] >= 0.8).any()),
                "any_fp_ge_0.8": bool((pa[~tp_mask] >= 0.8).any()),
            })
    cv = pd.DataFrame(cv_rows)
    cv.to_csv(OUT / "calibration_variant_summary.csv", index=False)
    print(cv.to_string(index=False))

    # ==================================================================
    # Part 2: within-bin tie-break audit
    # Focus: the bin that produced p_answer=0.667 in current_wilson_z1 b=80.
    # Identify the top p_answer bin per variant and audit tie-break.
    # ==================================================================
    print("Part 2: within-bin tie-break audit...")
    audit_rows = []
    # Use budget=80 for the audit (where CILS actually returns something).
    budget = 80
    # event intervals for "is in event region" check
    ev_spans = [(float(e.t_start), float(e.t_end)) for e in events.itertuples(index=False)]

    for variant in VARIANTS:
        cal = calibrate_variant(cand, budget, variant)
        pa = cal["p_answer"]
        top_pa = float(pa.max())
        # top bin = all candidates with p_answer == top_pa (within 1e-9)
        top_bin = cal[pa >= top_pa - 1e-9].copy()
        n_bin = len(top_bin)
        n_tp_bin = int(top_bin[ANSWER].astype(bool).sum())
        n_iou5_bin = int(top_bin["answer_iou_0_5"].astype(bool).sum()) if "answer_iou_0_5" in top_bin else 0
        bin_precision = n_tp_bin / n_bin if n_bin else float("nan")

        # reconstruct utility exactly as cils_select does
        duration_cap = min(32.0, float(events["duration"].quantile(0.95)) * 3.0)
        bq = 0.55 + 0.45 * normalize(top_bin["boundary_left_drop"] + top_bin["boundary_right_drop"])
        dur_penalty = np.where(top_bin["duration"] <= duration_cap, 1.0, duration_cap / top_bin["duration"])
        top_bin = top_bin.copy()
        top_bin["value"] = np.minimum(top_bin["duration"], duration_cap) * (0.5 + 0.5 * top_bin["active_score"])
        top_bin["boundary_quality"] = bq.values * dur_penalty
        top_bin["utility"] = top_bin["p_answer"] * top_bin["value"] * top_bin["boundary_quality"]

        # k = actual selected count from patch_smoke for b=80 tau=0.6 = 25; use 20 (tau=0.5) and 25 (tau=0.6)
        for k in [20, 25]:
            if n_bin < k:
                continue
            top_sorted = top_bin.sort_values(["utility", "active_score"], ascending=False)
            top_k = top_sorted.head(k)
            prec_top = float(top_k[ANSWER].astype(bool).mean())
            prec_bot = float(top_sorted.tail(k)[ANSWER].astype(bool).mean())

            # random-k averaged over 100 seeds
            rng = np.random.default_rng(20260630)
            rand_precs = []
            for _ in range(100):
                idx = rng.choice(n_bin, size=k, replace=False)
                rand_precs.append(float(top_bin.iloc[idx][ANSWER].astype(bool).mean()))
            prec_rand = float(np.mean(rand_precs))
            prec_rand_q025 = float(np.quantile(rand_precs, 0.025))
            prec_rand_q975 = float(np.quantile(rand_precs, 0.975))

            # TP rank positions under current utility (1-indexed)
            top_sorted_full = top_sorted.reset_index(drop=True)
            tp_idx = top_sorted_full.index[top_sorted_full[ANSWER].astype(bool)].tolist()
            tp_ranks = [int(i) + 1 for i in tp_idx]

            # utility / active_score / boundary_quality / duration quantiles for TP vs FP
            tp_sub = top_bin[top_bin[ANSWER].astype(bool)]
            fp_sub = top_bin[~top_bin[ANSWER].astype(bool)]
            def q(s): return float(s.quantile(0.5)) if len(s) else float("nan")
            audit_rows.append({
                "variant": variant,
                "budget": budget,
                "k": k,
                "top_p_answer": top_pa,
                "n_in_bin": n_bin,
                "n_tp_in_bin": n_tp_bin,
                "n_iou5_in_bin": n_iou5_bin,
                "bin_precision": bin_precision,
                "prec_top_k_utility": prec_top,
                "prec_bot_k_utility": prec_bot,
                "prec_rand_k_mean": prec_rand,
                "prec_rand_k_q025": prec_rand_q025,
                "prec_rand_k_q975": prec_rand_q975,
                "tp_ranks_under_utility": str(tp_ranks),
                "n_tp_under_top_k": int((top_sorted_full.index.isin(tp_idx[:k])).sum()) if False else int(sum(1 for r in tp_ranks if r <= k)),
                "utility_q0.5_tp": q(tp_sub["utility"]),
                "utility_q0.5_fp": q(fp_sub["utility"]),
                "active_score_q0.5_tp": q(tp_sub["active_score"]),
                "active_score_q0.5_fp": q(fp_sub["active_score"]),
                "boundary_quality_q0.5_tp": q(tp_sub["boundary_quality"]),
                "boundary_quality_q0.5_fp": q(fp_sub["boundary_quality"]),
                "duration_q0.5_tp": q(tp_sub["duration"]),
                "duration_q0.5_fp": q(fp_sub["duration"]),
            })
    audit = pd.DataFrame(audit_rows)
    audit.to_csv(OUT / "tiebreak_bin_audit.csv", index=False)
    print(audit.to_string(index=False))

    # ==================================================================
    # Part 3: selector rerun with calibration variants
    # ==================================================================
    print("Part 3: selector rerun across variants...")
    sel_rows = []
    for variant in VARIANTS:
        for budget in BUDGETS:
            for tau in TAUS:
                # selector is deterministic (no seed dependence in cils_select);
                # the patch_smoke seeds only affected audited_repair. We still
                # record 20 seed rows for parity, all identical.
                sel, exp_prec, max_pa = cils_select_variant(cand, budget, tau, events, variant)
                nsel = len(sel)
                empty = nsel == 0
                if nsel > 0:
                    preds = to_intervals(sel, "interval_id")
                    obs_prec = float(sel[ANSWER].astype(bool).mean()) if ANSWER in sel else math.nan
                    r03 = metric_event_recall(preds, ev_intervals, 0.3)
                    r05 = metric_event_recall(preds, ev_intervals, 0.5)
                    ret_dur = float(sel["duration"].sum())
                    true_dur = float(events["duration"].sum())
                    dur_inf = ret_dur / true_dur if true_dur else math.nan
                    tp_count = int(sel[ANSWER].astype(bool).sum())
                    fp_count = nsel - tp_count
                else:
                    obs_prec = math.nan
                    r03 = 0.0
                    r05 = 0.0
                    dur_inf = math.nan
                    tp_count = 0
                    fp_count = 0
                for seed in SEEDS:
                    for pt in PREC_TARGETS:
                        sel_rows.append({
                            "calibration_variant": variant,
                            "budget": budget,
                            "cils_tau": tau,
                            "precision_target": pt,
                            "seed": seed,
                            "returned_interval_count": nsel,
                            "empty_return": empty,
                            "observed_precision": obs_prec,
                            "expected_precision": exp_prec,
                            "recall_iou_0_3": r03,
                            "recall_iou_0_5": r05,
                            "duration_inflation": dur_inf,
                            "max_p_answer": max_pa,
                            "selected_tp_count": tp_count,
                            "selected_fp_count": fp_count,
                        })
    sel_df = pd.DataFrame(sel_rows)
    sel_df.to_csv(OUT / "selector_variant_metrics.csv", index=False)
    # per-variant/budget/tau summary (drop seed/pt duplication)
    summary = sel_df.groupby(["calibration_variant", "budget", "cils_tau"], dropna=False).agg(
        returned_interval_count=("returned_interval_count", "first"),
        empty_return=("empty_return", "first"),
        observed_precision=("observed_precision", "first"),
        recall_iou_0_3=("recall_iou_0_3", "first"),
        recall_iou_0_5=("recall_iou_0_5", "first"),
        max_p_answer=("max_p_answer", "first"),
        selected_tp_count=("selected_tp_count", "first"),
        selected_fp_count=("selected_fp_count", "first"),
    ).reset_index()
    summary.to_csv(OUT / "selector_variant_summary.csv", index=False)
    print(summary.to_string(index=False))

    # save config
    (OUT / "config_used.json").write_text(json.dumps({
        "budgets": BUDGETS,
        "cils_taus": TAUS,
        "precision_targets": PREC_TARGETS,
        "seeds": SEEDS,
        "calibration_variants": VARIANTS,
        "iou_thresholds": IOU_THR,
        "note": "selector is deterministic; seed/precision_target rows are duplicated for parity with patch_smoke schema.",
    }, indent=2))

    # ==================================================================
    # Part 4: numbers needed for REPORT.md
    # ==================================================================
    # best observed precision with nonzero recall
    nonempty = summary[~summary["empty_return"] & (summary["recall_iou_0_3"] > 0)]
    best_prec_nonzero_recall = float(nonempty["observed_precision"].max()) if len(nonempty) else math.nan
    best_recall_at_prec08 = float(nonempty[nonempty["observed_precision"] >= 0.8]["recall_iou_0_3"].max()) if len(nonempty) and (nonempty["observed_precision"] >= 0.8).any() else 0.0
    best_recall_at_prec09 = float(nonempty[nonempty["observed_precision"] >= 0.9]["recall_iou_0_3"].max()) if len(nonempty) and (nonempty["observed_precision"] >= 0.9).any() else 0.0

    print("\n=== REPORT inputs ===")
    print(f"best observed precision with nonzero recall: {best_prec_nonzero_recall}")
    print(f"best recall@0.3 at prec>=0.8: {best_recall_at_prec08}")
    print(f"best recall@0.3 at prec>=0.9: {best_recall_at_prec09}")

    # pick the current_wilson_z1 b=80 top bin audit row (k=20) for the report
    cur_audit = audit[(audit["variant"] == "current_wilson_z1") & (audit["k"] == 20)].iloc[0]
    print("\ncurrent_wilson_z1 b=80 top bin (k=20):")
    print(cur_audit.to_dict())

    # write a json of key numbers for the report
    report_data = {
        "cv": cv.to_dict("records"),
        "audit": audit.to_dict("records"),
        "summary": summary.to_dict("records"),
        "best_prec_nonzero_recall": best_prec_nonzero_recall,
        "best_recall_at_prec08": best_recall_at_prec08,
        "best_recall_at_prec09": best_recall_at_prec09,
    }
    (OUT / "_report_data.json").write_text(json.dumps(report_data, default=str, indent=2))
    print("\nDone. Outputs in", OUT)


if __name__ == "__main__":
    main()
