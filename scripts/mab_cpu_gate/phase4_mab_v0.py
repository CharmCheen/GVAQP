#!/usr/bin/env python3
"""Phase 4: MAB-v0 — contextual Thompson Sampling vs deterministic greedy.

Executed ONLY when the Phase 3 gates pass (ACTION_SPACE_GO +
CONTEXTUAL_MODEL_VIABLE). If gates do not pass, this script prints the
declined route and writes a stub MAB_V0_RESULTS.csv documenting NO_RUN.

Research scope (frozen): fixed candidate universe + weak proxy ranking;
choose the next VERIFY action to maximize terminal EventRelation quality
under an abstract query budget. NO endogenous acquisition claim.

Models: Bayesian logistic regression (Newton/variational approximation via
logistic regression with Laplace posterior) and linear contextual Thompson
Sampling; features = visible_* only. 50 seeds per cluster; seeds aggregated
within cluster before cluster-level comparison (video x query is the
statistical unit).
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "outputs/mab_cpu_gate_v1"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from common import VIDEOS, QUERY_VULN, QUERY_DRIVER, BUDGETS, any_time_auc
from phase2_action_table import Cluster, visible_rewards
from phase3_gate_metrics import anytime_curve, legal_next

FEATS = ["visible_proxy_score", "visible_proxy_rank", "visible_distance_to_positive",
         "visible_distance_to_negative", "visible_new_component_gain", "visible_redundancy",
         "visible_merge_risk", "visible_uncovered_region_change", "remaining_budget_fraction",
         "region_coverage_fraction", "current_component_count"]


def featurize(cl, queried, outcomes, action, budget):
    f = {}
    a_int = cl.intervals[action]
    dpos, dneg = [], []
    for c in queried:
        d = min(abs(a_int[1] - cl.intervals[c][2]), abs(a_int[2] - cl.intervals[c][1]))
        (dpos if outcomes.get(c) == "relevant" else dneg).append(d)
    comps = []
    pos = [cl.intervals[c] for c in queried if outcomes.get(c) == "relevant"]
    if pos:
        from common import c1_materialize
        comps = c1_materialize(cl.video, cl.query, pos)
    covered = sum(e.end_time - e.start_time for e in comps)
    t_span = cl.units[-1]["end_time"] - cl.units[0]["start_time"]
    n_total = len(cl.unit_ids)
    f["visible_proxy_score"] = cl.scores[action]
    f["visible_proxy_rank"] = cl.rank[action] / n_total
    f["visible_distance_to_positive"] = (min(dpos) if dpos else 10.0 * n_total) / (10.0 * n_total)
    f["visible_distance_to_negative"] = (min(dneg) if dneg else 10.0 * n_total) / (10.0 * n_total)
    f["visible_new_component_gain"] = float(not any(e.start_time < a_int[2] and e.end_time > a_int[1] for e in comps))
    f["visible_redundancy"] = 0.0
    f["visible_merge_risk"] = 0.0
    for e in comps:
        inter = max(0.0, min(a_int[2], e.end_time) - max(a_int[1], e.start_time))
        if inter > 0:
            f["visible_redundancy"] = max(f["visible_redundancy"], inter / (a_int[2] - a_int[1]))
        gap = min(max(0.0, e.start_time - a_int[2]), max(0.0, a_int[1] - e.end_time))
        if 0 < gap <= 10.0:
            f["visible_merge_risk"] = 1.0
    f["visible_uncovered_region_change"] = 1.0
    f["remaining_budget_fraction"] = (budget - len(queried)) / budget
    f["region_coverage_fraction"] = covered / t_span if t_span else 0.0
    f["current_component_count"] = len(comps)
    return np.array([f[k] for k in FEATS], dtype=float)


class BayesianLogistic:
    """Laplace-approximated Bayesian logistic regression (normal prior).
    Features are pre-scaled to [0,1]-ish ranges inside featurize()."""
    def __init__(self, dim, lam=1.0):
        self.dim = dim
        self.lam = lam
        self.w = np.zeros(dim)
        self.Hinv = np.eye(dim) / lam

    def update(self, X, y):
        for _ in range(20):
            p = 1.0 / (1.0 + np.exp(-np.clip(X @ self.w, -30, 30)))
            g = X.T @ (p - y) + self.lam * self.w
            S = (p * (1 - p))
            H = (X * S[:, None]).T @ X + self.lam * np.eye(self.dim)
            try:
                step = np.linalg.solve(H, g)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(H, g, rcond=None)[0]
            self.w = self.w - step
            if np.linalg.norm(step) < 1e-6:
                break
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ self.w, -30, 30)))
        S = (p * (1 - p))
        H = (X * S[:, None]).T @ X + self.lam * np.eye(self.dim)
        self.Hinv = np.linalg.inv(H)

    def sample_w(self, rng):
        return self.w + rng.multivariate_normal(np.zeros(self.dim), self.Hinv)


def simulate(cl, budget, policy, seed, model=None):
    """Run one episode under a policy; returns EventF1 at each budget step."""
    rng = np.random.default_rng(seed)
    q, o = [], {}
    f1s = []
    while len(q) < budget:
        legal = [c for c in cl.unit_ids if c not in q]
        if not legal:
            break
        # precompute current C1 components once per step (shared by all candidates)
        from common import c1_materialize
        pos = [cl.intervals[c] for c in q if o.get(c) == "relevant"]
        comps = c1_materialize(cl.video, cl.query, pos) if pos else []
        if policy == "top_proxy":
            a = min(legal, key=lambda c: (-cl.scores[c], c))
        elif policy == "relation_greedy":
            cand = sorted(legal, key=lambda c: (-cl.scores[c], c))[:50]
            a = max(cand, key=lambda c: visible_rewards(cl, q, o, c, comps)["visible_reward_r4"])
        elif policy == "ts":
            cand = sorted(legal, key=lambda c: (-cl.scores[c], c))[:50]
            X = np.array([featurize(cl, q, o, c, budget) for c in cand])
            w = model.sample_w(rng)
            p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -30, 30)))
            # expected value with counterfactual surrogate deltas
            vals = []
            for c, pi in zip(cand, p):
                rw = visible_rewards(cl, q, o, c, comps)
                d_pos = rw["visible_reward_r4"] + 1.0
                d_neg = rw["visible_reward_r4"]
                vals.append(pi * d_pos + (1 - pi) * d_neg)
            a = cand[int(np.argmax(vals))]
        else:
            raise ValueError(policy)
        q.append(a)
        o[a] = cl.label(a)
        if policy == "ts" and model is not None:
            x1 = featurize(cl, q, o, a, budget).reshape(1, -1)
            model.update(x1, np.array([1.0 if o[a] == "relevant" else 0.0]))
        f1s.append(cl.f1([c for c in q if o.get(c) == "relevant"]))
    return f1s


def _cluster_rows(args):
    cl, budgets_use, seeds = args
    rows = []
    t0 = time.time()
    for pol in ("top_proxy", "relation_greedy", "ts"):
        for b in budgets_use:
            aucs = []
            for seed in seeds:
                model = BayesianLogistic(len(FEATS), lam=1.0) if pol == "ts" else None
                f1s = simulate(cl, b, pol, int(seed), model)
                aucs.append(any_time_auc([(i + 1, f) for i, f in enumerate(f1s)]))
            rows.append({"cluster": f"{cl.video}_{cl.query}", "policy": pol, "budget": b,
                         "n_seeds": len(seeds),
                         "mean_eventf1_auc": float(np.mean(aucs)),
                         "seed_std": float(np.std(aucs))})
    print(f"[{time.time()-t0:.0f}s] {cl.video}/{cl.query} done", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    metrics = json.loads((GATE / "MAB_GATE_METRICS.json").read_text())
    routes = metrics["routes"]
    if not (routes["action_space"] == "ACTION_SPACE_GO" and routes["context"] == "CONTEXTUAL_MODEL_VIABLE"):
        pd.DataFrame({"policy": ["NO_RUN"], "cluster": ["n/a"], "seed": [0],
                      "eventf1_auc": [float("nan")], "reason": [routes]}).to_csv(
            GATE / "MAB_V0_RESULTS.csv", index=False)
        (GATE / "MAB_V0_REPORT.md").write_text(
            f"# MAB-v0 not executed\n\nRoutes: {routes}\n\nGates did not pass; "
            "MAB-v0 is not justified on the current substrate.\n")
        print("gates not passed; MAB-v0 declined:", routes)
        return

    budgets_use = (5, 10, 20) if args.quick else BUDGETS
    seeds = (0, 1) if args.quick else tuple(range(50))
    from phase2_action_table import GRID, PROXY_A, LABELS_BY_QUERY  # noqa
    clusters = []
    for v in VIDEOS:
        for q in (QUERY_VULN, QUERY_DRIVER):
            clusters.append(Cluster(v, q))

    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=min(6, len(clusters))) as ex:
        all_rows = list(ex.map(_cluster_rows, [(cl, budgets_use, seeds) for cl in clusters]))
    rows = [r for sub in all_rows for r in sub]
    print(f"total {time.time()-t0:.0f}s, rows={len(rows)}", flush=True)

    res = pd.DataFrame(rows)
    res.to_csv(GATE / "MAB_V0_RESULTS.csv", index=False)

    # comparison: TS vs relation greedy vs top_proxy (per cluster, primary query)
    md = ["# MAB-v0 report", ""]
    prim = res[res["cluster"].str.contains("Q_VULNERABLE")]
    for b in budgets_use:
        pivot = prim[prim["budget"] == b].pivot(index="cluster", columns="policy", values="mean_eventf1_auc")
        md.append(f"## budget {b}")
        md.append(pivot.round(4).to_markdown() if hasattr(pivot, "to_markdown") else pivot.round(4).to_string())
        md.append("")
    md.append("## gates and scope")
    md.append("- Scope: FIXED_CANDIDATE_REPLAY only; no endogenous acquisition claim.")
    md.append("- Model: Bayesian logistic (Laplace) contextual TS over visible_* features, top-50 proxy candidates.")
    md.append(f"- Routes at entry: {routes}")
    (GATE / "MAB_V0_REPORT.md").write_text("\n".join(md))
    print("MAB_V0_RESULTS.csv + report written")


if __name__ == "__main__":
    main()
