#!/usr/bin/env python3
"""ERAEA CPU novelty gate — baselines + metrics + experiments (CPU-only).

Scope: FIXED_CANDIDATE_REPLAY, MODEL_RELATIVE_DIAGNOSTIC.
All methods share the same candidate universe, visible state, action cost
(1 VERIFY call), verifier outcomes, materializer contract and evaluator.

Experiments:
  E1 equal-yield residual pairs
  E2 novelty-killer baseline matrix (G_generic, eta_explained)
  E3 reward ablation R0..R4
  E4 materializer decoupling + gap sensitivity (Retention_gap)
  E5 deviation audit (BENEFICIAL/HARMFUL/INDIFFERENT + reasons)
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "outputs/eraea_cpu_novelty_gate_v1"
GATE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scripts/mab_cpu_gate"))

import numpy as np
import pandas as pd

from common import (VIDEOS, QUERY_VULN, QUERY_DRIVER, BUDGETS, any_time_auc,
                    c1_materialize, temporal_iou, event_f1, match_events)
from phase2_action_table import Cluster, visible_rewards

MATS = {"C1": "C1_gap_limited", "K0": "K0_single_span", "C3": "C3_gap_duration_barrier"}
C1_GAP = 10.0
C3_GAP = 10.0
C3_DUR = 40.0
STRATA = 10
ALPHA_EXSAMPLE = 3.0
UCB_C = 1.0
UCB_BLOCK = 50.0  # seconds per Seiden-style region


# ---------------------------------------------------------------- materializers

def materialize(cluster, query, pos_units, mat, gap=C1_GAP):
    """pos_units: list of (unit_id, start, end) of verified-relevant units."""
    if not pos_units:
        return []
    pos = sorted(pos_units, key=lambda x: (x[1], x[2], x[0]))
    if mat == "K0":
        return [type("E", (), {"event_id": "k0", "query_id": query, "video_id": cluster.video,
                "start_time": pos[0][1], "end_time": pos[-1][2], "source_unit_ids": tuple(x[0] for x in pos),
                "materializer": "K0"})()]
    groups = [[pos[0]]]
    for right in pos[1:]:
        left = groups[-1][-1]
        g = max(0.0, right[1] - left[2])
        merge = g <= (C3_GAP if mat == "C3" else gap)
        if mat == "C3":
            proposed = groups[-1][0][1], right[2]
            merge = merge and (proposed[1] - proposed[0] <= C3_DUR)
        # negative barrier for C3: a verified-not-relevant unit strictly between anchors
        if mat == "C3":
            merge = merge and not has_barrier(cluster, pos_units, left[2], right[1])
        if merge:
            groups[-1].append(right)
        else:
            groups.append([right])
    out = []
    for i, g in enumerate(groups):
        out.append(type("E", (), {"event_id": f"{mat}_{i}", "query_id": query, "video_id": cluster.video,
                "start_time": min(x[1] for x in g), "end_time": max(x[2] for x in g),
                "source_unit_ids": tuple(x[0] for x in g), "materializer": mat})())
    return out


def has_barrier(cluster, all_units, lo, hi):
    """True if any unit interval strictly between lo..hi is a verified negative
    (barrier) in the query's cached outcome for this trace."""
    # barrier semantics need the verified-negative units between the anchors;
    # we approximate with the full cached label grid of the cluster.
    for u in cluster.unit_ids:
        s, e = cluster.intervals[u][1], cluster.intervals[u][2]
        if s >= lo and e <= hi and s < hi and e > lo:
            if cluster.label(u) == "not_relevant":
                return True
    return False


def f1_vs_ref(cluster, pos_units, mat):
    pred = materialize(cluster, cluster.query, pos_units, mat)
    return event_f1(pred, cluster.reference)


# ---------------------------------------------------------------- trace metrics

