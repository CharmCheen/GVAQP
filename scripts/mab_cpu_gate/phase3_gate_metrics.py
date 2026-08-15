#!/usr/bin/env python3
"""Phase 3: MAB gate metrics from ACTION_VALUE_TABLE + fresh anytime curves.

Computes (per video x query cluster, pooled):
  - G_oracle: AUC(best adaptive oracle) - AUC(strongest fixed legal baseline)
  - opportunity density rho_0.01/0.02/0.05 + beneficial/harmful/indifferent
  - context predictability (LOVO: ridge + pairwise logistic) + headroom recovered
  - G_lookahead: AUC(depth-2 oracle) - AUC(myopic oracle)
  - reward alignment R0-R4 vs oracle terminal value
Preregistered thresholds from the DSH prompt are used verbatim.
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "outputs/mab_cpu_gate_v1"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge, LogisticRegression

from common import VIDEOS, QUERY_VULN, QUERY_DRIVER, BUDGETS, any_time_auc
from phase2_action_table import (Cluster, top_proxy_order, dyadic_order,
                                 coverage_first_order, visible_rewards,
                                 rollout)

def make_clusters():
    from phase2_action_table import GRID, PROXY_A, LABELS_BY_QUERY  # noqa
    cls = []
    for v in VIDEOS:
        for q in (QUERY_VULN, QUERY_DRIVER):
            cls.append(Cluster(v, q))
    return cls

# ------------------------------------------------------------ anytime curves

def oracle1_policy(cl, queried, outcomes):
    """Myopic oracle: legal action maximizing one-step reference-EventF1 delta."""
    base = cl.f1([c for c in queried if outcomes.get(c) == "relevant"])
    best, best_d = None, -1e9
    for c in cl.unit_ids:
        if c in queried:
            continue
        o = cl.label(c)
        pos1 = [x for x in queried if outcomes.get(x) == "relevant"]
        if o == "relevant":
            pos1.append(c)
        d = cl.f1(pos1) - base
        if d > best_d:
            best, best_d = c, d
    return best

def oracle2_policy(cl, queried, outcomes):
    """Depth-2 oracle (full-information expectation): max E_Y[Delta1 + max_a2 Delta1].
    Outer candidates restricted to top-100 legal actions by one-step Delta1
    (K=100 recorded); inner max over top-50 proxy candidates (K=50 recorded)."""
    base = cl.f1([c for c in queried if outcomes.get(c) == "relevant"])
    cand = [c for c in cl.unit_ids if c not in queried]
    inner_cand = sorted(cand, key=lambda c: (-cl.scores[c], c))[:50]
    # one-step deltas for all legal actions
    d1 = {}
    for c in cand:
        o = cl.label(c)
        pos1 = [x for x in queried if outcomes.get(x) == "relevant"]
        if o == "relevant":
            pos1.append(c)
        d1[c] = cl.f1(pos1) - base
    outer = sorted(cand, key=lambda c: -d1[c])[:100]
    best, best_v = None, -1e9
    for c in outer:
        o = cl.label(c)
        pos1 = [x for x in queried if outcomes.get(x) == "relevant"]
        if o == "relevant":
            pos1.append(c)
        f1_h1 = base + d1[c]
        best_next = -1e9
        for a2 in inner_cand:
            if a2 == c or a2 in queried:
                continue
            o2 = cl.label(a2)
            pos2 = pos1 + ([a2] if o2 == "relevant" else [])
            d = cl.f1(pos2) - f1_h1
            if d > best_next:
                best_next = d
        v = d1[c] + best_next
        if v > best_v:
            best, best_v = c, v
    return best

def legal_next(cl, queried, outcomes, policy):
    legal = [c for c in cl.unit_ids if c not in queried]
    if not legal:
        return None
    if policy == "top_proxy":
        return min(legal, key=lambda c: (-cl.scores[c], c))
    if policy == "uniform":
        return dyadic_order(legal, None)[0]
    if policy == "coverage_first":
        return coverage_first_order(cl, None, 1)[0]
    if policy == "relation_greedy":
        cand = sorted(legal, key=lambda c: (-cl.scores[c], c))[:50]
        return max(cand, key=lambda c: visible_rewards(cl, queried, outcomes, c)["visible_reward_r4"])
    if policy == "oracle1":
        return oracle1_policy(cl, queried, outcomes)
    if policy == "oracle2":
        return oracle2_policy(cl, queried, outcomes)
    raise ValueError(policy)

def anytime_curve(cl, policy, budgets=BUDGETS):
    """EventF1 at each budget. Nested deterministic policies (top_proxy,
    uniform, coverage_first) use prefix slices of one precomputed order;
    relation_greedy and oracles are simulated stepwise from scratch per budget."""
    if policy in ("top_proxy", "uniform", "coverage_first"):
        maxb = max(budgets)
        if policy == "top_proxy":
            order = top_proxy_order(cl)
        elif policy == "uniform":
            order = dyadic_order(cl.unit_ids, None)
        else:
            order = coverage_first_order(cl, None, maxb)
        out = []
        for b in budgets:
            q = order[:b]
            o = {c: cl.label(c) for c in q}
            out.append((b, cl.f1([c for c in q if o.get(c) == "relevant"])))
        return out
    out = []
    for b in budgets:
        q, o = [], {}
        while len(q) < b:
            a = legal_next(cl, q, o, policy)
            if a is None:
                break
            q.append(a); o[a] = cl.label(a)
        out.append((b, cl.f1([c for c in q if o.get(c) == "relevant"])))
    return out

# ------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    df = pd.read_parquet(GATE / "ACTION_VALUE_TABLE.parquet")
    clusters = make_clusters()
    cl_by_key = {(c.video, c.query): c for c in clusters}
    budgets_use = (5, 10, 20) if args.quick else BUDGETS

    # ---- 1. anytime curves + G_oracle / G_lookahead (Q_VULNERABLE primary) ----
    curves = {}
    policies = ["top_proxy", "uniform", "coverage_first", "relation_greedy", "oracle1", "oracle2"]
    for v in VIDEOS:
        cl = cl_by_key[(v, QUERY_VULN)]
        for pol in policies:
            c = anytime_curve(cl, pol, budgets_use)
            curves[(v, QUERY_VULN, pol)] = c
            print(f"curve {v} {pol}: {[round(x[1],3) for x in c]}", flush=True)

    gate = {}
    g_oracle_rows, g_look_rows = [], []
    for v in VIDEOS:
        cl = cl_by_key[(v, QUERY_VULN)]
        auc = {pol: any_time_auc(curves[(v, QUERY_VULN, pol)]) for pol in policies}
        legal = {pol: auc[pol] for pol in ("top_proxy", "uniform", "coverage_first", "relation_greedy")}
        best_fixed = max(legal, key=legal.get)
        oracle_best = max(auc["oracle1"], auc["oracle2"])
        g_oracle = oracle_best - auc[best_fixed]
        g_look = auc["oracle2"] - auc["oracle1"]
        gate[f"{v}_Q_VULN"] = {"auc": {k: round(vv, 5) for k, vv in auc.items()},
                               "best_fixed": best_fixed, "g_oracle": round(g_oracle, 5),
                               "g_lookahead": round(g_look, 5)}
        g_oracle_rows.append({"cluster": f"{v}_Q_VULN", "best_fixed_auc": round(auc[best_fixed], 5),
                              "oracle1_auc": round(auc["oracle1"], 5), "oracle2_auc": round(auc["oracle2"], 5),
                              "g_oracle": round(g_oracle, 5), "g_lookahead": round(g_look, 5)})

    # ---- 2. opportunity density from terminal deltas ----
    term = df.dropna(subset=["oracle_terminal_delta_topproxy"]).copy()
    rho_rows = []
    for (v, q), g in term.groupby(["video_id", "query_id"]):
        per_state = []
        for sid, h in g.groupby("state_id"):
            base_row = h.loc[h["visible_proxy_rank"].idxmin()]
            per_state.append({"state_id": sid, "best": h["oracle_terminal_delta_topproxy"].max(),
                              "base": base_row["oracle_terminal_delta_topproxy"]})
        per_state = pd.DataFrame(per_state)
        per_state["gap"] = per_state["best"] - per_state["base"]
        for eps in (0.01, 0.02, 0.05):
            rho_rows.append({"cluster": f"{v}_{q}", "eps": eps,
                             "rho": float((per_state["gap"] > eps).mean()),
                             "n_states": len(per_state)})
        b = int((per_state["gap"] > 0.02).sum())
        # harmful = ACTION-level rate: fraction of sampled actions with
        # terminal delta < -0.02 (choosing them would materially hurt);
        # state-level gap cannot be negative by construction (baseline action
        # is in the sampled set, so max >= baseline).
        harm = float((g["oracle_terminal_delta_topproxy"] < -0.02).mean())
        rho_rows.append({"cluster": f"{v}_{q}", "eps": "counts_0.02",
                         "rho": float("nan"), "n_states": len(per_state),
                         "beneficial": b, "harmful": harm,
                         "indifferent": len(per_state) - b})

    # pooled (primary clusters only)
    prim = term[term["query_id"] == QUERY_VULN]
    _ps = []
    for sid, h in prim.groupby("state_id"):
        base_row = h.loc[h["visible_proxy_rank"].idxmin()]
        _ps.append({"state_id": sid, "best": h["oracle_terminal_delta_topproxy"].max(),
                    "base": base_row["oracle_terminal_delta_topproxy"]})
    ps = pd.DataFrame(_ps)
    ps["gap"] = ps["best"] - ps["base"]
    rho_pooled = {"rho_0.01": float((ps["gap"] > 0.01).mean()),
                  "rho_0.02": float((ps["gap"] > 0.02).mean()),
                  "rho_0.05": float((ps["gap"] > 0.05).mean())}
    rho_pooled.update({"beneficial": int((ps["gap"] > 0.02).sum()),
                       "harmful_action_rate": float((prim["oracle_terminal_delta_topproxy"] < -0.02).mean()),
                       "indifferent": int((ps["gap"] <= 0.02).sum()),
                       "n_states": len(ps)})

    # ---- 3. context predictability (LOVO over videos; primary query) ----
    # Baseline action = top-proxy action at each state; its terminal delta is
    # 0 BY CONSTRUCTION (continuing from H with top_proxy picks it first), so
    # HeadroomRecovered = mean(model-selected gain)/mean(oracle-best gain).
    prim = df[df["query_id"] == QUERY_VULN].dropna(subset=["oracle_terminal_delta_topproxy"]).copy()
    feat_cols = ["visible_proxy_score", "visible_proxy_rank", "visible_distance_to_positive",
                 "visible_distance_to_negative", "visible_new_component_gain", "visible_redundancy",
                 "visible_merge_risk", "visible_uncovered_region_change", "remaining_budget_fraction",
                 "region_coverage_fraction", "current_component_count"]
    prim = prim.replace([np.inf, -np.inf], np.nan)
    prim[feat_cols] = prim[feat_cols].fillna(prim[feat_cols].median())
    X = prim[feat_cols].to_numpy(float)
    y = prim["oracle_terminal_delta_topproxy"].to_numpy(float)
    clusters_keys = sorted(prim["video_id"].unique())
    lovo_rows = []
    for held in clusters_keys:
        tr = prim["video_id"] != held
        te = prim["video_id"] == held
        if tr.sum() == 0 or te.sum() == 0:
            continue
        te_pos = np.flatnonzero(te)
        local = prim.iloc[te_pos].reset_index(drop=True)
        m = Ridge(alpha=1.0).fit(X[tr], y[tr])
        pred = m.predict(X[te_pos])
        obs = y[te_pos]
        sp = stats.spearmanr(pred, obs).statistic if len(np.unique(pred)) > 1 and len(np.unique(obs)) > 1 else float("nan")
        # pairwise ranking accuracy within states
        accs = []
        for sid, g in local.groupby("state_id"):
            if len(g) < 2:
                continue
            pr, ob = pred[g.index.to_numpy()], obs[g.index.to_numpy()]
            pairs = 0; corr = 0
            for i in range(len(pr)):
                for j in range(i + 1, len(pr)):
                    pairs += 1
                    corr += int((pr[i] - pr[j]) * (ob[i] - ob[j]) > 0)
            if pairs:
                accs.append(corr / pairs)
        # selected-action regret vs oracle-best within states
        reg = []
        for sid, g in local.groupby("state_id"):
            pr, ob = pred[g.index.to_numpy()], obs[g.index.to_numpy()]
            if len(pr) < 1:
                continue
            reg.append(ob.max() - ob[np.argmax(pr)])
        lovo_rows.append({"heldout_video": held, "n_train_states": tr.sum(), "n_test_rows": te.sum(),
                          "spearman": round(sp, 4) if sp == sp else None,
                          "pairwise_accuracy": round(float(np.mean(accs)), 4) if accs else None,
                          "mean_selected_regret": round(float(np.mean(reg)), 5) if reg else None,
                          "oracle_gain_mean": round(float(np.mean([g["oracle_terminal_delta_topproxy"].max() for _, g in local.groupby("state_id")])), 5)})
    # pooled headroom recovered: mean(model-selected gain)/mean(oracle-best gain)
    gain_rows = []
    for sid, g in prim.groupby("state_id"):
        ob = g["oracle_terminal_delta_topproxy"].to_numpy()
        gain_rows.append({"state": sid, "oracle_gain": ob.max(), "base_gain": ob.min()})
    gr = pd.DataFrame(gain_rows)
    # fit ridge on all-but-holdout per video, evaluate pooled selected gain via LOVO preds
    pooled_pred = np.zeros(len(prim))
    for held in clusters_keys:
        tr = prim["video_id"] != held
        te = prim["video_id"] == held
        m = Ridge(alpha=1.0).fit(X[tr], y[tr])
        pooled_pred[te] = m.predict(X[te])
    sel_gain = []
    for sid, g in prim.groupby("state_id"):
        ob = g["oracle_terminal_delta_topproxy"].to_numpy()
        pos = prim.index.get_indexer(g.index)
        pr = pooled_pred[pos]
        sel_gain.append(ob[np.argmax(pr)])
    oracle_gain_mean = float(gr["oracle_gain"].mean())
    base_gain_mean = 0.0  # top-proxy baseline action gain is 0 by construction
    model_gain_mean = float(np.mean(sel_gain))
    headroom_recovered = model_gain_mean / oracle_gain_mean if oracle_gain_mean > 0 else float("nan")

    # ---- 4. reward alignment (primary query) ----
    align_rows = []
    for (v, q), g in prim.groupby(["video_id", "query_id"]):
        row = {"cluster": f"{v}_{q}"}
        for rk in ("r0", "r1", "r2", "r3", "r4"):
            col = f"visible_reward_{rk}"
            row[f"spearman_{rk}"] = round(stats.spearmanr(g[col], g["oracle_terminal_delta_topproxy"]).statistic, 4)
            top_acc = []
            harmful = []
            for sid, h in g.groupby("state_id"):
                if len(h) < 2:
                    continue
                top_acc.append(int(h.loc[h[col].idxmax(), "oracle_terminal_delta_topproxy"] == h["oracle_terminal_delta_topproxy"].max()))
                if h.loc[h[col].idxmax(), "oracle_terminal_delta_topproxy"] < -0.02:
                    harmful.append(1)
            row[f"top_action_acc_{rk}"] = round(float(np.mean(top_acc)), 4) if top_acc else None
            row[f"harmful_dev_rate_{rk}"] = round(float(np.mean(harmful)), 4) if harmful else None
        align_rows.append(row)

    # ---- 5. preregistered gate routing ----
    g_oracle_med = float(np.median([r["g_oracle"] for r in g_oracle_rows]))
    g_look_med = float(np.median([r["g_lookahead"] for r in g_oracle_rows]))
    rho_02 = rho_pooled["rho_0.02"]
    if g_oracle_med < 0.03 or rho_02 < 0.15:
        route_action = "NO_GO_NO_ACTION_HEADROOM"
    elif g_oracle_med >= 0.05 and rho_02 >= 0.20:
        route_action = "ACTION_SPACE_GO"
    else:
        route_action = "INCONCLUSIVE"
    if (headroom_recovered == headroom_recovered and headroom_recovered < 0.20) or rho_02 < 0.15:
        route_context = "GO_RELATION_GREEDY_ONLY"
    elif headroom_recovered == headroom_recovered and headroom_recovered >= 0.40:
        route_context = "CONTEXTUAL_MODEL_VIABLE"
    else:
        route_context = "INCONCLUSIVE_CONTEXT"
    if g_look_med <= 0.02:
        route_look = "MYOPIC_CONTEXTUAL_MAB_IS_ADEQUATE"
    elif g_look_med >= 0.03:
        route_look = "GO_NONMYOPIC_ACTIVE_SEARCH"
    else:
        route_look = "INCONCLUSIVE_LOOKAHEAD"

    result = {
        "g_oracle_median": round(g_oracle_med, 5),
        "g_lookahead_median": round(g_look_med, 5),
        "rho": rho_pooled,
        "headroom_recovered": round(headroom_recovered, 4) if headroom_recovered == headroom_recovered else None,
        "model_selected_gain_mean": round(model_gain_mean, 5),
        "oracle_gain_mean": round(oracle_gain_mean, 5),
        "baseline_gain_mean": round(base_gain_mean, 5),
        "routes": {"action_space": route_action, "context": route_context, "lookahead": route_look},
        "per_cluster": gate,
        "anytime_auc_rows": g_oracle_rows,
        "rho_rows": rho_rows,
        "lovo_rows": lovo_rows,
        "reward_alignment_rows": align_rows,
    }

    def _json_default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(o)

    (GATE / "MAB_GATE_METRICS.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, default=_json_default))
    pd.DataFrame(g_oracle_rows).to_csv(GATE / "MAB_GATE_METRICS.csv", index=False)
    print(json.dumps({k: result[k] for k in ("g_oracle_median", "g_lookahead_median", "rho", "headroom_recovered", "routes")}, indent=1))

if __name__ == "__main__":
    main()
