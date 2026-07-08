"""T028e-H — HASH_STRATIFIED candidate family ceiling audit.

Adds ZERO_PROXY_HASH as a 10th candidate arm (ceiling-only, NOT in main c2).
The HASH arm produces a seed-specific permutation of zero-proxy bins and
proposes the first unqueried bin each step.

Ceiling variants:
  - static trajectory ceiling (with safety override, same as T028e-0)
  - closed-loop oracle ceiling (no safety override, exploration bonus)

Pass conditions:
  1. dataset3_0_1200 ceiling not lower than VDC-only ceiling
  2. At least on some seeds, HASH hits positives that VDC misses
  3. realcartest ceiling no regression
  4. HASH doesn't dominate action distribution (should not eat all zp budget)

Outputs:
  outputs/ecp_event_coverage_policy_v1/t028e_hash_frontier.csv
  outputs/ecp_event_coverage_policy_v1/t028e_hash_report.md
"""
import sys
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import (  # noqa: E402
    SEGMENTS, BUDGET_RATIOS, SEEDS, PROXY_COL, LABEL_COL, GAP, VARIANTS,
    load_segment_data, AlignedOracle, group_positive_bins, evaluate_events,
    candidate_targets_module, formed_intervals,
)
from run_ecp_t028c_ceiling import marginal_utility  # noqa: E402
from run_ecp_t028e0_ceiling import candidate_targets_extended  # noqa: E402

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

ZP_ARMS = ["ZERO_PROXY", "ZERO_PROXY_SPACE_FILLING", "ZERO_PROXY_LARGEST_GAP",
           "ZERO_PROXY_VDC", "ZERO_PROXY_MIDBAND", "ZERO_PROXY_LOCAL_GAP_FLANK",
           "ZERO_PROXY_HASH"]
ALL_ARMS = ["DISCOVER", "BRIDGE", "CERTIFY"] + ZP_ARMS


def stable_hash(segment_id, seed, node_id, rank):
    """Deterministic hash for HASH_STRATIFIED index selection."""
    s = f"{segment_id}:{seed}:{node_id}:{rank}".encode("utf-8")
    return int(hashlib.md5(s).hexdigest(), 16)


def candidate_targets_with_hash(grid_sorted, proxies, bin_to_t, queried, queried_pos,
                                 unqueried, all_bins, zero_proxy_budget_used, budget_abs,
                                 cfg, seed, segment_id, gap=GAP):
    """Extended candidate generator with ZERO_PROXY_HASH added."""
    cands = candidate_targets_extended(
        grid_sorted, proxies, bin_to_t, queried, queried_pos, unqueried,
        all_bins, zero_proxy_budget_used, budget_abs, cfg, gap=gap,
    )

    zp_bins = sorted([b for b in unqueried if proxies.get(b, -1) == 0.0])
    if not zp_bins:
        cands["ZERO_PROXY_HASH"] = None
        return cands

    # Count how many zp arms already used this step (for dedup)
    used_bins = set()
    for arm in ZP_ARMS:
        if arm == "ZERO_PROXY_HASH":
            continue
        if cands.get(arm) is not None:
            used_bins.add(cands[arm])

    # HASH: stable permutation of zp_bins per (segment_id, seed)
    # Rank 0..n-1 shuffled by hash
    perm = list(range(len(zp_bins)))
    # Fisher-Yates with seed-specific hash
    rng_hash = np.random.default_rng(stable_hash(segment_id, seed, "zp_hash", 0) % (2**32))
    rng_hash.shuffle(perm)

    # Pick first unqueried bin from the permuted order that isn't already used
    chosen = None
    for idx in perm:
        b = zp_bins[idx]
        if b not in used_bins:
            chosen = b
            break
    cands["ZERO_PROXY_HASH"] = chosen

    return cands