def trace_metrics(cluster, queried, outcomes, mat="C1", gap=C1_GAP):
    """Full metrics of one completed trace under final materializer `mat`."""
    pos = [(u, cluster.intervals[u][1], cluster.intervals[u][2]) for u in queried
           if outcomes.get(u) == "relevant"]
    pred = materialize(cluster, cluster.query, pos, mat, gap)
    m = event_f1(pred, cluster.reference)
    # boundary IoU
    matches = match_events(pred, cluster.reference)
    biou = float(np.mean([mm[2] for mm in matches])) if matches else 0.0
    # overmerge / split via event-center coverage
    ref_centers = [(e.start_time + e.end_time) / 2 for e in cluster.reference]
    overmerge = 0
    for e in pred:
        hits = sum(1 for c in ref_centers if e.start_time <= c <= e.end_time)
        if hits >= 2:
            overmerge += 1
    pred_centers = [(e.start_time + e.end_time) / 2 for e in pred]
    split = 0
    for r in cluster.reference:
        hits = sum(1 for c in pred_centers if r.start_time <= c <= r.end_time)
        if hits >= 2:
            split += 1
    # duplicate evidence rate: verified-relevant units inside a previously
    # formed component span (computed greedily along the query order)
    comp_spans = []
    dup = 0
    for u in queried:
        s, e = cluster.intervals[u][1], cluster.intervals[u][2]
        inside = any(lo <= s and e <= hi for (lo, hi) in comp_spans)
        if outcomes.get(u) == "relevant":
            if inside:
                dup += 1
            # update spans with C1 merge over positives so far
            pos_so_far = [(x, cluster.intervals[x][1], cluster.intervals[x][2])
                          for x in queried[: queried.index(u) + 1] if outcomes.get(x) == "relevant"]
            comp_spans = [(ev.start_time, ev.end_time)
                          for ev in materialize(cluster, cluster.query, pos_so_far, "C1", gap)]
    n_pos = len(pos)
    return {
        "yield": n_pos,
        "coverage_fraction": (sum(e.end_time - e.start_time for e in pred) /
                              (cluster.units[-1]["end_time"] - cluster.units[0]["start_time"])) if pred else 0.0,
        "EventF1": m["EventF1"], "EventRecall": m["EventRecall"], "EventPrecision": m["EventPrecision"],
        "boundary_iou": biou, "overmerge": overmerge, "split": split,
        "duplicate_evidence_rate": (dup / n_pos) if n_pos else 0.0,
        "unique_event_recall": m["EventRecall"], "n_predicted_events": len(pred),
    }


# ---------------------------------------------------------------- policies

def policy_order(cluster, policy, budget, seed=0, reward=None, mat="C1", model=None, rng=None):
    """Return the ordered selection for a policy (deterministic given seed)."""
    if policy in ("uniform", "stratified", "top_proxy", "temporal_coverage", "new_component",
                  "mmr", "facility", "relation_greedy", "yield_greedy_oracle", "oracle1", "oracle2"):
        q, o = [], {}
        while len(q) < budget:
            legal = [c for c in cluster.unit_ids if c not in q]
            if not legal:
                break
            a = _next(cluster, q, o, policy, budget, seed, reward, mat)
            q.append(a); o[a] = cluster.label(a)
        return q, o
    # stochastic policies
    r = rng or np.random.default_rng(seed)
    q, o = [], {}
    while len(q) < budget:
        legal = [c for c in cluster.unit_ids if c not in q]
        if not legal:
            break
        a = _next(cluster, q, o, policy, budget, seed, reward, mat, model, r)
        q.append(a); o[a] = cluster.label(a)
        if policy in ("relation_ts", "yield_ts") and model is not None:
            from phase4_mab_v0 import featurize, FEATS as P4FEATS
            x1 = featurize(cluster, q, o, a, budget).reshape(1, -1)
            model.update(x1, np.array([1.0 if o[a] == "relevant" else 0.0]))
    return q, o


def _visible_comp(cluster, queried, outcomes, mat):
    pos = [(cluster.intervals[c][0], cluster.intervals[c][1], cluster.intervals[c][2])
           for c in queried if outcomes.get(c) == "relevant"]
    return materialize(cluster, cluster.query, pos, mat) if pos else []


