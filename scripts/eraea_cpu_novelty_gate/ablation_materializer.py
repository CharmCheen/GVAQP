#!/usr/bin/env python3
"""ERAEA E3/E4: reward ablation (R0..R4) + materializer decoupling
(3 scorings x 3 materializers) + gap-threshold sensitivity. CPU-only."""
import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "outputs/eraea_cpu_novelty_gate_v1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scripts/mab_cpu_gate"))

import numpy as np
import pandas as pd

from common import VIDEOS, QUERY_VULN, BUDGETS, any_time_auc
from phase2_action_table import Cluster, visible_rewards
from run_eraea_gate import (policy_order, trace_metrics, MATS, materialize,
                            event_f1, C1_GAP, C3_GAP, C3_DUR, has_barrier)

FEAT_REWARDS = {"R1": "visible_reward_r1", "R2": "visible_reward_r2",
                "R3": "visible_reward_r3", "R4": "visible_reward_r4"}


def scoring_greedy(cluster, budget, score_kind, mat, seed=0):
    """Deterministic greedy using one scoring family; returns (q, o)."""
    q, o = [], {}
    while len(q) < budget:
        legal = [c for c in cluster.unit_ids if c not in q]
        if not legal:
            break
        comps = materialize(cluster, cluster.query,
                            [(cluster.intervals[c][0], cluster.intervals[c][1], cluster.intervals[c][2])
                             for c in q if o.get(c) == "relevant"], mat) if q else []
        if score_kind == "agnostic":
            a = min(legal, key=lambda c: (-cluster.scores[c], c))
        elif score_kind == "gap_aware":
            cand = sorted(legal, key=lambda c: (-cluster.scores[c], c))[:50]
            a = max(cand, key=lambda c: visible_rewards(cluster, q, o, c, comps)["visible_reward_r4"])
        elif score_kind == "k3_aware":
            # barrier/duration-aware visible surrogate using C3 semantics
            cand = sorted(legal, key=lambda c: (-cluster.scores[c], c))[:50]
            best, best_v = None, -1e18
            for c in cand:
                rw = visible_rewards(cluster, q, o, c, comps)
                s, e = cluster.intervals[c][1], cluster.intervals[c][2]
                # K3-like: merge risk counts a verified-negative barrier in the gap
                barrier_risk = 0.0
                for u in q:
                    if o.get(u) == "not_relevant":
                        us, ue = cluster.intervals[u][1], cluster.intervals[u][2]
                        if us >= min(e, comps[-1].end_time if comps else e) and ue <= max(s, comps[0].start_time if comps else s) and ue > s and us < e:
                            barrier_risk = 1.0
                v = rw["visible_reward_r2"] - rw["visible_merge_risk"] - 0.5 * barrier_risk
                if v > best_v:
                    best, best_v = c, v
            a = best
        else:  # reward ablation: R1..R4 visible
            col = FEAT_REWARDS[score_kind]
            cand = sorted(legal, key=lambda c: (-cluster.scores[c], c))[:50]
            a = max(cand, key=lambda c: visible_rewards(cluster, q, o, c, comps)[col])
        q.append(a); o[a] = cluster.label(a)
    return q, o


def run_jobs(args):
    cl, budgets_use = args
    rows = []
    # E3 reward ablation (C1 materializer)
    for rk in ("R0", "R1", "R2", "R3", "R4"):
        for b in budgets_use:
            if rk == "R0":
                q, o = scoring_greedy(cl, b, "agnostic", "C1")  # visible yield surrogate = proxy score
            else:
                q, o = scoring_greedy(cl, b, rk, "C1")
            auc = any_time_auc([(i + 1, trace_metrics(cl, q[: i + 1], o, "C1")["EventF1"]) for i in range(len(q))])
            tm = trace_metrics(cl, q, o, "C1")
            rows.append({"video_id": cl.video, "query_id": cl.query, "reward": rk, "budget": b,
                         "eventf1_auc": auc, "EventF1": tm["EventF1"], "yield": tm["yield"],
                         "coverage_fraction": tm["coverage_fraction"]})
    # E4 materializer decoupling: scoring x materialize
    for scoring in ("agnostic", "gap_aware", "k3_aware"):
        for mat_name in ("C1", "K0", "C3"):
            for b in budgets_use:
                q, o = scoring_greedy(cl, b, scoring, mat_name)
                auc = any_time_auc([(i + 1, trace_metrics(cl, q[: i + 1], o, mat_name)["EventF1"]) for i in range(len(q))])
                rows.append({"video_id": cl.video, "query_id": cl.query,
                             "scoring": scoring, "materializer": mat_name, "budget": b,
                             "eventf1_auc": auc, "experiment": "E4"})
    # E4 gap-threshold sensitivity (C1 family, relation-greedy vs top_proxy)
    for gap in (5.0, 10.0, 15.0, 20.0):
        for pol, scoring in (("top_proxy", "agnostic"), ("relation_greedy", "gap_aware")):
            for b in budgets_use:
                q, o = scoring_greedy(cl, b, scoring, "C1")
                auc = any_time_auc([(i + 1, trace_metrics(cl, q[: i + 1], o, "C1", gap)["EventF1"]) for i in range(len(q))])
                rows.append({"video_id": cl.video, "query_id": cl.query,
                             "gap_threshold": gap, "policy": pol, "budget": b,
                             "eventf1_auc": auc, "experiment": "E4GAP"})
    print(f"[{time.time():.0f}] {cl.video}/{cl.query} done", flush=True)
    return rows


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    budgets_use = (5, 10, 20) if args.quick else BUDGETS
    from phase2_action_table import GRID, PROXY_A, LABELS_BY_QUERY  # noqa
    clusters = [Cluster(v, QUERY_VULN) for v in VIDEOS]
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=min(6, len(clusters))) as ex:
        all_rows = list(ex.map(run_jobs, [(cl, budgets_use) for cl in clusters]))
    rows = [r for sub in all_rows for r in sub]
    df = pd.DataFrame(rows)
    df.to_csv(GATE / "MATERIALIZER_DECOUPLING.csv", index=False)
    print(f"MATERIALIZER_DECOUPLING.csv rows={len(df)} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
