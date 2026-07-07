#!/usr/bin/env python3
"""HTS-EC-v0 Phase 2A-RP preflight: Robust Probing / StagRepMix diagnostics.

Runs a minimal ablation on 6 segments × 3 budgets × 3 seeds:
  - HTS-EC-safe                     (baseline, flags off)
  - HTS-EC-safe-shadow-stag         (shadow logging only; must equal safe)
  - HTS-EC-safe-StagRepMix-force    (eligible stagnant node gets bounded
                                     diverse probe; force policy)

Outputs (in outputs/hts_ec_v0_phase2a_rp_preflight_v1/):
  - hts_ec_v0_frontier.csv
  - hts_ec_v0_call_trace.csv
  - hts_ec_v0_diagnostics.csv
  - hts_ec_v0_probe_log.csv
  - hts_ec_v0_scheduler_decision_log.csv

This is NOT a full Phase 2A (no ELFine / combo ablation, no SOTA claim).
Purpose: verify G0–G5 before adding ELFine.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from garc_eval.hts_ec_v0 import HtsEcV0Runner, HtsEcV0Config
from run_aligned_baselines_v1 import (
    load_segment_data, SEGMENTS, PROXY_COL, LABEL_COL,
    AlignedOracle, group_positive_bins, evaluate_events,
)

OUT = REPO / "outputs" / "hts_ec_v0_phase2a_rp_preflight_v1"
OUT.mkdir(parents=True, exist_ok=True)

IOU_THRESH = 0.3
BUDGET_RATIOS = [0.10, 0.20, 0.30]
SEEDS = [0, 1, 2]

VARIANTS = {
    "HTS-EC-safe": HtsEcV0Config(
        method_id="HTS-EC-safe",
        detector_posterior_thresh=0.85,
        detector_k_min=4,
        tree_preference_bonus=0.1,
        posterior_prune_thresh=0.15,
    ),
    "HTS-EC-safe-shadow-stag": HtsEcV0Config(
        method_id="HTS-EC-safe-shadow-stag",
        detector_posterior_thresh=0.85,
        detector_k_min=4,
        tree_preference_bonus=0.1,
        posterior_prune_thresh=0.15,
        use_node_stagnation=True,   # shadow predicate + logs only
        use_stag_repmix=False,
    ),
    "HTS-EC-safe-StagRepMix-force": HtsEcV0Config(
        method_id="HTS-EC-safe-StagRepMix-force",
        detector_posterior_thresh=0.85,
        detector_k_min=4,
        tree_preference_bonus=0.1,
        posterior_prune_thresh=0.15,
        use_node_stagnation=True,
        use_stag_repmix=True,
        stagmix_priority_policy="inf_when_eligible",
        stagmix_strategy_set="legacy",
    ),
    "HTS-EC-safe-StagRepMix-force-gap_flank_v2": HtsEcV0Config(
        method_id="HTS-EC-safe-StagRepMix-force-gap_flank_v2",
        detector_posterior_thresh=0.85,
        detector_k_min=4,
        tree_preference_bonus=0.1,
        posterior_prune_thresh=0.15,
        use_node_stagnation=True,
        use_stag_repmix=True,
        stagmix_priority_policy="inf_when_eligible",
        stagmix_strategy_set="gap_flank_v2",
        stagmix_gap_flank_radius=3,
    ),
}


def flat_topproxy_recall(labels, proxies, budget_abs, grid, ref_events):
    """Fixed 10s top-proxy baseline."""
    probe_order = np.argsort(-proxies, kind="stable")
    pos_bins = set()
    for i in range(min(budget_abs, len(labels))):
        b = int(probe_order[i])
        if labels[b] == 1:
            pos_bins.add(b)
    intervals = group_positive_bins(sorted(pos_bins), grid)
    return evaluate_events(intervals, ref_events), intervals


def main():
    all_frontier = []
    all_trace = []
    all_diag = []
    all_probe_log = []
    all_sched_log = []

    # For G0 invariance: store safe result per (seg, br, seed).
    safe_results = {}

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid, ref_seg, err = load_segment_data(seg)
        if err:
            print(f"SKIP {seg_id}: {err}")
            continue
        grid = grid.sort_values("bin_idx").reset_index(drop=True)
        n_bins = len(grid)
        labels = grid[LABEL_COL].astype(int).values
        proxies = grid[PROXY_COL].values

        for br in BUDGET_RATIOS:
            budget_abs = max(1, int(round(br * n_bins)))

            # Flat top-proxy baseline for context
            flat_ev, flat_intervals = flat_topproxy_recall(
                labels, proxies, budget_abs, grid, ref_seg)
            all_frontier.append({
                "segment_id": seg_id,
                "method_id": "fixed_10s_topproxy",
                "seed": 0,
                "budget_abs": budget_abs,
                "budget_ratio": br,
                "oracle_calls_total": min(budget_abs, n_bins),
                "returned_intervals": str(flat_intervals),
                "event_precision": flat_ev["event_precision"],
                "event_recall": flat_ev["event_recall"],
                "unique_event_coverage": flat_ev["unique_event_coverage"],
                "strict_replay_or_posthoc": "strict_replay",
                "online_uses_event_id": False,
                "can_be_main_comparison": False,
                "applicability_note": "flat proxy-ranked top-k, strict-replay",
            })

            for variant_name, config in VARIANTS.items():
                for seed in SEEDS:
                    oracle = AlignedOracle(
                        grid, seg_id, variant_name, seed, budget_abs, br)
                    runner = HtsEcV0Runner(config)
                    result = runner.run(
                        grid, oracle, budget_abs, seed=seed,
                        run_id=variant_name, segment_id=seg_id,
                        budget_config=str(br))

                    ev = evaluate_events(result["intervals"], ref_seg)

                    oracle.assert_no_event_id()
                    assert oracle.calls <= budget_abs, \
                        f"Budget violation: {oracle.calls} > {budget_abs}"

                    key = (seg_id, br, seed)
                    if variant_name == "HTS-EC-safe":
                        safe_results[key] = {
                            "pos_bins": result["pos_bins"],
                            "calls": result["calls"],
                            "intervals": result["intervals"],
                        }

                    row = {
                        "segment_id": seg_id,
                        "method_id": variant_name,
                        "seed": seed,
                        "budget_abs": budget_abs,
                        "budget_ratio": br,
                        "oracle_calls_total": oracle.calls,
                        "returned_intervals": str(result["intervals"]),
                        "event_precision": ev["event_precision"],
                        "event_recall": ev["event_recall"],
                        "unique_event_coverage": ev["unique_event_coverage"],
                        "strict_replay_or_posthoc": "strict_replay",
                        "online_uses_event_id": False,
                        "can_be_main_comparison": False,
                        "applicability_note": (
                            f"Phase 2A-RP preflight, flags="
                            f"stag({int(config.use_node_stagnation)})"
                            f"/repmix({int(config.use_stag_repmix)}), "
                            f"policy={config.stagmix_priority_policy}, "
                            f"strat_set={config.stagmix_strategy_set}, "
                            f"d*={result['diagnostics']['d_star']:.4f}, "
                            f"detector_triggers={result['diagnostics']['detector_triggers']}, "
                            f"stagmix_steps={result['diagnostics']['n_probe_log_rows']}"
                        ),
                    }
                    all_frontier.append(row)
                    all_trace.extend(oracle.ledger)
                    all_diag.append({
                        "segment_id": seg_id,
                        "method_id": variant_name,
                        "seed": seed,
                        "budget_abs": budget_abs,
                        "budget_ratio": br,
                        **result["diagnostics"],
                    })
                    all_probe_log.extend(result.get("probe_log", []))
                    all_sched_log.extend(result.get("scheduler_decision_log", []))

    frontier_df = pd.DataFrame(all_frontier)
    trace_df = pd.DataFrame(all_trace)
    diag_df = pd.DataFrame(all_diag)

    f_path = OUT / "hts_ec_v0_frontier.csv"
    t_path = OUT / "hts_ec_v0_call_trace.csv"
    d_path = OUT / "hts_ec_v0_diagnostics.csv"
    frontier_df.to_csv(f_path, index=False)
    trace_df.to_csv(t_path, index=False)
    diag_df.to_csv(d_path, index=False)

    if all_probe_log:
        pl_path = OUT / "hts_ec_v0_probe_log.csv"
        pd.DataFrame(all_probe_log).to_csv(pl_path, index=False)
    if all_sched_log:
        sl_path = OUT / "hts_ec_v0_scheduler_decision_log.csv"
        pd.DataFrame(all_sched_log).to_csv(sl_path, index=False)

    # ============================================================
    # Preflight sanity checks
    # ============================================================
    hts_df = frontier_df[frontier_df["method_id"].isin(VARIANTS.keys())].copy()
    n_violations = int((hts_df["oracle_calls_total"] > hts_df["budget_abs"]).sum())
    n_leaks = int((hts_df["online_uses_event_id"] == True).sum())

    # S-1: no duplicate paid bin query within one run.
    # Every row in trace_df is a paid oracle call (AlignedOracle ledger), so
    # we group by the per-run key + bin_id and assert each (run, bin) appears
    # at most once. Zero is the only acceptable value: any non-zero count means
    # either the query-cache assert in HtsEcV0Runner._paid_query was bypassed
    # or a selector returned an already-paid bin.
    if "oracle_call" in trace_df.columns:
        paid_trace = trace_df[trace_df["oracle_call"] == True]
    else:
        paid_trace = trace_df
    dup_grp = paid_trace.groupby(
        ["segment_id", "method_id", "seed", "budget_ratio", "bin_id"]
    ).size().reset_index(name="n")
    duplicate_paid_queries = int((dup_grp["n"] > 1).sum())

    # G0: shadow-stag must equal safe on pos_bins, calls, intervals.
    g0_failures = 0
    for key, safe in safe_results.items():
        shadow = None
        for row in all_frontier:
            if (row["method_id"] == "HTS-EC-safe-shadow-stag"
                    and row["segment_id"] == key[0]
                    and row["budget_ratio"] == key[1]
                    and row["seed"] == key[2]):
                shadow = row
                break
        if shadow is None:
            g0_failures += 1
            continue
        same = (safe["calls"] == shadow["oracle_calls_total"]
                and str(safe["intervals"]) == shadow["returned_intervals"])
        if not same:
            g0_failures += 1

    # G2: eligible-but-not-chosen rows in StagRepMix-force variants.
    bad_g2 = 0
    FORCE_METHODS = {"HTS-EC-safe-StagRepMix-force",
                     "HTS-EC-safe-StagRepMix-force-gap_flank_v2"}
    for sl_ in all_sched_log:
        if (sl_["method"] in FORCE_METHODS
                and sl_["stagmix_candidate_count"] > 0
                and sl_["diverse_probe_budget_used"] < sl_["diverse_probe_budget_cap"]
                and sl_["chosen_source"] != "stagmix"):
            bad_g2 += 1

    # Diverse share cap sanity.
    probe_df = pd.DataFrame(all_probe_log) if all_probe_log else pd.DataFrame()
    if len(probe_df):
        sm_df = probe_df[probe_df["frontier_source"] == "stagmix"]
        diverse_share_by_run = sm_df.groupby(["run_id", "segment_id", "budget_config", "seed"]).size()
    else:
        diverse_share_by_run = pd.Series(dtype=int)

    print("=" * 80)
    print("HTS-EC-v0 Phase 2A-RP preflight diagnostics")
    print("=" * 80)
    print(f"Variants: {list(VARIANTS.keys())}")
    print(f"Budgets: {BUDGET_RATIOS}, Seeds: {SEEDS}")
    print()
    print(f"Budget violations: {n_violations} (must be 0)")
    print(f"event_id leaks:    {n_leaks} (must be 0)")
    print(f"S-1 duplicate paid queries:      {duplicate_paid_queries} (must be 0)")
    print(f"G0 shadow invariance failures: {g0_failures} (must be 0)")
    print(f"G2 eligible-but-not-chosen rows: {bad_g2} (must be 0)")
    print()

    if len(probe_df):
        print("StagRepMix-force probe counts:")
        print(probe_df.groupby("frontier_source").size().to_string())
        print()
        print("StagRepMix-force strategy exposure:")
        print(sm_df.groupby("stagmix_strategy").size().to_string())
        print()

    print("Per segment x budget (best-of-3-seed IoU>=0.3 recall):")
    for (seg, br), grp in frontier_df.groupby(["segment_id", "budget_ratio"]):
        print(f"  {seg:28s} b={br:.2f}")
        for mid in sorted(grp["method_id"].unique()):
            sub = grp[grp["method_id"] == mid]
            if mid in VARIANTS:
                best_recall = sub["event_recall"].max()
                print(f"    {mid:42s} best={best_recall:.3f}")
            else:
                r = sub["event_recall"].iloc[0] if len(sub) > 0 else 0.0
                print(f"    {mid:42s} best={r:.3f}")
    print()

    # G5 dense regression guard @ budget 0.30
    df30 = frontier_df[frontier_df["budget_ratio"] == 0.30]
    for force_mid in FORCE_METHODS:
        sub = df30[(df30["segment_id"] == "realcartest_2000_3200")
                   & (df30["method_id"] == force_mid)]
        rc_recall = float(sub["event_recall"].max()) if len(sub) else 0.0
        print(f"G5 dense regression guard (realcartest_2000_3200 @ 0.30, "
              f"{force_mid}): {rc_recall:.3f} (target >= 0.180)")
    print()

    print(f"Written: {f_path}  rows={len(frontier_df)}")
    print(f"Written: {t_path}  rows={len(trace_df)}")
    print(f"Written: {d_path}  rows={len(diag_df)}")
    if all_probe_log:
        print(f"Written: {pl_path}  rows={len(all_probe_log)}")
    if all_sched_log:
        print(f"Written: {sl_path}  rows={len(all_sched_log)}")
    print()

    assert n_violations == 0, f"Budget violations: {n_violations}"
    assert n_leaks == 0, f"event_id leaks: {n_leaks}"
    assert duplicate_paid_queries == 0, f"duplicate paid queries: {duplicate_paid_queries}"
    assert g0_failures == 0, f"G0 shadow invariance failures: {g0_failures}"
    assert bad_g2 == 0, f"G2 eligible-but-not-chosen rows: {bad_g2}"


if __name__ == "__main__":
    main()