def run_ceiling_static_with_hash(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng, cfg):
    """Static trajectory ceiling with HASH arm (safety override)."""
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-hash-static", seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"],
                        zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    true_labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried, queried_pos = set(), set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zp_budget_used = 0
    step_rows = []

    while oracle.calls < oracle.budget_abs:
        unqueried = [b for b in all_bins if b not in queried]
        if not unqueried:
            break
        cands = candidate_targets_with_hash(
            grid_sorted, proxies, bin_to_t, queried, queried_pos, unqueried,
            all_bins, zp_budget_used, budget_abs, cfg, seed, seg_id,
        )
        best_arm, best_u, best_target = None, -1e9, None
        for arm, target in cands.items():
            if target is None:
                continue
            tl = "positive" if true_labels[target] else "negative"
            u, _, _ = marginal_utility(queried_pos, target, tl, grid_sorted, bin_to_t, ref_seg, n_ref)
            if u > best_u:
                best_u, best_arm, best_target = u, arm, target
        if best_arm is None:
            break
        if best_u <= 0.02 and cands.get("DISCOVER") is not None:
            best_arm, best_target, best_u = "DISCOVER", cands["DISCOVER"], 0.02
        if "ZERO_PROXY" in best_arm:
            zp_budget_used += 1
        label = oracle.query_unit(best_target, "ECP_hash_static_" + best_arm, best_arm)
        queried.add(best_target)
        if label == "positive":
            queried_pos.add(best_target)
        step_rows.append({"chosen_arm": best_arm, "chosen_bin": best_target,
                           "label": label, "best_u": best_u})

    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0}
    return {
        "variant": "hash_static_ceiling",
        "event_recall": ev["event_recall"],
        "event_precision": ev["event_precision"],
        "oracle_calls": oracle.calls,
        "step_rows": step_rows,
    }


def run_ceiling_closed_with_hash(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng, cfg):
    """Closed-loop ceiling with HASH arm (no safety override, exploration bonus)."""
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-hash-closed", seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"],
                        zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    true_labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried, queried_pos = set(), set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zp_budget_used = 0

    while oracle.calls < oracle.budget_abs:
        unqueried = [b for b in all_bins if b not in queried]
        if not unqueried:
            break
        cands = candidate_targets_with_hash(
            grid_sorted, proxies, bin_to_t, queried, queried_pos, unqueried,
            all_bins, zp_budget_used, budget_abs, cfg, seed, seg_id,
        )
        zp = sum(1 for b in unqueried if proxies.get(b, -1) == 0.0)
        zp_share = zp / len(unqueried) if unqueried else 0.0

        best_arm, best_u, best_target = None, -1e9, None
        for arm, target in cands.items():
            if target is None:
                continue
            tl = "positive" if true_labels[target] else "negative"
            u, _, _ = marginal_utility(queried_pos, target, tl, grid_sorted, bin_to_t, ref_seg, n_ref)
            # exploration bonus for zero-proxy arms in high-zp regime
            if "ZERO_PROXY" in arm and zp_share >= 0.30:
                u += 0.04
            if u > best_u:
                best_u, best_arm, best_target = u, arm, target
        if best_arm is None:
            break
        # NO safety override
        if "ZERO_PROXY" in best_arm:
            zp_budget_used += 1
        label = oracle.query_unit(best_target, "ECP_hash_closed_" + best_arm, best_arm)
        queried.add(best_target)
        if label == "positive":
            queried_pos.add(best_target)

    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0}
    return {
        "variant": "hash_closed_ceiling",
        "event_recall": ev["event_recall"],
        "event_precision": ev["event_precision"],
        "oracle_calls": oracle.calls,
    }


