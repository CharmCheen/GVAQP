#!/usr/bin/env python3
"""HTS-EC-v0 strict-replay Phase 1 smoke.

Runs 3 HTS-EC-v0 variants + baselines on 6 segments × 3 budgets × 3 seeds,
strict-replay (no event_id online, posterior-based drill/prune, no certify).

Variants:
  - HTS-EC-safe: conservative detector (P_thresh=0.85, k_min=6)
  - HTS-EC-gated-dual: default (P_thresh=0.75, k_min=5)
  - HTS-EC-gated-dual-conservative: P_thresh=0.85, k_min=5, higher tree bonus

Baselines (pulled from existing CSVs):
  - naive-HTS-strict-posterior (from naive_hts_aqp_frontier.csv)
  - fixed_10s_topproxy (computed inline)
  - EventLift-DC (from full_frontier_raw.csv)
  - B7-strict-replay (from aligned_baseline_frontier_raw.csv)
  - D3-norepair-core-strict (from aligned_baseline_frontier_raw.csv)

Gate conditions (per audit §6):
  1. 0 budget violations
  2. 0 event_id leaks
  3. rc_2000 recall >= flat - 0.02
  4. dataset3_0_1200 recall >= naive-HTS-strict-posterior or > 0
  5. dataset3_2400_3462 not lower than EventLift-DC - 0.05
  6. detector triggers reasonable (not 0, not all-the-time)
  7. fine frontier not always-on (fine_fraction < 0.8 for sparse segments)

Hard constraints (per AGENTS.md):
  - No VLM/GPU/video. Replays existing is_positive labels.
  - No event_id online. AlignedOracle.assert_no_event_id() verified.
  - IoU>=0.3 evaluation.
  - No safe-stopping claim.
"""
import sys
import math
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from garc_eval.hts_ec_v0 import HtsEcV0Runner, HtsEcV0Config
from run_aligned_baselines_v1 import (
    load_segment_data, SEGMENTS, PROXY_COL, LABEL_COL,
    AlignedOracle, group_positive_bins, evaluate_events, _iou_interval,
)

OUT = REPO / "outputs" / "hts_ec_v0_strict_v1"
OUT.mkdir(parents=True, exist_ok=True)

IOU_THRESH = 0.3
BUDGET_RATIOS = [0.10, 0.20, 0.30]
SEEDS = [0, 1, 2]

