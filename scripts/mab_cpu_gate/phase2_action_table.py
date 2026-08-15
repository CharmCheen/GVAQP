#!/usr/bin/env python3
"""Phase 2: construct the full-information ACTION_VALUE_TABLE (CPU-only).

Substrate: FIXED_CANDIDATE_REPLAY over frozen cached artifacts.
  - Q_VULNERABLE x {DALI,HANGZHOU,WUHAN}: full 1475-unit semantic table
    (rebuilt from qwen32_oracle/raw, validated 252/252 vs P2 manifest),
    Proxy A scores (reconstructed + validated), 10s unit grid.
  - Q_DRIVER x 3 videos: MODEL_RELATIVE_DIAGNOSTIC_ONLY, union-known labels,
    partial reference (full grid unrecoverable locally).

Actions: a_t = VERIFY(c) for legal (unqueried, known-label) candidates.
Values: R0-R4 visible surrogates; one-step oracle EventF1 delta; terminal
deltas under top_proxy / relation_greedy continuations; depth-2 on small
remaining-budget states. Policy/oracle isolation enforced (features visible_*).

Usage:
  python scripts/mab_cpu_gate/phase2_action_table.py [--quick]
"""
import argparse, csv, hashlib, json, random, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "outputs/mab_cpu_gate_v1"
GATE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (VIDEOS, QUERY_VULN, QUERY_DRIVER, BUDGETS, load_unit_grid,
                    load_qwen32_labels, load_trace_labels, load_seal_labels,
                    load_proxy_a_scores, load_p2_manifest, c1_materialize,
                    event_f1, temporal_iou)

import numpy as np
import pandas as pd

GRID = load_unit_grid()
PROXY_A = load_proxy_a_scores()
LABELS_BY_QUERY = {
    QUERY_VULN: load_qwen32_labels(),
    QUERY_DRIVER: {**load_trace_labels(), **load_seal_labels()},
}

# ------------------------------------------------------------ substrate

class Cluster:
    def __init__(self, video, query):
        self.video, self.query = video, query
        self.units = sorted([u for u in GRID[video]], key=lambda u: u["unit_id"])
        self.unit_ids = [u["candidate_id"] for u in self.units]
        self.intervals = {u["candidate_id"]: (u["candidate_id"], u["start_time"], u["end_time"]) for u in self.units}
        self.labels = LABELS_BY_QUERY[query]
        self.full = query == QUERY_VULN
        pos = [self.intervals[c] for c in self.unit_ids if self.labels.get(c) == "relevant"]
        self.reference = c1_materialize(video, query, pos)
        self.ref_by_id = {e.event_id: e for e in self.reference}
        scores = PROXY_A
        self.scores = {c: scores[c] for c in self.unit_ids}
        order = sorted(self.unit_ids, key=lambda c: (-self.scores[c], c))
        self.rank = {c: i for i, c in enumerate(order)}
        self.universe = set(self.unit_ids)

    def label(self, c):
        return self.labels.get(c, "unknown")

    def f1(self, pos_units):
        pred = c1_materialize(self.video, self.query, [self.intervals[c] for c in pos_units])
        return event_f1(pred, self.reference)["EventF1"]

# ------------------------------------------------------------ policies

def dyadic_order(unit_ids, rng):
    n = len(unit_ids)
    order = []
    def rec(lo, hi):
        if hi - lo <= 1:
            if lo < hi: order.append(unit_ids[lo])
            return
        mid = (lo + hi) // 2
        rec(lo, mid); rec(mid, hi)
    rec(0, n)
    return order

def top_proxy_order(cluster):
    return sorted(cluster.unit_ids, key=lambda c: (-cluster.scores[c], c))

def coverage_first_order(cluster, rng, budget):
    """Deterministic farthest-first temporal coverage (mirrors P2 CoverageFirst:
    greedily pick the unit whose interval is farthest from all selected ones)."""
    sel = []
    remaining = [c for c in cluster.unit_ids]
    def dist(c):
        s, e = cluster.intervals[c][1], cluster.intervals[c][2]
        best = float("inf")
        for x in sel:
            xs, xe = cluster.intervals[x][1], cluster.intervals[x][2]
            if e <= xs:
                d = xs - e
            elif s >= xe:
                d = s - xe
            else:
                d = 0.0
            best = min(best, d)
        return best
    first = [min(cluster.unit_ids, key=lambda c: cluster.intervals[c][1]),
             max(cluster.unit_ids, key=lambda c: cluster.intervals[c][2])]
    for c in first:
        if c in remaining:
            sel.append(c); remaining.remove(c)
    while len(sel) < budget and remaining:
        c = max(remaining, key=dist)
        sel.append(c); remaining.remove(c)
    return sel

