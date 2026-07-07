#!/usr/bin/env python3
"""HTS-EC Gate A — Granularity Heterogeneity & Regret Analysis.

Re-aggregates existing strict-replay frontier CSVs (no new oracle/VLM/GPU).
For each segment, finds the best fixed-granularity method (by best-of-3-seed
IoU>=0.3 recall at budget 0.30), then compares per-segment best granularity
to a single global best granularity. The "adaptive granularity gain" quantifies
whether resolution-adaptive search (HTS-EC) has room to add value over any
single fixed resolution.

Hard constraints honored (per AGENTS.md):
  - No oracle / VLM / GPU / new labels / video.
  - No modification of existing benchmark output.
  - IoU>=0.3 is the MAIN metric; any-overlap reported only as a diagnostic
    upper-bound column (from Phase 0 God's-eye sim, not strict-replay).
  - All numbers tagged with source + track.
  - No safe-stopping / formal-guarantee / statistical-bound claim.

Sources read:
  - outputs/aligned_baselines_v1/aligned_baseline_frontier_raw.csv (IoU>=0.3)
  - outputs/eventlift_full_benchmark_v1/full_frontier_raw.csv (IoU>=0.3)
  - outputs/hts_aqp_phase0_feasibility/coarse_to_fine_call_count_by_segment.csv
    (any-overlap, God's-eye, diagnostic-only upper bound)
  - outputs/late_aqp_event_diverse_discovery_v1/segment_info.csv
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs" / "hts_ec_feasibility_v1"
OUT.mkdir(parents=True, exist_ok=True)

ALIGNED = REPO / "outputs/aligned_baselines_v1/aligned_baseline_frontier_raw.csv"
EVENTLIFT = REPO / "outputs/eventlift_full_benchmark_v1/full_frontier_raw.csv"
PHASE0 = REPO / "outputs/hts_aqp_phase0_feasibility/coarse_to_fine_call_count_by_segment.csv"
SEGINFO = REPO / "outputs/late_aqp_event_diverse_discovery_v1/segment_info.csv"

BUDGET_RATIO_MAIN = 0.30
IOU_THRESH = 0.3

# Map each strict-replay method to its base resolution (granularity).
# Source: ALIGNED_BASELINES_V1_REPORT.md + EVENTLIFT_AQP_ALGORITHM_SPEC.md.
# - B7 / D3: 60s chunk-bandit
# - SUPG-event-rt: 10s record selection (proxy-ranked)
# - EventLift-discover-*: 10s atomic-bin discover
METHOD_TO_GRANULARITY = {
    "B7-strict-replay": "60s_chunk",
    "D3-norepair-core-strict": "60s_chunk",
    "SUPG-event-rt-strict": "10s_proxy",
    "EventLift-discover-only": "10s_eventlift",
    "EventLift-discover-audit": "10s_eventlift",
    "EventLift-discover-certify": "10s_eventlift",
    "EventLift-discover-audit-certify": "10s_eventlift",
    "EventLift-full-stage2": "10s_eventlift",
}

# ABae-residual is aggregate-estimation, no intervals -> excluded from
# granularity comparison (it has no event_recall under IoU>=0.3).
EXCLUDE_METHODS = {"ABae-residual-strict"}

# Phase 0 God's-eye HTS — any-overlap only, diagnostic upper bound.
PHASE0_GRANULARITY = {
    2: "HTS_b2_godseye",
    4: "HTS_b4_godseye",
}

SEGMENTS_ALL = [
    "realcartest_0_1570",
    "realcartest_2000_3200",
    "realcartest_3200_3830",
    "dataset3_0_1200",
    "dataset3_1200_2400",
    "dataset3_2400_3462",
]

DENSITY_BUCKETS = {
    "realcartest_0_1570": "dense_28pct",
    "realcartest_2000_3200": "dense_27pct",
    "realcartest_3200_3830": "mid_21pct",
    "dataset3_0_1200": "sparse_6pct",
    "dataset3_1200_2400": "sparse_18pct",
    "dataset3_2400_3462": "sparse_11pct",
}


def _to_float(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return np.nan


def load_strict_replay_recall():
    """Return DataFrame: segment_id, method_id, granularity, recall_IoU@0.30 (best-of-3-seed)."""
    rows = []
    for path in [ALIGNED, EVENTLIFT]:
        df = pd.read_csv(path)
        # Align column names: aligned uses event_recall; eventlift uses event_recall.
        # Filter strict_replay, budget 0.30, exclude ABae.
        df = df[df["strict_replay_or_posthoc"] == "strict_replay"].copy()
        df = df[~df["method_id"].isin(EXCLUDE_METHODS)]
        df = df[df["budget_ratio"] == BUDGET_RATIO_MAIN].copy()
        df["event_recall_f"] = df["event_recall"].apply(_to_float)
        for seg in SEGMENTS_ALL:
            sub = df[df["segment_id"] == seg]
            if len(sub) == 0:
                continue
            for method, grp in sub.groupby("method_id"):
                if method not in METHOD_TO_GRANULARITY:
                    continue
                recall_vals = grp["event_recall_f"].dropna().values
                if len(recall_vals) == 0:
                    continue
                best_recall = float(np.max(recall_vals))
                rows.append({
                    "segment_id": seg,
                    "method_id": method,
                    "granularity": METHOD_TO_GRANULARITY[method],
                    "recall_IoU@0.30": best_recall,
                    "n_seeds": len(recall_vals),
                    "source": "aligned_baselines_v1" if path == ALIGNED else "eventlift_full_benchmark_v1",
                    "track": "strict_replay",
                })
    return pd.DataFrame(rows)


def load_phase0_anyoverlap():
    """Phase 0 God's-eye HTS — any-overlap coverage (diagnostic upper bound)."""
    df = pd.read_csv(PHASE0)
    rows = []
    for _, r in df.iterrows():
        seg = r["segment_id"]
        b = int(r["branching_factor"])
        ref_total = int(r["ref_events_total"])
        touched = int(r["ref_events_touchable_by_pos_bins"])
        cov = touched / ref_total if ref_total > 0 else 0.0
        rows.append({
            "segment_id": seg,
            "method_id": f"naive_HTS_b{b}_godseye",
            "granularity": PHASE0_GRANULARITY[b],
            "recall_anyoverlap@full_coverage": cov,
            "oracle_calls_full_coverage": int(r["total_oracle_calls_used"]),
            "source": "hts_aqp_phase0_feasibility",
            "track": "godseye_anyoverlap",
        })
    return pd.DataFrame(rows)