def _next(cluster, q, o, policy, budget, seed, reward, mat, model=None, rng=None):
    legal = [c for c in cluster.unit_ids if c not in q]
    if policy == "uniform":
        return dyadic_first(cluster, legal)
    if policy == "stratified":
        span = cluster.units[-1]["end_time"] - cluster.units[0]["start_time"]
        w = span / STRATA
        # pick the least-covered stratum, then top proxy inside it
        covered = [0.0] * STRATA
        for c in q:
            s = cluster.intervals[c][1]
            covered[min(int(s // w), STRATA - 1)] += 1
        strata = sorted(range(STRATA), key=lambda k: (covered[k], k))
        for k in strata:
            lo, hi = k * w, (k + 1) * w
            cands = [c for c in legal if lo <= cluster.intervals[c][1] < hi]
            if cands:
                return min(cands, key=lambda c: (-cluster.scores[c], c))
        return min(legal, key=lambda c: (-cluster.scores[c], c))
    if policy == "top_proxy":
        return min(legal, key=lambda c: (-cluster.scores[c], c))
    if policy == "temporal_coverage":
        return coverage_next(cluster, q, legal)
    if policy in ("new_component", "relation_greedy", "reward_ablation"):
        comps = _visible_comp(cluster, q, o, mat if mat in MATS else "C1")
        rk = "visible_reward_r1" if policy == "new_component" else (f"visible_reward_{reward}" if reward else "visible_reward_r4")
        cand = sorted(legal, key=lambda c: (-cluster.scores[c], c))[:50]
        return max(cand, key=lambda c: visible_rewards(cluster, q, o, c, comps)[rk])
    if policy == "mmr":
        # frozen MMR formula (scripts/freeze_p1_trace_population.py::mmr):
        # novelty = min |i-j| / (len-1) over INDEX positions; score normalized [0,1]
        lam = 0.5
        idx = {c: k for k, c in enumerate(sorted(legal, key=lambda c: (-cluster.scores[c], c)))}
        cand_sorted = [c for c in sorted(legal, key=lambda c: (-cluster.scores[c], c))]
        n = len(cand_sorted)
        scores = np.array([cluster.scores[c] for c in cand_sorted])
        lo, hi = scores.min(), scores.max()
        norm = (scores - lo) / (hi - lo) if hi > lo else np.zeros_like(scores)
        sel_pos = sorted(idx[c] for c in q if c in idx)
        best, best_v = None, -1e18
        for i, c in enumerate(cand_sorted):
            novelty = 1.0 if not sel_pos else min(abs(i - j) / max(n - 1, 1) for j in sel_pos)
            v = (1 - lam) * norm[i] + lam * novelty
            if v > best_v:
                best, best_v = c, v
        return best
    if policy == "facility":
        # submodular facility-location greedy with temporal closeness kernel
        best, best_v = None, -1e18
        for c in legal:
            gain = 0.0
            for u in cluster.unit_ids:
                if u in q or u == c:
                    continue
                du = min(min(abs(cluster.intervals[u][1] - cluster.intervals[x][2]),
                             abs(cluster.intervals[u][2] - cluster.intervals[x][1])) for x in (q + [c]))
                gain += np.exp(-du / 100.0) if du < 1e6 else 0.0
            if gain > best_v:
                best, best_v = c, gain
        return best
    if policy == "yield_greedy_oracle":
        return min(legal, key=lambda c: (0 if cluster.label(c) == "relevant" else 1, -cluster.scores[c]))
    if policy == "exsample":
        # Thompson per-unit: Beta(1 + a*s, 1 + a*(1-s)) over the proxy score
        cand = sorted(legal, key=lambda c: -cluster.scores[c])[:100]
        vals = {}
        for c in cand:
            s = cluster.scores[c]
            vals[c] = rng.beta(1 + ALPHA_EXSAMPLE * s, 1 + ALPHA_EXSAMPLE * (1 - s))
        return max(cand, key=lambda c: vals[c])
    if policy == "seiden_ucb":
        # region-level UCB (region = 50s block)
        span = cluster.units[-1]["end_time"] - cluster.units[0]["start_time"]
        nblocks = int(np.ceil(span / UCB_BLOCK))
        visited = {k: 0 for k in range(nblocks)}
        pos_hits = {k: 0 for k in range(nblocks)}
        for c in q:
            k = min(int(cluster.intervals[c][1] // UCB_BLOCK), nblocks - 1)
            visited[k] += 1
            if o.get(c) == "relevant":
                pos_hits[k] += 1
        total = len(q) + 1
        best, best_v = None, -1e18
        for c in legal:
            k = min(int(cluster.intervals[c][1] // UCB_BLOCK), nblocks - 1)
            mean = (pos_hits[k] / visited[k]) if visited[k] else 0.5
            ucb = mean + UCB_C * np.sqrt(2 * np.log(total) / max(visited[k], 1))
            v = ucb + 1e-6 * cluster.scores[c]
            if v > best_v:
                best, best_v = c, v
        return best
    if policy == "relation_ts":
        from phase4_mab_v0 import featurize, FEATS as P4FEATS
        cand = sorted(legal, key=lambda c: (-cluster.scores[c], c))[:50]
        comps = _visible_comp(cluster, q, o, "C1")
        X = np.array([featurize(cluster, q, o, c, budget) for c in cand])
        w = model.sample_w(rng)
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -30, 30)))
        vals = []
        for c, pi in zip(cand, p):
            rw = visible_rewards(cluster, q, o, c, comps)
            vals.append(pi * (rw["visible_reward_r4"] + 1.0) + (1 - pi) * rw["visible_reward_r4"])
        return cand[int(np.argmax(vals))]
    if policy == "yield_ts":
        from phase4_mab_v0 import featurize, FEATS as P4FEATS
        cand = sorted(legal, key=lambda c: (-cluster.scores[c], c))[:50]
        X = np.array([featurize(cluster, q, o, c, budget) for c in cand])
        w = model.sample_w(rng)
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -30, 30)))
        return cand[int(np.argmax(p))]
    if policy == "oracle1":
        base = cluster.f1([c for c in q if o.get(c) == "relevant"])
        best, best_d = None, -1e9
        for c in legal:
            pos1 = [x for x in q if o.get(x) == "relevant"]
            if cluster.label(c) == "relevant":
                pos1.append(c)
            d = cluster.f1(pos1) - base
            if d > best_d:
                best, best_d = c, d
        return best
    if policy == "oracle2":
        from phase3_gate_metrics import oracle2_policy
        return oracle2_policy(cluster, q, o)
    raise ValueError(policy)


def dyadic_first(cluster, legal):
    if not legal:
        return None
    # first element of the dyadic bisection of the legal set (nested uniform)
    order = []
    rec = lambda lo, hi: None
    def r(lo, hi):
        if hi - lo <= 1:
            if lo < hi:
                order.append(legal[lo])
            return
        mid = (lo + hi) // 2
        r(lo, mid); r(mid, hi)
    r(0, len(legal))
    return order[0]


def coverage_next(cluster, q, legal):
    sel = [cluster.intervals[x][1] for x in q] + [cluster.intervals[x][2] for x in q]
    def dist(c):
        s, e = cluster.intervals[c][1], cluster.intervals[c][2]
        return min([min(abs(s - t), abs(e - t)) for t in sel] or [1e9])
    if not q:
        return min(legal, key=lambda c: cluster.intervals[c][1])
    return max(legal, key=dist)


# ---------------------------------------------------------------- run

def run_cluster(args):
    cl, budgets_use, policies, mat, seeds = args
    rows = []
    for pol in policies:
        for b in budgets_use:
            if pol in ("exsample", "seiden_ucb"):
                aucs = []
                for s in range(3):
                    q, o = policy_order(cl, pol, b, seed=s)
                    aucs.append(any_time_auc([(i + 1, trace_metrics(cl, q[: i + 1], o)["EventF1"]) for i in range(len(q))]))
                auc = float(np.mean(aucs))
            elif pol in ("relation_ts", "yield_ts"):
                from phase4_mab_v0 import BayesianLogistic, FEATS as P4FEATS
                aucs = []
                for s in range(3):
                    model = BayesianLogistic(len(P4FEATS), lam=1.0)
                    q, o = policy_order(cl, pol, b, seed=s, model=model)
                    aucs.append(any_time_auc([(i + 1, trace_metrics(cl, q[: i + 1], o)["EventF1"]) for i in range(len(q))]))
                auc = float(np.mean(aucs))
            else:
                q, o = policy_order(cl, pol, b, seed=0)
                auc = any_time_auc([(i + 1, trace_metrics(cl, q[: i + 1], o)["EventF1"]) for i in range(len(q))])
            tm = trace_metrics(cl, q, o, mat) if pol not in ("exsample", "seiden_ucb", "relation_ts", "yield_ts") else trace_metrics(cl, q, o, mat)
            rows.append({"video_id": cl.video, "query_id": cl.query, "policy": pol, "budget": b,
                         "mat": mat, "eventf1_auc": auc, **{k: tm[k] for k in
                         ("yield", "coverage_fraction", "EventF1", "EventRecall", "boundary_iou",
                          "overmerge", "split", "duplicate_evidence_rate", "n_predicted_events")}})
    print(f"[{time.time():.0f}] {cl.video}/{cl.query} done", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    budgets_use = (5, 10, 20) if args.quick else BUDGETS
    policies = ["uniform", "stratified", "top_proxy", "temporal_coverage", "new_component",
                "mmr", "facility", "exsample", "seiden_ucb", "relation_greedy",
                "yield_greedy_oracle", "relation_ts", "yield_ts", "oracle1", "oracle2"]
    from phase2_action_table import GRID, PROXY_A, LABELS_BY_QUERY  # noqa
    clusters = []
    for v in VIDEOS:
        for q in (QUERY_VULN,):
            clusters.append(Cluster(v, q))
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=min(6, len(clusters))) as ex:
        all_rows = list(ex.map(run_cluster, [(cl, budgets_use, policies, "C1", (0, 1, 2)) for cl in clusters]))
    rows = [r for sub in all_rows for r in sub]
    df = pd.DataFrame(rows)
    df.to_csv(GATE / "BASELINE_MATRIX.csv", index=False)
    print(f"BASELINE_MATRIX.csv rows={len(df)} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