def visible_rewards(cluster, queried, outcomes, action, comps=None):
    """R0-R4 computed from visible state + action interval + (for R0) the
    recorded outcome of this action (full-information table stores observed
    outcome; online policies use expected value instead). comps may be
    precomputed per step for speed."""
    a_int = cluster.intervals[action]
    a_start, a_end = a_int[1], a_int[2]
    if comps is None:
        pos = [cluster.intervals[c] for c in queried if outcomes.get(c) == "relevant"]
        comps = c1_materialize(cluster.video, cluster.query, pos) if pos else []
    # visible geometry vs current components
    new_comp_gain = 1.0
    redundancy = 0.0
    merge_risk = 0.0
    boundary_unc = 0.0
    covered_len = 0.0
    for e in comps:
        inter = max(0.0, min(a_end, e.end_time) - max(a_start, e.start_time))
        gap_lo = max(0.0, e.start_time - a_end)
        gap_hi = max(0.0, a_start - e.end_time)
        gap = min(gap_lo, gap_hi)
        if inter > 0:
            new_comp_gain = 0.0
            redundancy = max(redundancy, inter / (a_end - a_start))
            boundary_unc = max(boundary_unc, 1.0)
            covered_len += inter
        elif gap <= 10.0:
            new_comp_gain = min(new_comp_gain, 0.5)
            merge_risk = 1.0
    uncovered_change = (a_end - a_start - covered_len) / (a_end - a_start)
    y = 1.0 if cluster.label(action) == "relevant" else 0.0
    r0 = y
    r1 = new_comp_gain
    r2 = new_comp_gain - redundancy
    r3 = r2 - merge_risk
    r4 = r3 + boundary_unc
    return dict(
        visible_new_component_gain=new_comp_gain, visible_redundancy=redundancy,
        visible_merge_risk=merge_risk, visible_boundary_uncertainty=boundary_unc,
        visible_uncovered_region_change=uncovered_change,
        visible_reward_r0=r0, visible_reward_r1=r1, visible_reward_r2=r2,
        visible_reward_r3=r3, visible_reward_r4=r4)

def state_features(cluster, queried, outcomes, budget):
    """Visible features of the state itself (action-independent)."""
    n_total = len(cluster.unit_ids)
    t_span = cluster.units[-1]["end_time"] - cluster.units[0]["start_time"]
    covered = 0.0
    pos = [cluster.intervals[c] for c in queried if outcomes.get(c) == "relevant"]
    comps = c1_materialize(cluster.video, cluster.query, pos) if pos else []
    for e in comps:
        covered += (e.end_time - e.start_time)
    return dict(
        remaining_budget=budget - len(queried),
        remaining_budget_fraction=(budget - len(queried)) / budget,
        queried_fraction=len(queried) / n_total,
        verified_positive_count=sum(1 for c in queried if outcomes.get(c) == "relevant"),
        verified_negative_count=sum(1 for c in queried if outcomes.get(c) not in ("relevant",)),
        region_coverage_fraction=covered / t_span if t_span else 0.0,
        current_component_count=len(comps))

def action_features(cluster, queried, outcomes, action, budget):
    f = {}
    a_int = cluster.intervals[action]
    f["action_id"] = action
    f["action_type"] = "VERIFY"
    f["candidate_start"] = a_int[1]
    f["candidate_end"] = a_int[2]
    f["context_length"] = a_int[2] - a_int[1]
    f["visible_proxy_score"] = cluster.scores[action]
    f["visible_proxy_rank"] = cluster.rank[action]
    # distances to verified positives/negatives (visible)
    dpos, dneg = [], []
    for c in queried:
        o = outcomes.get(c)
        d = min(abs(a_int[1] - cluster.intervals[c][2]), abs(a_int[2] - cluster.intervals[c][1]))
        if o == "relevant": dpos.append(d)
        else: dneg.append(d)
    f["visible_distance_to_positive"] = min(dpos) if dpos else float("nan")
    f["visible_distance_to_negative"] = min(dneg) if dneg else float("nan")
    f.update(state_features(cluster, queried, outcomes, budget))
    return f