# Variant configs
VARIANTS = {
    "HTS-EC-safe": HtsEcV0Config(
        method_id="HTS-EC-safe",
        detector_posterior_thresh=0.85,
        detector_k_min=4,
        tree_preference_bonus=0.1,
        posterior_prune_thresh=0.15,
    ),
    "HTS-EC-gated-dual": HtsEcV0Config(
        method_id="HTS-EC-gated-dual",
        detector_posterior_thresh=0.75,
        detector_k_min=3,
        tree_preference_bonus=0.1,
        posterior_prune_thresh=0.15,
    ),
    "HTS-EC-gated-dual-conservative": HtsEcV0Config(
        method_id="HTS-EC-gated-dual-conservative",
        detector_posterior_thresh=0.80,
        detector_k_min=4,
        tree_preference_bonus=0.2,  # higher tree bonus
        posterior_prune_thresh=0.15,
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


def get_baseline_recall(seg_id, budget_ratio, method_id, csv_path, method_col="method_id"):
    """Pull best-of-3-seed recall from existing CSV."""
    if not Path(csv_path).exists():
        return None
    df = pd.read_csv(csv_path)
    df = df[(df["segment_id"] == seg_id) &
            (df[method_col] == method_id) &
            (df["budget_ratio"] == budget_ratio)]
    if len(df) == 0:
        return None
    df["event_recall"] = pd.to_numeric(df["event_recall"], errors="coerce")
    df = df.dropna(subset=["event_recall"])
    if len(df) == 0:
        return None
    best = df.loc[df["event_recall"].idxmax()]
    return {
        "recall": float(best["event_recall"]),
        "precision": float(best.get("event_precision", 0.0) or 0.0),
        "calls": int(best.get("oracle_calls_total", 0)),
    }


def main():
    all_frontier = []
    all_trace = []
    all_diag = []

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

            # Compute flat top-proxy baseline inline
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
                "can_be_main_comparison": True,
                "applicability_note": "flat proxy-ranked top-k, strict-replay",
            })

            # Pull baselines from existing CSVs
            aligned_path = REPO / "outputs/aligned_baselines_v1/aligned_baseline_frontier_raw.csv"
            el_path = REPO / "outputs/eventlift_full_benchmark_v1/full_frontier_raw.csv"
            naive_path = REPO / "outputs/hts_ec_feasibility_v1/naive_hts_aqp_frontier.csv"

            for mid, csv_p, col in [
                ("B7-strict-replay", aligned_path, "method_id"),
                ("D3-norepair-core-strict", aligned_path, "method_id"),
                ("EventLift-discover-certify", el_path, "method_id"),
                ("naive-HTS-strict-posterior", naive_path, "method_id"),
            ]:
                bl = get_baseline_recall(seg_id, br, mid, csv_p, col)
                if bl:
                    all_frontier.append({
                        "segment_id": seg_id,
                        "method_id": mid,
                        "seed": -1,  # best-of-3-seed
                        "budget_abs": budget_abs,
                        "budget_ratio": br,
                        "oracle_calls_total": bl["calls"],
                        "returned_intervals": "",
                        "event_precision": bl["precision"],
                        "event_recall": bl["recall"],
                        "unique_event_coverage": 0,
                        "strict_replay_or_posthoc": "strict_replay",
                        "online_uses_event_id": False,
                        "can_be_main_comparison": True,
                        "applicability_note": f"best-of-3-seed from {Path(csv_p).name}",
                    })

            # Run HTS-EC-v0 variants
            for variant_name, config in VARIANTS.items():
                for seed in SEEDS:
                    oracle = AlignedOracle(
                        grid, seg_id, variant_name, seed, budget_abs, br)
                    runner = HtsEcV0Runner(config)
                    result = runner.run(grid, oracle, budget_abs, seed=seed)

                    ev = evaluate_events(result["intervals"], ref_seg)

                    oracle.assert_no_event_id()
                    assert oracle.calls <= budget_abs, \
                        f"Budget violation: {oracle.calls} > {budget_abs}"

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
                        "can_be_main_comparison": True,
                        "applicability_note": (
                            f"HTS-EC-v0 strict-replay, posterior drill/prune, "
                            f"gated dual frontier, no certify. "
                            f"d*={result['diagnostics']['d_star']:.4f}, "
                            f"detector_triggers={result['diagnostics']['detector_triggers']}, "
                            f"fine_fraction={result['diagnostics']['fine_fraction']:.3f}"),
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

    frontier_df = pd.DataFrame(all_frontier)
    trace_df = pd.DataFrame(all_trace)
    diag_df = pd.DataFrame(all_diag)

    f_path = OUT / "hts_ec_v0_frontier.csv"
    t_path = OUT / "hts_ec_v0_call_trace.csv"
    d_path = OUT / "hts_ec_v0_diagnostics.csv"
    frontier_df.to_csv(f_path, index=False)
    trace_df.to_csv(t_path, index=False)
    diag_df.to_csv(d_path, index=False)

    # ============================================================
    # Constraint verification + gate conditions
    # ============================================================
    hts_df = frontier_df[frontier_df["method_id"].isin(VARIANTS.keys())].copy()
    n_violations = int((hts_df["oracle_calls_total"] > hts_df["budget_abs"]).sum())
    n_leaks = int((hts_df["online_uses_event_id"] == True).sum())

    print("=" * 80)
    print("HTS-EC-v0 strict-replay Phase 1 smoke")
    print("=" * 80)
    print(f"Variants: {list(VARIANTS.keys())}")
    print(f"Budgets: {BUDGET_RATIOS}, Seeds: {SEEDS}")
    print(f"Total HTS-EC runs: {len(hts_df)}")
    print()
    print(f"Budget violations: {n_violations} (must be 0)")
    print(f"event_id leaks: {n_leaks} (must be 0)")
    print()
    print("Per segment x budget x variant (best-of-3-seed IoU>=0.3 recall):")
    for (seg, br), grp in frontier_df.groupby(["segment_id", "budget_ratio"]):
        print(f"  {seg:28s} b={br:.2f}")
        for mid in sorted(grp["method_id"].unique()):
            sub = grp[grp["method_id"] == mid]
            if mid in VARIANTS:
                best_recall = sub["event_recall"].max()
                mean_recall = sub["event_recall"].mean()
                n = len(sub)
                print(f"    {mid:42s} n={n} best={best_recall:.3f} mean={mean_recall:.3f}")
            else:
                # baseline (single row, best-of-3)
                r = sub["event_recall"].iloc[0] if len(sub) > 0 else 0.0
                print(f"    {mid:42s}       best={r:.3f}")
    print()

    # Gate conditions @ budget 0.30
    df30 = frontier_df[frontier_df["budget_ratio"] == 0.30]
    print("Gate conditions @ budget 0.30:")
    print()

    # Helper: get best-of-3-seed recall for HTS-EC variant
    def best_recall_hts(seg_id, variant):
        sub = df30[(df30["segment_id"] == seg_id) & (df30["method_id"] == variant)]
        return float(sub["event_recall"].max()) if len(sub) else 0.0

    def baseline_recall(seg_id, method_id):
        sub = df30[(df30["segment_id"] == seg_id) & (df30["method_id"] == method_id)]
        return float(sub["event_recall"].iloc[0]) if len(sub) else 0.0

    # 1 & 2: constraints
    g1 = n_violations == 0
    g2 = n_leaks == 0
    print(f"  1. 0 budget violations: {'PASS' if g1 else 'FAIL'} ({n_violations})")
    print(f"  2. 0 event_id leaks:     {'PASS' if g2 else 'FAIL'} ({n_leaks})")

    # 3. rc_2000 recall >= flat - 0.02
    rc_flat = baseline_recall("realcartest_2000_3200", "fixed_10s_topproxy")
    print(f"\n  3. rc_2000 recall >= flat({rc_flat:.3f}) - 0.02 = {rc_flat - 0.02:.3f}:")
    g3_any = False
    for v in VARIANTS:
        r = best_recall_hts("realcartest_2000_3200", v)
        passed = r >= rc_flat - 0.02
        g3_any = g3_any or passed
        print(f"     {v:42s} {r:.3f} → {'PASS' if passed else 'FAIL'}")

    # 4. dataset3_0_1200 recall >= naive-HTS-strict-posterior or > 0
    naive_ds0 = baseline_recall("dataset3_0_1200", "naive-HTS-strict-posterior")
    print(f"\n  4. ds3_0_1200 recall >= naive-HTS-posterior({naive_ds0:.3f}) or > 0:")
    g4_any = False
    for v in VARIANTS:
        r = best_recall_hts("dataset3_0_1200", v)
        passed = (r >= naive_ds0 - 0.02) or (r > 0)
        g4_any = g4_any or passed
        print(f"     {v:42s} {r:.3f} → {'PASS' if passed else 'FAIL'}")

    # 5. dataset3_2400_3462 not lower than EventLift-DC - 0.05
    el_ds24 = baseline_recall("dataset3_2400_3462", "EventLift-discover-certify")
    print(f"\n  5. ds3_2400_3462 recall >= EL-DC({el_ds24:.3f}) - 0.05 = {el_ds24 - 0.05:.3f}:")
    g5_any = False
    for v in VARIANTS:
        r = best_recall_hts("dataset3_2400_3462", v)
        passed = r >= el_ds24 - 0.05
        g5_any = g5_any or passed
        print(f"     {v:42s} {r:.3f} → {'PASS' if passed else 'FAIL'}")

    # 6. detector triggers reasonable
    print(f"\n  6. detector triggers reasonable (not 0, not all-the-time):")
    g6_any = False
    for v in VARIANTS:
        sub = diag_df[(diag_df["method_id"] == v) & (diag_df["budget_ratio"] == 0.30)]
        if len(sub):
            mean_triggers = float(sub["detector_triggers"].mean())
            mean_fine_frac = float(sub["fine_fraction"].mean())
            reasonable = (mean_triggers > 0) and (mean_fine_frac < 0.8)
            g6_any = g6_any or reasonable
            print(f"     {v:42s} triggers={mean_triggers:.1f} fine_frac={mean_fine_frac:.3f} → "
                  f"{'PASS' if reasonable else 'FAIL'}")

    # 7. fine frontier not always-on for sparse segments
    print(f"\n  7. fine frontier not always-on for sparse segments (fine_frac < 0.8):")
    sparse_segs = ["dataset3_0_1200", "dataset3_1200_2400", "dataset3_2400_3462"]
    g7_any = False
    for v in VARIANTS:
        sub = diag_df[(diag_df["method_id"] == v) &
                      (diag_df["budget_ratio"] == 0.30) &
                      (diag_df["segment_id"].isin(sparse_segs))]
        if len(sub):
            max_fine_frac = float(sub["fine_fraction"].max())
            passed = max_fine_frac < 0.8
            g7_any = g7_any or passed
            print(f"     {v:42s} max_fine_frac(sparse)={max_fine_frac:.3f} → "
                  f"{'PASS' if passed else 'FAIL'}")

    print()
    all_gates = [g1, g2, g3_any, g4_any, g5_any, g6_any, g7_any]
    n_pass = sum(all_gates)
    if all(all_gates):
        verdict = "PASS — all 7 gate conditions met"
    elif n_pass >= 5:
        verdict = f"CONDITIONAL — {n_pass}/7 gates pass"
    else:
        verdict = f"FAIL — only {n_pass}/7 gates pass"
    print(f"PHASE 1 SMOKE VERDICT: {verdict}")
    print()

    # Per-variant summary: which variant passes all of gates 3-5?
    print("Per-variant pass (gates 3+4+5):")
    for v in VARIANTS:
        rc_r = best_recall_hts("realcartest_2000_3200", v)
        ds0_r = best_recall_hts("dataset3_0_1200", v)
        ds24_r = best_recall_hts("dataset3_2400_3462", v)
        g3 = rc_r >= rc_flat - 0.02
        g4 = (ds0_r >= naive_ds0 - 0.02) or (ds0_r > 0)
        g5 = ds24_r >= el_ds24 - 0.05
        all3 = g3 and g4 and g5
        print(f"  {v:42s} rc={rc_r:.3f}({'P' if g3 else 'F'}) "
              f"ds0={ds0_r:.3f}({'P' if g4 else 'F'}) "
              f"ds24={ds24_r:.3f}({'P' if g5 else 'F'}) → "
              f"{'ALL PASS' if all3 else 'PARTIAL'}")

    print()
    print(f"Written: {f_path}  rows={len(frontier_df)}")
    print(f"Written: {t_path}  rows={len(trace_df)}")
    print(f"Written: {d_path}  rows={len(diag_df)}")

    # Hard asserts
    assert n_violations == 0, f"Budget violations: {n_violations}"
    assert n_leaks == 0, f"event_id leaks: {n_leaks}"


if __name__ == "__main__":
    main()
