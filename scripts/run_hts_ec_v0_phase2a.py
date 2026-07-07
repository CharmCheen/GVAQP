#!/usr/bin/env python3
"""HTS-EC-v0 Phase 2A: Fix weak-proxy recall gap with ELFine + RepMix.

Tests 4 HTS-EC variants + 3 baselines on 4 key segments.
Goal: fix ds3_2400_3462 (Gate 5) and ds3_0_1200 (Gate 4) without breaking rc_2000.

Variants:
  - HTS-EC-safe (baseline from Phase 1)
  - HTS-EC-safe+ELFine (EventLift-style fine frontier)
  - HTS-EC-safe+RepMix (mixed representative bin selection)
  - HTS-EC-safe+ELFine+RepMix (both)
  - HTS-EC-safe+ELFine+RepMix+Escape (add escape hatch + proxy-mass drill)

Hard constraints (per AGENTS.md):
  - No VLM/GPU/video. Replays existing is_positive labels.
  - No event_id online. AlignedOracle.assert_no_event_id() verified.
  - IoU>=0.3 evaluation. No safe-stopping claim.
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
    AlignedOracle, group_positive_bins, evaluate_events,
)

OUT = REPO / "outputs" / "hts_ec_v0_phase2a"
OUT.mkdir(parents=True, exist_ok=True)

IOU_THRESH = 0.3
BUDGET_RATIOS = [0.10, 0.20, 0.30]
SEEDS = [0, 1, 2]

# 4 key segments (per audit)
KEY_SEGMENTS = [
    {"segment_id": "realcartest_2000_3200", "video_id": "realcartest", "t_start": 2000.0, "t_end": 3200.0},
    {"segment_id": "dataset3_0_1200", "video_id": "long_video_dataset3", "t_start": 0.0, "t_end": 1200.0},
    {"segment_id": "dataset3_1200_2400", "video_id": "long_video_dataset3", "t_start": 1200.0, "t_end": 2400.0},
    {"segment_id": "dataset3_2400_3462", "video_id": "long_video_dataset3", "t_start": 2400.0, "t_end": 3462.93},
]

# Base safe config (from Phase 1)
SAFE_BASE = dict(
    detector_posterior_thresh=0.85,
    detector_k_min=4,
    tree_preference_bonus=0.1,
    posterior_drill_thresh=0.5,   # original: works for rc_2000
    posterior_prune_thresh=0.05,
    posterior_min_probes=2,
    posterior_prune_min_probes=6,
    ucb_c=0.5,  # original: works for rc_2000
)

# Variant with higher exploration for weak-proxy
EXPLORATIVE_BASE = dict(
    detector_posterior_thresh=0.85,
    detector_k_min=4,
    tree_preference_bonus=0.1,
    posterior_drill_thresh=0.35,
    posterior_prune_thresh=0.05,
    posterior_min_probes=2,
    posterior_prune_min_probes=6,
    ucb_c=1.5,  # higher exploration
)

VARIANTS = {
    "HTS-EC-safe": HtsEcV0Config(
        method_id="HTS-EC-safe",
        **SAFE_BASE,
    ),
    "HTS-EC-safe+ELFine": HtsEcV0Config(
        method_id="HTS-EC-safe+ELFine",
        **SAFE_BASE,
        use_elfine=True,
    ),
    "HTS-EC-safe+RepMix": HtsEcV0Config(
        method_id="HTS-EC-safe+RepMix",
        **SAFE_BASE,
        use_repmix=True,
        repmix_first_k=4,
    ),
    "HTS-EC-safe+ELFine+RepMix": HtsEcV0Config(
        method_id="HTS-EC-safe+ELFine+RepMix",
        **SAFE_BASE,
        use_elfine=True,
        use_repmix=True,
        repmix_first_k=4,
    ),
    "HTS-EC-explorative+RepMix": HtsEcV0Config(
        method_id="HTS-EC-explorative+RepMix",
        **EXPLORATIVE_BASE,
        use_repmix=True,
        repmix_first_k=4,
    ),
    "HTS-EC-explorative+ELFine+RepMix+Escape": HtsEcV0Config(
        method_id="HTS-EC-explorative+ELFine+RepMix+Escape",
        **EXPLORATIVE_BASE,
        use_elfine=True,
        use_repmix=True,
        repmix_first_k=4,
        use_escape_hatch=True,
        escape_hatch_budget_frac=0.05,
        escape_hatch_stagnation_window=10,
        use_proxy_mass_drill=True,
        proxy_mass_drill_frac=0.6,
    ),
}


def get_baseline_recall(seg_id, budget_ratio, method_id, csv_path):
    if not Path(csv_path).exists():
        return None
    df = pd.read_csv(csv_path)
    df = df[(df["segment_id"] == seg_id) &
            (df["method_id"] == method_id) &
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

    for seg in KEY_SEGMENTS:
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

            # Flat top-proxy baseline
            probe_order = np.argsort(-proxies, kind="stable")
            flat_pos = set()
            for i in range(min(budget_abs, n_bins)):
                b = int(probe_order[i])
                if labels[b] == 1:
                    flat_pos.add(b)
            flat_intervals = group_positive_bins(sorted(flat_pos), grid)
            flat_ev = evaluate_events(flat_intervals, ref_seg)
            all_frontier.append({
                "segment_id": seg_id, "method_id": "fixed_10s_topproxy",
                "seed": -1, "budget_abs": budget_abs, "budget_ratio": br,
                "oracle_calls_total": min(budget_abs, n_bins),
                "returned_intervals": str(flat_intervals),
                "event_precision": flat_ev["event_precision"],
                "event_recall": flat_ev["event_recall"],
                "unique_event_coverage": flat_ev["unique_event_coverage"],
                "strict_replay_or_posthoc": "strict_replay",
                "online_uses_event_id": False,
                "can_be_main_comparison": True,
                "applicability_note": "flat proxy-ranked top-k",
            })

            # Baselines from CSVs
            aligned_path = REPO / "outputs/aligned_baselines_v1/aligned_baseline_frontier_raw.csv"
            el_path = REPO / "outputs/eventlift_full_benchmark_v1/full_frontier_raw.csv"
            for mid, csv_p in [
                ("B7-strict-replay", aligned_path),
                ("D3-norepair-core-strict", aligned_path),
                ("EventLift-discover-certify", el_path),
            ]:
                bl = get_baseline_recall(seg_id, br, mid, csv_p)
                if bl:
                    all_frontier.append({
                        "segment_id": seg_id, "method_id": mid,
                        "seed": -1, "budget_abs": budget_abs, "budget_ratio": br,
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

            # Run HTS-EC variants
            for variant_name, config in VARIANTS.items():
                for seed in SEEDS:
                    oracle = AlignedOracle(grid, seg_id, variant_name, seed, budget_abs, br)
                    runner = HtsEcV0Runner(config)
                    result = runner.run(grid, oracle, budget_abs, seed=seed)
                    ev = evaluate_events(result["intervals"], ref_seg)
                    oracle.assert_no_event_id()
                    assert oracle.calls <= budget_abs, f"Budget violation: {oracle.calls} > {budget_abs}"
                    all_frontier.append({
                        "segment_id": seg_id, "method_id": variant_name,
                        "seed": seed, "budget_abs": budget_abs, "budget_ratio": br,
                        "oracle_calls_total": oracle.calls,
                        "returned_intervals": str(result["intervals"]),
                        "event_precision": ev["event_precision"],
                        "event_recall": ev["event_recall"],
                        "unique_event_coverage": ev["unique_event_coverage"],
                        "strict_replay_or_posthoc": "strict_replay",
                        "online_uses_event_id": False,
                        "can_be_main_comparison": True,
                        "applicability_note": (
                            f"HTS-EC-v0 Phase 2A, d*={result['diagnostics']['d_star']:.4f}, "
                            f"triggers={result['diagnostics']['detector_triggers']}, "
                            f"fine_frac={result['diagnostics']['fine_fraction']:.3f}, "
                            f"escape={result['diagnostics']['escape_hatch_steps']}"),
                    })
                    all_trace.extend(oracle.ledger)
                    all_diag.append({
                        "segment_id": seg_id, "method_id": variant_name,
                        "seed": seed, "budget_abs": budget_abs, "budget_ratio": br,
                        **result["diagnostics"],
                    })

    frontier_df = pd.DataFrame(all_frontier)
    trace_df = pd.DataFrame(all_trace)
    diag_df = pd.DataFrame(all_diag)

    f_path = OUT / "phase2a_frontier.csv"
    t_path = OUT / "phase2a_call_trace.csv"
    d_path = OUT / "phase2a_diagnostics.csv"
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
    print("HTS-EC-v0 Phase 2A — ELFine + RepMix + Escape Hatch")
    print("=" * 80)
    print(f"Variants: {list(VARIANTS.keys())}")
    print(f"Segments: {[s['segment_id'] for s in KEY_SEGMENTS]}")
    print(f"Budgets: {BUDGET_RATIOS}, Seeds: {SEEDS}")
    print(f"Total HTS-EC runs: {len(hts_df)}")
    print(f"Budget violations: {n_violations} (must be 0)")
    print(f"event_id leaks: {n_leaks} (must be 0)")
    print()

    # Results @ 0.30
    df30 = frontier_df[frontier_df["budget_ratio"] == 0.30]
    print("Results @ budget 0.30 (best-of-3-seed IoU>=0.3 recall):")
    for seg_id in df30["segment_id"].unique():
        sub = df30[df30["segment_id"] == seg_id]
        print(f"  {seg_id}:")
        for mid in sorted(sub["method_id"].unique()):
            ss = sub[sub["method_id"] == mid]
            if mid in VARIANTS:
                best = ss["event_recall"].max()
                mean = ss["event_recall"].mean()
                print(f"    {mid:42s} best={best:.3f} mean={mean:.3f}")
            else:
                r = ss["event_recall"].iloc[0] if len(ss) > 0 else 0.0
                print(f"    {mid:42s}       best={r:.3f}")
    print()

    # Gate conditions @ 0.30
    print("Gate conditions @ budget 0.30:")
    print()

    def best_hts(seg_id, variant):
        sub = df30[(df30["segment_id"] == seg_id) & (df30["method_id"] == variant)]
        return float(sub["event_recall"].max()) if len(sub) else 0.0

    def baseline_r(seg_id, mid):
        sub = df30[(df30["segment_id"] == seg_id) & (df30["method_id"] == mid)]
        return float(sub["event_recall"].iloc[0]) if len(sub) else 0.0

    flat_rc = baseline_r("realcartest_2000_3200", "fixed_10s_topproxy")
    el_ds24 = baseline_r("dataset3_2400_3462", "EventLift-discover-certify")
    b7_ds0 = baseline_r("dataset3_0_1200", "B7-strict-replay")

    print(f"  1. 0 budget violations: {'PASS' if n_violations == 0 else 'FAIL'} ({n_violations})")
    print(f"  2. 0 event_id leaks:     {'PASS' if n_leaks == 0 else 'FAIL'} ({n_leaks})")

    print(f"\n  3. rc_2000 >= flat({flat_rc:.3f}) - 0.02 = {flat_rc - 0.02:.3f}:")
    g3 = {}
    for v in VARIANTS:
        r = best_hts("realcartest_2000_3200", v)
        p = r >= flat_rc - 0.02
        g3[v] = p
        print(f"     {v:42s} {r:.3f} → {'PASS' if p else 'FAIL'}")

    print(f"\n  4. ds3_0_1200 > 0 or >= B7({b7_ds0:.3f}) - 0.05:")
    g4 = {}
    for v in VARIANTS:
        r = best_hts("dataset3_0_1200", v)
        p = (r > 0) or (r >= b7_ds0 - 0.05)
        g4[v] = p
        print(f"     {v:42s} {r:.3f} → {'PASS' if p else 'FAIL'}")

    print(f"\n  5. ds3_2400_3462 >= EL-DC({el_ds24:.3f}) - 0.05 = {el_ds24 - 0.05:.3f}:")
    g5 = {}
    for v in VARIANTS:
        r = best_hts("dataset3_2400_3462", v)
        p = r >= el_ds24 - 0.05
        g5[v] = p
        print(f"     {v:42s} {r:.3f} → {'PASS' if p else 'FAIL'}")

    print(f"\n  6. fine frontier gated on sparse (fine_frac < 0.8):")
    g6 = {}
    sparse_segs = ["dataset3_0_1200", "dataset3_1200_2400", "dataset3_2400_3462"]
    for v in VARIANTS:
        sub = diag_df[(diag_df["method_id"] == v) &
                      (diag_df["budget_ratio"] == 0.30) &
                      (diag_df["segment_id"].isin(sparse_segs))]
        max_ff = float(sub["fine_fraction"].max()) if len(sub) else 1.0
        p = max_ff < 0.8
        g6[v] = p
        print(f"     {v:42s} max_fine_frac(sparse)={max_ff:.3f} → {'PASS' if p else 'FAIL'}")

    print()
    # Per-variant overall
    print("Per-variant summary (gates 3+4+5+6):")
    for v in VARIANTS:
        all4 = g3.get(v, False) and g4.get(v, False) and g5.get(v, False) and g6.get(v, False)
        n = sum([g3.get(v, False), g4.get(v, False), g5.get(v, False), g6.get(v, False)])
        print(f"  {v:42s} {n}/4 → {'ALL PASS' if all4 else 'PARTIAL'}")

    print()
    # Find best variant
    best_variant = None
    best_n = 0
    for v in VARIANTS:
        n = sum([g3.get(v, False), g4.get(v, False), g5.get(v, False), g6.get(v, False)])
        if n > best_n:
            best_n = n
            best_variant = v

    if best_n == 4:
        verdict = f"PASS — {best_variant} passes all 4 conditions"
    elif best_n >= 3:
        verdict = f"CONDITIONAL — {best_variant} passes {best_n}/4"
    else:
        verdict = f"FAIL — best variant passes {best_n}/4"

    print(f"PHASE 2A VERDICT: {verdict}")
    print()
    print(f"Written: {f_path}  rows={len(frontier_df)}")
    print(f"Written: {t_path}  rows={len(trace_df)}")
    print(f"Written: {d_path}  rows={len(diag_df)}")

    assert n_violations == 0, f"Budget violations: {n_violations}"
    assert n_leaks == 0, f"event_id leaks: {n_leaks}"


if __name__ == "__main__":
    main()