# ------------------------------------------------------------ rollouts

def rollout(cluster, budget, queried, outcomes, policy, rng, max_steps=None):
    """Continue from a prefix with a legal policy until budget exhausted.
    Returns final EventF1 against the reference and the action sequence.
    relation_greedy = visible R4 greedy over the top-50 proxy-ranked legal
    actions (K=50 recorded); top_proxy = pure proxy order."""
    q = list(queried); o = dict(outcomes)
    steps = 0
    while len(q) < budget:
        if max_steps is not None and steps >= max_steps:
            break
        legal = [c for c in cluster.unit_ids if c not in q]
        if not legal:
            break
        if policy == "top_proxy":
            a = min(legal, key=lambda c: (-cluster.scores[c], c))
        elif policy == "relation_greedy":
            cand = sorted(legal, key=lambda c: (-cluster.scores[c], c))[:50]
            a = max(cand, key=lambda c: visible_rewards(cluster, q, o, c)["visible_reward_r4"])
        else:
            raise ValueError(policy)
        q.append(a); o[a] = cluster.label(a); steps += 1
    f1 = cluster.f1([c for c in q if o.get(c) == "relevant"])
    return f1, q

# ------------------------------------------------------------ main

def build(cluster, queried, outcomes, budget, state_id, action_set, k_note,
          do_terminal, do_depth2, depth2_topk):
    rows = []
    base_f1 = cluster.f1([c for c in queried if outcomes.get(c) == "relevant"])
    sfeat = state_features(cluster, queried, outcomes, budget)
    # baseline terminal (default action policy from H): top_proxy continuation
    if do_terminal:
        base_top, _ = rollout(cluster, budget, queried, outcomes, "top_proxy", None)
        base_rel, _ = rollout(cluster, budget, queried, outcomes, "relation_greedy", None)
    for action in action_set:
        out = cluster.label(action)
        f = {"video_id": cluster.video, "query_id": cluster.query, "state_id": state_id,
             "decision_idx": len(queried), "budget": budget, "action_set_kind": k_note,
             "materializer_version": "C1_gap_limited",
             "reference_type": "MODEL_RELATIVE" if cluster.full else "MODEL_RELATIVE_PARTIAL_UNION"}
        f.update(action_features(cluster, queried, outcomes, action, budget))
        f["observed_outcome"] = out
        f["actual_or_cached_cost"] = 1.0  # one VERIFY call (abstract query budget)
        rw = visible_rewards(cluster, queried, outcomes, action)
        f.update(rw)
        # one-step oracle delta
        pos1 = [c for c in queried if outcomes.get(c) == "relevant"]
        if out == "relevant":
            pos1.append(action)
        f1a = cluster.f1(pos1)
        f["oracle_eventf1_delta_1step"] = f1a - base_f1
        # terminal deltas: computed only for top-15 actions (K=15 recorded)
        f["oracle_terminal_delta_topproxy"] = float("nan")
        f["oracle_terminal_delta_relation_greedy"] = float("nan")
        # depth-2 (only for small remaining budget and top actions)
        f["oracle_depth2_delta"] = float("nan")
        rows.append(f)
    if do_terminal:
        # terminal rollouts for top-15 actions by |delta1| then R4 (K recorded)
        top15 = sorted(rows, key=lambda r: (-abs(r["oracle_eventf1_delta_1step"]), -r["visible_reward_r4"]))[:15]
        for f in top15:
            action = f["action_id"]
            out = f["observed_outcome"]
            f1_top, _ = rollout(cluster, budget, queried + [action],
                                {**outcomes, action: out}, "top_proxy", None)
            f1_rel, _ = rollout(cluster, budget, queried + [action],
                                {**outcomes, action: out}, "relation_greedy", None)
            f["oracle_terminal_delta_topproxy"] = f1_top - base_top
            f["oracle_terminal_delta_relation_greedy"] = f1_rel - base_rel
    if do_depth2:
        # order rows by one-step delta desc, keep top-k (K recorded)
        ordered = sorted(rows, key=lambda r: r["oracle_eventf1_delta_1step"], reverse=True)[:depth2_topk]
        for f in ordered:
            action = f["action_id"]
            out = f["observed_outcome"]
            h1_queried = queried + [action]
            h1_outcomes = {**outcomes, action: out}
            pos1 = [c for c in h1_queried if h1_outcomes.get(c) == "relevant"]
            f1_h1 = cluster.f1(pos1)
            # top-K2=50 candidate actions for the max over next actions (K2 recorded)
            cand2 = sorted([c for c in cluster.unit_ids if c not in h1_queried],
                           key=lambda c: (-cluster.scores[c], c))[:50]
            random.seed(state_id + ":d2")
            cand2 += random.sample([c for c in cluster.unit_ids if c not in h1_queried], min(0, len(cluster.unit_ids) - len(h1_queried)))
            best_next = -1e9
            for a2 in set(cand2):
                o2 = cluster.label(a2)
                pos2 = pos1 + ([a2] if o2 == "relevant" else [])
                d = cluster.f1(pos2) - f1_h1
                if d > best_next:
                    best_next = d
            f["oracle_depth2_delta"] = (f1_h1 - base_f1) + best_next
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    clusters = []
    for v in VIDEOS:
        for q in (QUERY_VULN, QUERY_DRIVER):
            clusters.append(Cluster(v, q))

    budgets_use = (5, 10, 20) if args.quick else BUDGETS
    seeds_use = (0,) if args.quick else (0, 1, 2)
    policies = ["uniform", "top_proxy", "coverage_first", "positive_yield_greedy",
                "relation_greedy", "random_legal"]
    all_rows = []
    approx_checks = []
    t0 = time.time()

    for cl in clusters:
        for pol in policies:
            for budget in budgets_use:
                for seed in seeds_use:
                    rng = random.Random(f"{cl.video}:{cl.query}:{pol}:{budget}:{seed}")
                    if pol == "uniform":
                        order = dyadic_order(cl.unit_ids, rng)
                    elif pol == "top_proxy":
                        order = top_proxy_order(cl)
                    elif pol == "coverage_first":
                        order = coverage_first_order(cl, rng, budget)
                    elif pol == "positive_yield_greedy":
                        # oracle yield greedy: highest true-yield unit first (full-info; illegal, generator only)
                        order = sorted(cl.unit_ids, key=lambda c: (0 if cl.label(c) == "relevant" else 1, cl.rank[c]))
                    elif pol == "relation_greedy":
                        order = []
                        q, o = [], {}
                        while len(q) < budget:
                            legal = [c for c in cl.unit_ids if c not in q]
                            if not legal: break
                            cand = sorted(legal, key=lambda c: (-cl.scores[c], c))[:50]
                            a = max(cand, key=lambda c: visible_rewards(cl, q, o, c)["visible_reward_r4"])
                            q.append(a); o[a] = cl.label(a); order.append(a)
                        order += [c for c in cl.unit_ids if c not in order]
                    else:  # random_legal
                        order = list(cl.unit_ids); rng.shuffle(order)
                    order = order[:budget]
                    queried, outcomes = [], {}
                    idxs = range(len(order)) if budget <= 20 else [0, 1, 2, 4, 8, 16, 32, budget // 2, budget - 1]
                    for i in idxs:
                        if i >= len(order):
                            continue
                        queried = order[:i]
                        outcomes = {c: cl.label(c) for c in queried}
                        state_id = sha256(json.dumps({"v": cl.video, "q": cl.query, "p": pol,
                                                      "b": budget, "s": seed, "i": i}, sort_keys=True))[:16]
                        legal = [c for c in cl.unit_ids if c not in queried]
                        if not legal:
                            continue
                        # sample action set: top40 proxy + 20 stratified + 10 random
                        top = sorted(legal, key=lambda c: (-cl.scores[c], c))[:40]
                        strat = sorted(legal, key=lambda c: min(abs(cl.intervals[c][1] - t) for t in
                                      [cl.intervals[x][2] for x in queried] + [cl.intervals[x][1] for x in queried] or [0.0]))[:20]
                        random.seed(state_id)
                        rnd = random.sample(legal, min(10, len(legal)))
                        actions = sorted(set(top + strat + rnd))
                        do_terminal = (budget - i) <= 20
                        do_depth2 = (budget - i) <= 10
                        rows = build(cl, queried, outcomes, budget, state_id, actions,
                                     "SAMPLED_TOP40_STRAT20_RAND10", do_terminal, do_depth2, 10)
                        all_rows.extend(rows)
                        # exhaustive check on small states
                        if i == 0 and budget == 5 and len(legal) <= 600 and len(all_rows) < 400000:
                            ex_rows = build(cl, queried, outcomes, budget, state_id + ":EX", legal,
                                            "EXHAUSTIVE", False, False, 0)
                            ex_best = max((r["oracle_eventf1_delta_1step"] for r in ex_rows), default=-1e9)
                            sa_best = max((r["oracle_eventf1_delta_1step"] for r in rows), default=-1e9)
                            approx_checks.append({"video": cl.video, "query": cl.query, "state_id": state_id,
                                                  "n_legal": len(legal), "n_sampled": len(actions),
                                                  "exhaustive_best_delta1": ex_best, "sampled_best_delta1": sa_best,
                                                  "abs_error": abs(ex_best - sa_best)})
        print(f"[{time.time()-t0:.0f}s] cluster {cl.video}/{cl.query} done; rows so far={len(all_rows)}", flush=True)

    # P2-manifest-derived states (both proxies, frozen legal policies)
    p2_budgets = (5, 10) if args.quick else BUDGETS
    for r in load_p2_manifest():
        if int(r["budget"]) not in p2_budgets:
            continue
        cl = next(c for c in clusters if c.video == r["video_id"] and c.query == r["query_id"])
        order = json.loads(r["queried_unit_ids_json"])
        budget = int(r["budget"])
        idxs = range(len(order)) if budget <= 20 else [0, 1, 2, 4, 8, 16, 32, budget // 2, budget - 1]
        for i in idxs:
            if i >= len(order):
                continue
            queried = order[:i]
            outcomes = {c: cl.label(c) for c in queried}
            state_id = "P2:" + r["trace_hash"][:16] + f":{i}"
            legal = [c for c in cl.unit_ids if c not in queried]
            if not legal:
                continue
            top = sorted(legal, key=lambda c: (-cl.scores[c], c))[:40]
            random.seed(state_id)
            rnd = random.sample(legal, min(10, len(legal)))
            actions = sorted(set(top + rnd))
            rows = build(cl, queried, outcomes, budget, state_id, actions,
                         "SAMPLED_TOP40_RAND10", (budget - i) <= 20, (budget - i) <= 10, 10)
            all_rows.extend(rows)
    print(f"[{time.time()-t0:.0f}s] total rows={len(all_rows)} approx_checks={len(approx_checks)}", flush=True)

    df = pd.DataFrame(all_rows)
    if approx_checks:
        pd.DataFrame(approx_checks).to_csv(GATE / "ACTION_VALUE_SAMPLING_CHECK.csv", index=False)
    df.to_parquet(GATE / "ACTION_VALUE_TABLE.parquet", index=False)
    with open(GATE / "ACTION_VALUE_SCHEMA.md", "w") as f:
        f.write("# ACTION_VALUE_TABLE schema\n\n")
        f.write(f"rows={len(df)} generated={time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n")
        f.write("| column | dtype | semantics |\n|---|---|---|\n")
        for col in df.columns:
            f.write(f"| {col} | {df[col].dtype} | see prompt Phase 2 §4/§5 |\n")
        f.write("\n## Isolation notes\n")
        f.write("- visible_* columns are policy-visible; oracle_* columns are evaluator-only.\n")
        f.write("- observed_outcome comes from the frozen cached label grid (full-information table); online policies never see it.\n")
        f.write("- reference_type MODEL_RELATIVE = Q_VULNERABLE full-grid C1 reference (validated 252/252);\n")
        f.write("  MODEL_RELATIVE_PARTIAL_UNION = Q_DRIVER union-known labels, partial reference (diagnostic only).\n")
        f.write("- No 2s/5s semantic outcomes exist; all units are 10s (context_length=10).\n")
    print("ACTION_VALUE_TABLE.parquet + schema written")

def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()

if __name__ == "__main__":
    main()
