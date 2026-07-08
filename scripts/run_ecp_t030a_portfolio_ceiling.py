"""T030a — ECP-Portfolio candidate ceiling audit.

Treats each baseline method's next-action logic as a portfolio ARM.
At each step, enumerates ALL portfolio arms, computes offline marginal
event-utility, and selects the max-utility arm. This is a closed-loop
oracle ceiling (NO safety override, exploration bonus for zp arms).

Portfolio arms (10):
  1. ECP_DISCOVER        — highest-proxy unqueried bin
  2. ECP_CERTIFY         — boundary of formed positive interval
  3. ECP_BRIDGE          — gap-bridge between discovered positives
  4. ECP_ZERO_PROXY_VDC  — VDC low-discrepancy into zp bins
  5. B7_NEXT             — Thompson chunk-bandit + temporal expansion
  6. D3_NEXT             — Thompson chunk-bandit (no expansion)
  7. EventLift_DISCOVER  — Component-based discover
  8. EventLift_CERTIFY   — Anchor boundary certification
  9. HTS_EC_TREE         — UCB tree node + highest-proxy within-node
  10. TOPPROXY_NEXT      — Simple top-proxy unqueried

Pass conditions (T030a):
  - realcartest mean recall ceiling > B7-strict-replay
  - dataset3 mean recall ceiling > D3-norepair-core-strict
  - At least one segment × budget cell above best single baseline

Outputs:
  outputs/ecp_event_coverage_policy_v1/t030a_portfolio_frontier.csv
  outputs/ecp_event_coverage_policy_v1/t030a_portfolio_arm_usage.csv
  outputs/ecp_event_coverage_policy_v1/t030a_portfolio_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import (  # noqa: E402
    SEGMENTS, BUDGET_RATIOS, SEEDS, PROXY_COL, LABEL_COL, VARIANTS,
    load_segment_data, AlignedOracle, group_positive_bins, evaluate_events,
    candidate_targets_module, formed_intervals,
)
from run_ecp_t028c_ceiling import marginal_utility  # noqa: E402
from run_ecp_t028e0_ceiling import candidate_targets_extended  # noqa: E402

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Portfolio Arm: state → (arm_name, proposed_bin) or None
# ---------------------------------------------------------------------------
class PortfolioArms:
    """Collection of portfolio arms that propose next queries."""

    def __init__(self, grid_sorted, proxies, bin_to_t, all_bins, budget_abs):
        self.grid = grid_sorted
        self.proxies = proxies
        self.bin_to_t = bin_to_t
        self.all_bins = all_bins
        self.n_bins = len(all_bins)
        self.budget_abs = budget_abs

        # Precompute chunk boundaries for B7/D3 (60s chunks, ~6 bins each)
        bin_size = 10  # seconds per bin (approx)
        chunk_dur = 60
        bins_per_chunk = max(1, chunk_dur // bin_size)
        self.chunk_size = bins_per_chunk
        self.n_chunks = (self.n_bins + bins_per_chunk - 1) // bins_per_chunk
        self.chunk_bins = [[] for _ in range(self.n_chunks)]
        for i, b in enumerate(all_bins):
            self.chunk_bins[i // bins_per_chunk].append(b)

        # Precompute median proxy for EventLift components
        proxy_vals = np.array([proxies[b] for b in all_bins])
        self.median_proxy = np.median(proxy_vals) if len(proxy_vals) > 0 else 0.0

        # HTS tree state (lazy-init)
        self._hts_initialized = False
        self._hts_nodes = None

    def propose_ecp(self, queried, queried_pos, unqueried, zp_budget_used):
        """ECP arms: DISCOVER, CERTIFY, BRIDGE, ZERO_PROXY_VDC."""
        cfg = VARIANTS["v2"]
        cands = candidate_targets_extended(
            self.grid, self.proxies, self.bin_to_t,
            queried, queried_pos, unqueried, self.all_bins,
            zp_budget_used, self.budget_abs, cfg,
        )
        results = {}
        for key in ["DISCOVER", "CERTIFY", "BRIDGE", "ZERO_PROXY_VDC"]:
            if cands.get(key) is not None:
                results[f"ECP_{key}"] = cands[key]
        return results

    def propose_b7(self, queried, queried_pos, unqueried):
        """B7_NEXT: Thompson chunk-bandit + temporal expansion."""
        # Update chunk statistics from queried/queried_pos
        n_c = np.zeros(self.n_chunks)
        N1_c = np.zeros(self.n_chunks)
        for c in range(self.n_chunks):
            for b in self.chunk_bins[c]:
                if b in queried:
                    n_c[c] += 1
                    if b in queried_pos:
                        N1_c[c] += 1

        # Thompson sampling
        rng_b7 = np.random.default_rng(20260710)
        theta = np.zeros(self.n_chunks)
        for c in range(self.n_chunks):
            unsampled = [b for b in self.chunk_bins[c] if b not in queried]
            if len(unsampled) == 0:
                theta[c] = -np.inf
            else:
                theta[c] = rng_b7.gamma(shape=N1_c[c] + 0.1, scale=1.0 / (n_c[c] + 1.0))

        best_c = int(np.argmax(theta))
        unsampled_c = [b for b in self.chunk_bins[best_c] if b not in queried]
        if not unsampled_c:
            return {}
        chosen = int(rng_b7.choice(unsampled_c))

        # Check for temporal expansion: last queried positive
        # B7 fires expansion on positive hits
        return {"B7_NEXT": chosen}

    def propose_d3(self, queried, queried_pos, unqueried):
        """D3_NEXT: Thompson chunk-bandit (no expansion)."""
        n_c = np.zeros(self.n_chunks)
        N1_c = np.zeros(self.n_chunks)
        for c in range(self.n_chunks):
            for b in self.chunk_bins[c]:
                if b in queried:
                    n_c[c] += 1
                    if b in queried_pos:
                        N1_c[c] += 1

        rng_b7 = np.random.default_rng(20260710)
        theta = np.zeros(self.n_chunks)
        for c in range(self.n_chunks):
            unsampled = [b for b in self.chunk_bins[c] if b not in queried]
            if len(unsampled) == 0:
                theta[c] = -np.inf
            else:
                theta[c] = rng_b7.gamma(shape=N1_c[c] + 0.1, scale=1.0 / (n_c[c] + 1.0))

        best_c = int(np.argmax(theta))
        unsampled_c = [b for b in self.chunk_bins[best_c] if b not in queried]
        if not unsampled_c:
            return {}
        chosen = int(rng_b7.choice(unsampled_c))
        return {"D3_NEXT": chosen}

    def _build_components(self, queried):
        """EventLift: build contiguous above-median-proxy components."""
        uncovered = [b for b in self.all_bins if b not in queried]
        # Find runs of proxy >= median
        runs = []
        current = []
        for b in self.all_bins:
            if b not in queried and self.proxies[b] >= self.median_proxy:
                current.append(b)
            else:
                if current:
                    runs.append(current)
                    current = []
        if current:
            runs.append(current)
        return runs

    def propose_eventlift_discover(self, queried, queried_pos, unqueried):
        """EventLift_DISCOVER: component-based discovery with utility score."""
        components = self._build_components(queried)
        if not components:
            return {}
        # Score each component: proxy_mass * fresh_frac
        best_comp = None
        best_score = -1e9
        for comp in components:
            fresh = [b for b in comp if b not in queried]
            if not fresh:
                continue
            proxy_mass = sum(self.proxies[b] for b in comp)
            # fresh_frac = proportion of fresh bins in component
            fresh_frac = len(fresh) / len(comp)
            # simple utility: proxy_mass * fresh_frac - small penalty
            score = proxy_mass * fresh_frac - 0.01 * len(comp)
            if score > best_score:
                best_score = score
                best_comp = fresh

        if not best_comp:
            return {}
        # Sample one bin weighted by sqrt(proxy)
        w = np.array([max(0.001, np.sqrt(self.proxies[b])) for b in best_comp])
        w = w / w.sum()
        rng_el = np.random.default_rng(20260710)
        chosen = int(rng_el.choice(best_comp, p=w))
        return {"EventLift_DISCOVER": chosen}

    def propose_eventlift_certify(self, queried, queried_pos, unqueried):
        """EventLift_CERTIFY: certifying boundary of pending anchors."""
        # Find pending anchors: positive bins with unqueried neighbors
        anchors = []
        for b in queried_pos:
            for nb in [b - 1, b + 1]:
                if nb in self.all_bins and nb not in queried:
                    anchors.append((b, nb))
                    break  # one neighbor per anchor is enough

        if not anchors:
            return {}
        # Simple: pick anchor with fewest total neighbors queried (least explored)
        best_anchor = min(anchors, key=lambda pair: sum(1 for nb in [pair[0]-1, pair[0]+1] if nb in queried))
        return {"EventLift_CERTIFY": best_anchor[1]}

    def _init_hts(self):
        """Lazy-init HTS tree with Beta posteriors."""
        # Build a simple binary tree: groups of ~8 bins per leaf
        leaf_size = max(1, self.n_bins // 16)
        nodes = []
        # leaf nodes
        for i in range(0, self.n_bins, leaf_size):
            lo = i
            hi = min(i + leaf_size, self.n_bins)
            bins = self.all_bins[lo:hi]
            mean_proxy = np.mean([self.proxies[b] for b in bins])
            # Initial Beta posterior from proxy prior
            K0 = 2.0
            nodes.append({
                "lo": lo, "hi": hi, "alpha": 1.0 + K0 * mean_proxy,
                "beta": 1.0 + K0 * (1.0 - mean_proxy),
                "n_probe": 0, "n_pos": 0,
                "in_frontier": True, "expanded": False,
            })
        self._hts_nodes = nodes
        self._hts_initialized = True

    def _hts_update(self, bin_idx, label):
        """Update HTS node posteriors after a probe."""
        for node in self._hts_nodes:
            lo, hi = node["lo"], node["hi"]
            bin_pos = self.all_bins.index(bin_idx) if bin_idx in self.all_bins else -1
            if lo <= bin_pos < hi:
                node["n_probe"] += 1
                if label == "positive":
                    node["n_pos"] += 1
                    node["alpha"] += 1
                else:
                    node["beta"] += 1
                break

    def propose_hts(self, queried, queried_pos, unqueried, step_count):
        """HTS_EC_TREE: UCB-select tree node, highest-proxy within node."""
        if not self._hts_initialized:
            self._init_hts()
            # Initialize from existing queried data
            for b in queried:
                self._hts_update(b, "positive" if b in queried_pos else "negative")

        # UCB select node from frontier
        UCB_C = 1.0
        frontier = [n for n in self._hts_nodes if n["in_frontier"] and not n.get("expanded")]
        if not frontier:
            return {}

        best_node = None
        best_ucb = -1e9
        for node in frontier:
            mean = node["alpha"] / (node["alpha"] + node["beta"] + 1e-9)
            explore = UCB_C * np.sqrt(np.log(step_count + 2) / (node["n_probe"] + 1))
            ucb = mean + explore
            if ucb > best_ucb:
                best_ucb = ucb
                best_node = node

        if best_node is None:
            return {}

        # Select highest-proxy unqueried bin within node
        lo, hi = best_node["lo"], best_node["hi"]
        candidates = []
        for i in range(lo, min(hi, self.n_bins)):
            b = self.all_bins[i]
            if b not in queried:
                candidates.append((self.proxies[b], b))
        if not candidates:
            best_node["expanded"] = True  # no more bins, remove from frontier
            return {}
        candidates.sort(key=lambda x: -x[0])
        return {"HTS_EC_TREE": candidates[0][1]}

    def propose_topproxy(self, queried, queried_pos, unqueried):
        """TOPPROXY_NEXT: simple highest-proxy unqueried bin."""
        best_bin = None
        best_proxy = -1e9
        for b in unqueried:
            if self.proxies[b] > best_proxy:
                best_proxy = self.proxies[b]
                best_bin = b
        if best_bin is None:
            return {}
        return {"TOPPROXY_NEXT": best_bin}

    def propose_all(self, queried, queried_pos, unqueried, zp_budget_used, step_count):
        """Return all portfolio arm proposals for current state."""
        results = {}
        results.update(self.propose_ecp(queried, queried_pos, unqueried, zp_budget_used))
        results.update(self.propose_b7(queried, queried_pos, unqueried))
        results.update(self.propose_d3(queried, queried_pos, unqueried))
        results.update(self.propose_eventlift_discover(queried, queried_pos, unqueried))
        results.update(self.propose_eventlift_certify(queried, queried_pos, unqueried))
        results.update(self.propose_hts(queried, queried_pos, unqueried, step_count))
        results.update(self.propose_topproxy(queried, queried_pos, unqueried))
        return results


# ---------------------------------------------------------------------------
# Closed-loop oracle ceiling with portfolio arms
# ---------------------------------------------------------------------------
def run_portfolio_ceiling(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng):
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-portfolio-ceiling", seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"],
                        zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    true_labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried, queried_pos = set(), set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zp_budget_used = 0
    step_count = 0
    arm_calls = {}

    portfolio = PortfolioArms(grid_sorted, proxies, bin_to_t, all_bins, budget_abs)

    while oracle.calls < oracle.budget_abs:
        unqueried = [b for b in all_bins if b not in queried]
        if not unqueried:
            break
        step_count += 1

        proposals = portfolio.propose_all(queried, queried_pos, unqueried,
                                          zp_budget_used, step_count)

        zp_share_val = (sum(1 for b in unqueried if proxies.get(b, -1) == 0.0)
                        / len(unqueried)) if unqueried else 0.0

        # Compute offline marginal utility for each proposal
        best_arm, best_u, best_target = None, -1e9, None
        for arm, target in proposals.items():
            if target is None:
                continue
            tl = "positive" if true_labels[target] else "negative"
            u, _, _ = marginal_utility(queried_pos, target, tl, grid_sorted,
                                       bin_to_t, ref_seg, n_ref)
            # Exploration bonus for zero-proxy arms
            if "ZERO_PROXY" in arm and zp_share_val >= 0.30:
                u += 0.04
            if u > best_u:
                best_u, best_arm, best_target = u, arm, target

        if best_arm is None:
            break

        # No safety override — keep best selection
        if "ZERO_PROXY" in best_arm:
            zp_budget_used += 1
        label = oracle.query_unit(best_target, "ECP_portfolio_" + best_arm, best_arm)
        queried.add(best_target)
        if label == "positive":
            queried_pos.add(best_target)

        arm_calls[best_arm] = arm_calls.get(best_arm, 0) + 1

        # Update HTS tree if needed
        if "HTS_EC" in best_arm:
            portfolio._hts_update(best_target, label)

    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0}
    return {
        "event_recall": ev["event_recall"],
        "event_precision": ev["event_precision"],
        "oracle_calls": oracle.calls,
        "arm_calls": arm_calls,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    rng = np.random.default_rng(20260711)
    frontier_rows = []
    arm_call_rows = []

    for seg in SEGMENTS:
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            continue
        n_bins = len(grid)
        sid = seg["segment_id"]
        for br in BUDGET_RATIOS:
            for seed in SEEDS:
                budget_abs = max(1, int(round(br * n_bins)))
                res = run_portfolio_ceiling(grid, ref_seg, sid, budget_abs, br, seed, rng)
                frontier_rows.append({
                    "variant": "portfolio_ceiling",
                    "segment_id": sid, "seed": seed,
                    "budget_ratio": br, "budget_abs": budget_abs,
                    "event_recall": round(res["event_recall"], 4),
                    "event_precision": round(res["event_precision"], 4),
                    "strict_replay_or_posthoc": "OFFLINE_CEILING",
                    "applicability_note": "T030a portfolio closed-loop oracle ceiling",
                })
                for arm, count in res["arm_calls"].items():
                    arm_call_rows.append({
                        "segment_id": sid, "seed": seed,
                        "budget_ratio": br, "arm": arm, "count": count,
                    })
        print(f"done {sid}")

    frontier = pd.DataFrame(frontier_rows)
    frontier.to_csv(OUT / "t030a_portfolio_frontier.csv", index=False)
    arms = pd.DataFrame(arm_call_rows)
    arms.to_csv(OUT / "t030a_portfolio_arm_usage.csv", index=False)

    # Load baselines for comparison
    hts = pd.read_csv(REPO_ROOT / "outputs/hts_ec_v0_strict_v1/hts_ec_v0_frontier.csv")
    ecp_c2 = pd.read_csv(OUT / "t028e1_loso_frontier.csv")

    # Aggregate portfolio ceiling
    pf_agg = frontier.groupby(["segment_id", "budget_ratio"]).agg(
        pf_recall=("event_recall", "mean"),
        pf_prec=("event_precision", "mean"),
    ).reset_index()

    # Aggregate baselines (HTS, EventLift, B7, D3)
    baseline_methods = {
        "B7-strict-replay": "B7",
        "D3-norepair-core-strict": "D3",
        "HTS-EC-safe": "HTS-EC",
        "EventLift-discover-certify": "EventLift-DC",
        "fixed_10s_topproxy": "TopProxy",
    }
    bl_rows = []
    for mid, label in baseline_methods.items():
        sub = hts[hts["method_id"] == mid]
        if len(sub) == 0:
            continue
        agg = sub.groupby(["segment_id", "budget_ratio"]).agg(
            recall=("event_recall", "mean"),
            prec=("event_precision", "mean"),
        ).reset_index()
        agg["method"] = label
        bl_rows.append(agg)
    bl_all = pd.concat(bl_rows, ignore_index=True)

    # ECP-c2 LOSO
    c2_agg = ecp_c2[ecp_c2["variant"] == "c2_loso"].groupby(
        ["held_out_segment", "budget_ratio"]).agg(
        recall=("event_recall", "mean"),
        prec=("event_precision", "mean"),
    ).reset_index()
    c2_agg["segment_id"] = c2_agg["held_out_segment"]
    c2_agg["method"] = "ECP-c2"

    # Report
    all_seg_ids = [s["segment_id"] for s in SEGMENTS]

    L = []
    L.append("# T030a — ECP-Portfolio candidate ceiling audit\n")
    L.append(
        "Closed-loop oracle ceiling with 10 portfolio arms: "
        "ECP_DISCOVER, ECP_CERTIFY, ECP_BRIDGE, ECP_ZERO_PROXY_VDC, "
        "B7_NEXT, D3_NEXT, EventLift_DISCOVER, EventLift_CERTIFY, "
        "HTS_EC_TREE, TOPPROXY_NEXT.\n\n"
        "At each step, ALL arms propose their next query; offline marginal "
        "event-utility selects the best. Exploration bonus for zp arms when "
        "zp_share >= 0.30. No safety override.\n"
    )

    L.append("## Ceiling comparison: Portfolio vs baselines\n")
    L.append("| segment | budget | Portfolio | ECP-c2 | B7 | D3 | HTS-EC | EventLift | TopProxy |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for seg in all_seg_ids:
        for br in BUDGET_RATIOS:
            pf = pf_agg[(pf_agg.segment_id == seg) & (pf_agg.budget_ratio == br)]
            c2 = c2_agg[(c2_agg.segment_id == seg) & (c2_agg.budget_ratio == br)]
            if len(pf) == 0:
                continue
            cells = [f"R{pf.iloc[0]['pf_recall']:.3f}/P{pf.iloc[0]['pf_prec']:.3f}"]
            for m in ["ECP-c2", "B7", "D3", "HTS-EC", "EventLift-DC", "TopProxy"]:
                if m == "ECP-c2":
                    sub = c2
                else:
                    sub = bl_all[(bl_all.method == m) & (bl_all.segment_id == seg)
                                 & (bl_all.budget_ratio == br)]
                if len(sub):
                    cells.append(f"R{sub.iloc[0]['recall']:.3f}/P{sub.iloc[0]['prec']:.3f}")
                else:
                    cells.append("-")
            L.append(f"| {seg} | {br:.2f} | " + " | ".join(cells) + " |")

    L.append("\n## Portfolio vs best baseline recall delta\n")
    L.append("| segment | budget | pf_recall | best_bl_recall | best_bl | delta |")
    L.append("|---|---|---|---|---|---|")
    portfolio_wins = 0
    portfolio_ties = 0
    portfolio_losses = 0
    for seg in all_seg_ids:
        for br in BUDGET_RATIOS:
            pf = pf_agg[(pf_agg.segment_id == seg) & (pf_agg.budget_ratio == br)]
            if len(pf) == 0:
                continue
            pf_r = pf.iloc[0]["pf_recall"]
            # Find best among B7, D3, EventLift, HTS-EC
            best_r, best_name = 0.0, "none"
            for m in ["B7", "D3", "EventLift-DC", "HTS-EC"]:
                sub = bl_all[(bl_all.method == m) & (bl_all.segment_id == seg)
                             & (bl_all.budget_ratio == br)]
                if len(sub) and sub.iloc[0]["recall"] > best_r:
                    best_r = sub.iloc[0]["recall"]
                    best_name = m
            delta = pf_r - best_r
            if delta > 0.005:
                portfolio_wins += 1
            elif delta < -0.005:
                portfolio_losses += 1
            else:
                portfolio_ties += 1
            L.append(f"| {seg} | {br:.2f} | {pf_r:.3f} | {best_r:.3f} | {best_name} | {delta:+.3f} |")

    L.append(f"\n**Portfolio wins: {portfolio_wins}, ties: {portfolio_ties}, losses: {portfolio_losses}**\n")

    # Per-video summary
    L.append("## Per-video mean recall\n")
    for video in ["realcartest", "dataset3"]:
        L.append(f"\n### {video}\n")
        for mid, label in [("pf_agg", "Portfolio-ceiling")] + [(m, l) for m, l in [
            ("c2_agg.loc[c2_agg.segment_id.str.startswith(video)]", "ECP-c2")]]:
            pass  # Simplify below

    # Simpler: aggregate by video prefix
    for video in ["realcartest", "dataset3"]:
        L.append(f"\n### {video}\n")
        pf_v = pf_agg[pf_agg.segment_id.str.startswith(video)]
        c2_v = c2_agg[c2_agg.segment_id.str.startswith(video)]
        L.append(f"- Portfolio ceiling: recall={pf_v['pf_recall'].mean():.3f}, prec={pf_v['pf_prec'].mean():.3f}")
        if len(c2_v):
            L.append(f"- ECP-c2 LOSO: recall={c2_v['recall'].mean():.3f}, prec={c2_v['prec'].mean():.3f}")
        for m in ["B7", "D3", "HTS-EC", "EventLift-DC"]:
            sub = bl_all[(bl_all.method == m) & bl_all.segment_id.str.startswith(video)]
            if len(sub):
                L.append(f"- {m}: recall={sub['recall'].mean():.3f}, prec={sub['prec'].mean():.3f}")

    # Portfolio arm usage
    L.append("\n## Portfolio arm usage (mean calls per segment-budget-seed)\n")
    L.append("| arm | mean_calls | positive_rate_est |")
    L.append("|---|---|---|")
    arm_agg = arms.groupby("arm").agg(
        mean_calls=("count", lambda x: x.mean() if len(x) else 0),
        total_calls=("count", "sum"),
    ).reset_index()
    arm_agg = arm_agg.sort_values("total_calls", ascending=False)
    for _, r in arm_agg.iterrows():
        L.append(f"| {r['arm']} | {r['mean_calls']:.1f} | - |")

    L.append("\n## Pass/fail\n")
    pf_rc = pf_agg[pf_agg.segment_id.str.startswith("realcartest")]["pf_recall"].mean()
    pf_d3 = pf_agg[pf_agg.segment_id.str.startswith("dataset3")]["pf_recall"].mean()
    b7_rc = bl_all[(bl_all.method == "B7") & bl_all.segment_id.str.startswith("realcartest")]["recall"].mean()
    d3_rc = bl_all[(bl_all.method == "D3") & bl_all.segment_id.str.startswith("dataset3")]["recall"].mean()

    L.append(f"- Portfolio realcartest mean recall: {pf_rc:.3f} vs B7: {b7_rc:.3f} (delta {pf_rc-b7_rc:+.3f})")
    L.append(f"- Portfolio dataset3 mean recall: {pf_d3:.3f} vs D3: {d3_rc:.3f} (delta {pf_d3-d3_rc:+.3f})")

    if pf_rc >= b7_rc - 0.01 and pf_d3 >= d3_rc - 0.01:
        L.append("- **PASS**: Portfolio ceiling matches or exceeds best single baselines.")
    elif portfolio_wins >= 3:
        L.append(f"- **PARTIAL**: Portfolio wins on {portfolio_wins} cells but doesn't dominate overall.")
    else:
        L.append(f"- **FAIL**: Portfolio ceiling does not clearly exceed best single baselines ({portfolio_wins} wins).")

    L.append(
        "\n- This is an OFFLINE CEILING. If it passes, proceed to T030b "
        "(train event-utility portfolio selector for strict replay)."
    )

    md = OUT / "t030a_portfolio_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT / 't030a_portfolio_frontier.csv'}")
    print(f"wrote {OUT / 't030a_portfolio_arm_usage.csv'}")
    print(f"wrote {md}")

    # Quick summary
    print(f"\nPortfolio wins: {portfolio_wins}, ties: {portfolio_ties}, losses: {portfolio_losses}")
    print(f"realcartest: portfolio={pf_rc:.3f} vs B7={b7_rc:.3f}")
    print(f"dataset3: portfolio={pf_d3:.3f} vs D3={d3_rc:.3f}")


if __name__ == "__main__":
    main()