def compute_gate_a(strict_df, phase0_df, seginfo):
    """Per segment: best fixed granularity (IoU>=0.3) + adaptive gain vs global best."""
    out_rows = []
    # Per-segment best granularity (the granularity whose best-method recall is max)
    per_seg = {}
    for seg in SEGMENTS_ALL:
        sub = strict_df[strict_df["segment_id"] == seg]
        if len(sub) == 0:
            continue
        # best method per granularity
        gran_best = sub.groupby("granularity")["recall_IoU@0.30"].max()
        per_seg[seg] = gran_best
    # Global best granularity = granularity with max macro-average recall across segments
    gran_macro = {}
    for gran, gran_sub in strict_df.groupby("granularity"):
        # macro average of per-segment best recall for this granularity
        per_seg_best = []
        for seg in SEGMENTS_ALL:
            if seg in per_seg and gran in per_seg[seg].index:
                per_seg_best.append(per_seg[seg][gran])
        if len(per_seg_best) > 0:
            gran_macro[gran] = float(np.mean(per_seg_best))
    if len(gran_macro) == 0:
        raise RuntimeError("No granularity data available for Gate A.")
    global_best_gran = max(gran_macro, key=gran_macro.get)
    global_best_macro = gran_macro[global_best_gran]

    for seg in SEGMENTS_ALL:
        if seg not in per_seg:
            continue
        gran_best = per_seg[seg]
        seg_best_gran = gran_best.idxmax()
        seg_best_recall = float(gran_best.max())
        global_recall_on_seg = float(gran_best.get(global_best_gran, np.nan))
        gain = seg_best_recall - global_recall_on_seg if not np.isnan(global_recall_on_seg) else np.nan
        # phase0 any-overlap diagnostic
        p0 = phase0_df[phase0_df["segment_id"] == seg]
        hts_b2_cov = p0[p0["method_id"] == "naive_HTS_b2_godseye"]["recall_anyoverlap@full_coverage"]
        hts_b4_cov = p0[p0["method_id"] == "naive_HTS_b4_godseye"]["recall_anyoverlap@full_coverage"]
        anyoverlap_best = max(
            float(hts_b2_cov.iloc[0]) if len(hts_b2_cov) else 0.0,
            float(hts_b4_cov.iloc[0]) if len(hts_b4_cov) else 0.0,
        )
        info = seginfo[seginfo["segment_id"] == seg].iloc[0]
        out_rows.append({
            "segment_id": seg,
            "density_bucket": DENSITY_BUCKETS.get(seg, "unknown"),
            "event_density": float(info["positive_unit_density"]),
            "mean_event_duration": float(info["duration"]) / float(info["num_events"]) if int(info["num_events"]) > 0 else np.nan,
            "global_best_fixed_granularity": global_best_gran,
            "global_fixed_recall_IoU": global_recall_on_seg,
            "global_fixed_recall_anyoverlap": anyoverlap_best,
            "segment_best_fixed_granularity": seg_best_gran,
            "segment_best_fixed_recall_IoU": seg_best_recall,
            "segment_best_fixed_recall_anyoverlap": anyoverlap_best,
            "adaptive_granularity_gain_IoU": gain,
            "adaptive_granularity_regret_reduction_IoU": gain,
            "fixed_granularity_instability": int(seg_best_gran != global_best_gran),
            "strict_replay_or_posthoc": "strict_replay",
            "source": "aligned_baselines_v1+eventlift_full_benchmark_v1 (IoU); hts_aqp_phase0_feasibility (any-overlap)",
        })
    out_df = pd.DataFrame(out_rows)
    return out_df, global_best_gran, global_best_macro, gran_macro