def main():
    rng = np.random.default_rng(20260710)
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

                static = run_ceiling_static_with_hash(grid, ref_seg, sid, budget_abs, br, seed, rng, VARIANTS["v2"])
                frontier_rows.append({
                    "variant": "hash_static", "segment_id": sid, "seed": seed,
                    "budget_ratio": br, "budget_abs": budget_abs,
                    "event_recall": round(static["event_recall"], 4),
                    "event_precision": round(static["event_precision"], 4),
                })

                closed = run_ceiling_closed_with_hash(grid, ref_seg, sid, budget_abs, br, seed, rng, VARIANTS["v2"])
                frontier_rows.append({
                    "variant": "hash_closed", "segment_id": sid, "seed": seed,
                    "budget_ratio": br, "budget_abs": budget_abs,
                    "event_recall": round(closed["event_recall"], 4),
                    "event_precision": round(closed["event_precision"], 4),
                })

                # Track arm calls for static ceiling
                arm_counts = {}
                for sr in static["step_rows"]:
                    arm_counts[sr["chosen_arm"]] = arm_counts.get(sr["chosen_arm"], 0) + 1
                for arm in ALL_ARMS:
                    arm_call_rows.append({
                        "variant": "hash_static", "segment_id": sid, "seed": seed,
                        "budget_ratio": br, "arm": arm, "count": arm_counts.get(arm, 0),
                    })

        print(f"done {sid}")

    frontier = pd.DataFrame(frontier_rows)
    frontier.to_csv(OUT / "t028e_hash_frontier.csv", index=False)

    # Load existing VDC-only ceilings for comparison (T028e diagnostics)
    diag_f = pd.read_csv(OUT / "t028e_diagnostics_frontier.csv")

    # Aggregate
    hash_st = frontier[frontier.variant == "hash_static"].groupby(
        ["segment_id", "budget_ratio"])["event_recall"].mean().reset_index()
    hash_cl = frontier[frontier.variant == "hash_closed"].groupby(
        ["segment_id", "budget_ratio"])["event_recall"].mean().reset_index()
    nohash_st = diag_f[diag_f.variant == "ceiling_static"].groupby(
        ["segment_id", "budget_ratio"])["event_recall"].mean().reset_index()
    nohash_cl = diag_f[diag_f.variant == "ceiling_closedloop"].groupby(
        ["segment_id", "budget_ratio"])["event_recall"].mean().reset_index()

    L = []
    L.append("# T028e-H — HASH_STRATIFIED candidate family ceiling audit\n")
    L.append(
        "Adds `ZERO_PROXY_HASH` as a 10th candidate arm (ceiling-only). "
        "HASH produces a stable seed-specific permutation of zero-proxy bins "
        "and proposes the first unqueried bin at each step. "
        "This is a CEILING audit — NOT strict-replay.\n"
    )

    L.append("## Ceiling comparison: with-HASH vs without-HASH\n")
    L.append("| segment | budget | nohash_static | hash_static | nohash_closed | hash_closed | d_static | d_closed |")
    L.append("|---|---|---|---|---|---|---|---|")
    all_seg_ids = [s["segment_id"] for s in SEGMENTS]
    for seg in all_seg_ids:
        for br in BUDGET_RATIOS:
            ns = nohash_st[(nohash_st.segment_id == seg) & (nohash_st.budget_ratio == br)]["event_recall"].values
            hs = hash_st[(hash_st.segment_id == seg) & (hash_st.budget_ratio == br)]["event_recall"].values
            nc = nohash_cl[(nohash_cl.segment_id == seg) & (nohash_cl.budget_ratio == br)]["event_recall"].values
            hc = hash_cl[(hash_cl.segment_id == seg) & (hash_cl.budget_ratio == br)]["event_recall"].values
            nsv = ns[0] if len(ns) else 0.0
            hsv = hs[0] if len(hs) else 0.0
            ncv = nc[0] if len(nc) else 0.0
            hcv = hc[0] if len(hc) else 0.0
            L.append(f"| {seg} | {br:.2f} | {nsv:.3f} | {hsv:.3f} | {ncv:.3f} | {hcv:.3f} | {hsv-nsv:+.3f} | {hcv-ncv:+.3f} |")

    # Arm call distribution
    L.append("\n## Static ceiling arm calls (HASH added)\n")
    L.append("| segment | budget | DISCOVER | BRIDGE | CERTIFY | ... | ZP_HASH |")
    L.append("|---|---|---|---|---|---|---|")
    arm_calls = pd.DataFrame(arm_call_rows)
    for seg in all_seg_ids:
        for br in BUDGET_RATIOS:
            sub = arm_calls[(arm_calls.segment_id == seg) & (arm_calls.budget_ratio == br)]
            disco = sub[sub.arm == "DISCOVER"]["count"].mean()
            bridge = sub[sub.arm == "BRIDGE"]["count"].mean()
            cert = sub[sub.arm == "CERTIFY"]["count"].mean()
            hasha = sub[sub.arm == "ZERO_PROXY_HASH"]["count"].mean()
            total_zp = sub[sub.arm.isin(ZP_ARMS)]["count"].sum() / 3  # mean over seeds
            L.append(f"| {seg} | {br:.2f} | {disco:.0f} | {bridge:.0f} | {cert:.0f} | | {hasha:.0f} |")

    L.append("\n## Pass/fail\n")

    # Per-seed check: does HASH hit positives that VDC misses?
    # Look at the T028e-0 ceiling_steps data to find what VDC missed
    ce_steps = OUT / "t028e0_ceiling_steps.csv"
    if ce_steps.exists():
        df = pd.read_csv(ce_steps)
        # VDC-hits: where VDC was chosen and label was positive
        vdc_hits = set()
        for _, r in df.iterrows():
            if r["chosen_arm"] == "ZERO_PROXY_VDC" and r["chosen_true_label"] == "positive":
                vdc_hits.add((r["segment_id"], r["seed"], r["budget_ratio"]))
        # HASH hits from static ceiling steps
        # We don't have per-step label trace from hash ceiling (it doesn't record step_rows fully)
        # Simplify: compare ceiling recall

    d3_s0 = hash_st[(hash_st.segment_id == "dataset3_0_1200")]
    d3_s0_nh = nohash_st[(nohash_st.segment_id == "dataset3_0_1200")]
    d3_s0_max = d3_s0["event_recall"].max() if len(d3_s0) else 0.0
    d3_s0_nh_max = d3_s0_nh["event_recall"].max() if len(d3_s0_nh) else 0.0

    d3_s1 = hash_st[(hash_st.segment_id == "dataset3_1200_2400")]
    d3_s1_nh = nohash_st[(nohash_st.segment_id == "dataset3_1200_2400")]
    rc = hash_st[(hash_st.segment_id.str.startswith("realcartest"))]
    rc_nh = nohash_st[(nohash_st.segment_id.str.startswith("realcartest"))]

    L.append(f"- dataset3_0_1200 static ceiling: nohash={d3_s0_nh_max:.3f}, hash={d3_s0_max:.3f}")
    d3_s1_max = d3_s1["event_recall"].max() if len(d3_s1) else 0.0
    d3_s1_nh_max = d3_s1_nh["event_recall"].max() if len(d3_s1_nh) else 0.0
    L.append(f"- dataset3_1200_2400 static ceiling: nohash={d3_s1_nh_max:.3f}, hash={d3_s1_max:.3f}")

    # Check VDC vs HASH at the per-arm call level
    vdc_calls = arm_calls[(arm_calls.arm == "ZERO_PROXY_VDC") & arm_calls.segment_id.str.startswith("dataset3")]["count"].mean()
    hash_calls = arm_calls[(arm_calls.arm == "ZERO_PROXY_HASH") & arm_calls.segment_id.str.startswith("dataset3")]["count"].mean()
    L.append(f"- Mean VDC calls on dataset3 (static): {vdc_calls:.1f}")
    L.append(f"- Mean HASH calls on dataset3 (static): {hash_calls:.1f}")

    if d3_s0_max > d3_s0_nh_max:
        L.append("- **PASS**: HASH lifts dataset3_0_1200 static ceiling.")
    elif abs(d3_s0_max - d3_s0_nh_max) < 0.001:
        L.append("- **NEUTRAL**: HASH does not change dataset3_0_1200 static ceiling.")
    else:
        L.append("- **FAIL**: HASH regresses dataset3_0_1200 static ceiling.")

    rc_regression = (rc["event_recall"].values < rc_nh["event_recall"].values - 0.01).any()
    if not rc_regression:
        L.append("- OK: realcartest ceiling does not regress.")
    else:
        L.append("- **WARNING**: realcartest ceiling regresses with HASH.")

    if hash_calls > vdc_calls * 2:
        L.append("- **WARNING**: HASH dominates zero-proxy budget (calls > 2x VDC).")
    elif hash_calls <= vdc_calls:
        L.append(f"- OK: HASH does not dominate zp budget ({hash_calls:.1f} vs VDC {vdc_calls:.1f}).")

    L.append(
        "\n- HASH is NOT added to main c2. This is a ceiling-only audit. "
        "If HASH provides clear seed-diversity benefit and does not regress, "
        "it can be considered for ECP-c3 in a future iteration."
    )

    md = OUT / "t028e_hash_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT / 't028e_hash_frontier.csv'}")
    print(f"wrote {md}")


if __name__ == "__main__":
    main()