def main():
    strict_df = load_strict_replay_recall()
    phase0_df = load_phase0_anyoverlap()
    seginfo = pd.read_csv(SEGINFO)

    out_df, global_best_gran, global_best_macro, gran_macro = compute_gate_a(
        strict_df, phase0_df, seginfo)

    csv_path = OUT / "granularity_heterogeneity.csv"
    out_df.to_csv(csv_path, index=False)

    # Verdict
    n_positive_gain = int((out_df["adaptive_granularity_gain_IoU"] > 0).sum())
    macro_gain = float(out_df["adaptive_granularity_gain_IoU"].mean())
    macro_gain_relative = macro_gain / float(out_df["global_fixed_recall_IoU"].mean()) if float(out_df["global_fixed_recall_IoU"].mean()) > 0 else 0.0
    n_instability = int(out_df["fixed_granularity_instability"].sum())

    if n_positive_gain >= 4 and (macro_gain >= 0.03 or macro_gain_relative >= 0.10):
        verdict = "PASS"
    elif n_positive_gain >= 3 and macro_gain > 0:
        verdict = "CONDITIONAL"
    else:
        verdict = "FAIL"

    print("=" * 70)
    print("HTS-EC Gate A — Granularity Heterogeneity & Regret")
    print("=" * 70)
    print(f"Main metric: IoU>={IOU_THRESH} recall @ budget={BUDGET_RATIO_MAIN} (best-of-3-seed)")
    print(f"any-overlap reported only as diagnostic upper bound (Phase 0 God's-eye)")
    print()
    print("Per-granularity macro-average recall (IoU>=0.3):")
    for g, v in sorted(gran_macro.items(), key=lambda kv: -kv[1]):
        marker = "  <-- global best" if g == global_best_gran else ""
        print(f"  {g:20s}  macro_recall={v:.4f}{marker}")
    print()
    print(f"Global best fixed granularity: {global_best_gran} (macro recall={global_best_macro:.4f})")
    print()
    print("Per-segment:")
    for _, r in out_df.iterrows():
        print(f"  {r['segment_id']:28s} density={r['event_density']:.3f}  "
              f"seg_best={r['segment_best_fixed_granularity']:15s} ({r['segment_best_fixed_recall_IoU']:.3f})  "
              f"global={r['global_best_fixed_granularity']:15s} ({r['global_fixed_recall_IoU']:.3f})  "
              f"gain={r['adaptive_granularity_gain_IoU']:+.3f}")
    print()
    print(f"Segments with positive adaptive gain: {n_positive_gain}/6")
    print(f"Segments where seg_best != global_best: {n_instability}/6")
    print(f"Macro adaptive gain (IoU>=0.3): {macro_gain:+.4f}  (relative: {macro_gain_relative:+.2%})")
    print()
    print(f"GATE A VERDICT: {verdict}")
    print(f"  PASS      : >=4/6 segments positive gain AND macro gain >=0.03 or >=10% relative")
    print(f"  CONDITIONAL: 3/6 positive gain, macro gain > 0")
    print(f"  FAIL      : single global granularity near oracle-best")
    print()
    print(f"Written: {csv_path}")
    print(f"  rows={len(out_df)}  cols={len(out_df.columns)}")

    # Save the per-method granular recall as an auxiliary diagnostic
    strict_df.to_csv(OUT / "gate_a_per_method_recall_IoU.csv", index=False)
    print(f"Written: {OUT / 'gate_a_per_method_recall_IoU.csv'}  (auxiliary, per-method recall)")


if __name__ == "__main__":
    main()
