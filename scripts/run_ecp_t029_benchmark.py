"""T029 — frozen ECP-c2-globalcap apples-to-apples benchmark.

Loads all baseline data from existing frontier CSVs, normalizes to common
schema, and outputs three comparison tables:
  1. Absolute performance (event_recall, event_precision, unique_event_coverage)
  2. Delta over ECP-v2 (per-segment, per-budget)
  3. Delta over strongest baseline

No new runs — this is a pure aggregation/comparison of existing data.

Sources:
  hts_ec_v0_strict_v1/hts_ec_v0_frontier.csv     — HTS-EC-safe, fixed_10s_topproxy,
                                                     EventLift-discover-certify,
                                                     B7-strict-replay, D3-norepair-core-strict
  ecp_event_coverage_policy_v1/t028e1_loso_frontier.csv  — ECP-c2, ECP-v2 (LOSO)
  ecp_event_coverage_policy_v1/t028c2_loso_frontier.csv  — ECP-c1, ECP-v2 (LOSO)

Methods included:
  ECP-c2-globalcap       (strict-replay LOSO)
  ECP-c1                 (strict-replay LOSO)
  ECP-v2                 (strict-replay LOSO)
  HTS-EC-safe            (strict-replay)
  EventLift-discover-certify  (strict-replay)
  B7-strict-replay
  D3-norepair-core-strict
  fixed_10s_topproxy     (flat baseline)

Outputs:
  outputs/ecp_event_coverage_policy_v1/t029_benchmark_absolute.csv
  outputs/ecp_event_coverage_policy_v1/t029_benchmark_delta_v2.csv
  outputs/ecp_event_coverage_policy_v1/t029_benchmark_delta_best.csv
  outputs/ecp_event_coverage_policy_v1/t029_benchmark_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

BUDGETS = [0.10, 0.20, 0.30]
ALL_SEGMENTS = [
    "realcartest_0_1570", "realcartest_2000_3200", "realcartest_3200_3830",
    "dataset3_0_1200", "dataset3_1200_2400", "dataset3_2400_3462",
]


def load_hts_baselines():
    """Load HTS-EC and related baselines from hts_ec_v0_strict_v1."""
    path = REPO_ROOT / "outputs/hts_ec_v0_strict_v1/hts_ec_v0_frontier.csv"
    df = pd.read_csv(path)
    # Keep only strict-replay methods
    methods = [
        "HTS-EC-safe", "EventLift-discover-certify",
        "B7-strict-replay", "D3-norepair-core-strict",
        "fixed_10s_topproxy",
    ]
    df = df[df["method_id"].isin(methods)].copy()
    df["source"] = "hts_ec_v0_strict_v1"
    df["display_name"] = df["method_id"]
    return df


def load_ecp_loso(path, variants):
    """Load ECP LOSO frontier and aggregate over folds."""
    df = pd.read_csv(path)
    result = []
    for var in variants:
        sub = df[df["variant"] == var]
        # Aggregate over seeds for per-fold, per-budget
        agg = sub.groupby(["held_out_segment", "budget_ratio"]).agg(
            event_recall=("event_recall", "mean"),
            event_precision=("event_precision", "mean"),
            unique_event_coverage=("unique_event_coverage", "mean"),
            oracle_calls=("oracle_calls_total", "mean"),
        ).reset_index()
        agg["segment_id"] = agg["held_out_segment"]
        agg["method_id"] = var
        agg["source"] = "ecp_loso"
        agg["display_name"] = {
            "c2_loso": "ECP-c2-globalcap",
            "c1_loso": "ECP-c1",
            "v2_loso": "ECP-v2-LOSO",
        }.get(var, var)
        result.append(agg)
    return pd.concat(result, ignore_index=True)


def build_benchmark():
    # --- 1. Load all sources ---
    hts = load_hts_baselines()
    c2 = load_ecp_loso(OUT / "t028e1_loso_frontier.csv", ["c2_loso", "v2_loso"])
    c1 = load_ecp_loso(OUT / "t028c2_loso_frontier.csv", ["c1_loso"])

    # Normalize column subsets
    cols = ["segment_id", "method_id", "display_name", "source",
            "budget_ratio", "event_recall", "event_precision",
            "unique_event_coverage", "oracle_calls"]

    hts_norm = hts[["segment_id", "method_id", "display_name", "source",
                     "budget_ratio", "event_recall", "event_precision",
                     "unique_event_coverage", "oracle_calls_total"]].rename(
        columns={"oracle_calls_total": "oracle_calls"})
    hts_norm["segment_id"] = hts_norm["segment_id"].astype(str)

    for d in [c2, c1]:
        d["segment_id"] = d["segment_id"].astype(str)

    # For HTS baselines, aggregate over seeds
    hts_agg = hts_norm.groupby(["segment_id", "method_id", "display_name",
                                 "budget_ratio"]).agg(
        event_recall=("event_recall", "mean"),
        event_precision=("event_precision", "mean"),
        unique_event_coverage=("unique_event_coverage", "mean"),
        oracle_calls=("oracle_calls", "mean"),
    ).reset_index()

    # Combine all
    all_data = pd.concat([hts_agg, c2[cols], c1[cols]], ignore_index=True)

    # --- 2. Build absolute table ---
    methods_order = [
        "ECP-c2-globalcap", "ECP-c1", "ECP-v2-LOSO",
        "HTS-EC-safe", "EventLift-discover-certify",
        "B7-strict-replay", "D3-norepair-core-strict",
        "fixed_10s_topproxy",
    ]

    abs_rows = []
    for seg in ALL_SEGMENTS:
        for br in BUDGETS:
            for m in methods_order:
                sub = all_data[(all_data["segment_id"] == seg)
                               & (all_data["budget_ratio"] == br)
                               & (all_data["display_name"] == m)]
                if len(sub) == 0:
                    continue
                r = sub.iloc[0]
                abs_rows.append({
                    "segment": seg, "budget": br, "method": m,
                    "event_recall": round(r["event_recall"], 3),
                    "event_precision": round(r["event_precision"], 3),
                })
    abs_df = pd.DataFrame(abs_rows)
    abs_df.to_csv(OUT / "t029_benchmark_absolute.csv", index=False)

    # --- 3. Build delta-over-v2 table ---
    v2_baseline = all_data[all_data["display_name"] == "ECP-v2-LOSO"]

    delta_v2_rows = []
    for seg in ALL_SEGMENTS:
        for br in BUDGETS:
            v2_r = v2_baseline[(v2_baseline["segment_id"] == seg)
                               & (v2_baseline["budget_ratio"] == br)]
            if len(v2_r) == 0:
                continue
            v2_rec, v2_prec = v2_r.iloc[0]["event_recall"], v2_r.iloc[0]["event_precision"]
            for m in methods_order:
                if m == "ECP-v2-LOSO":
                    continue
                sub = all_data[(all_data["segment_id"] == seg)
                               & (all_data["budget_ratio"] == br)
                               & (all_data["display_name"] == m)]
                if len(sub) == 0:
                    continue
                r = sub.iloc[0]
                delta_v2_rows.append({
                    "segment": seg, "budget": br, "method": m,
                    "recall_delta": round(r["event_recall"] - v2_rec, 3),
                    "prec_delta": round(r["event_precision"] - v2_prec, 3),
                    "recall": round(r["event_recall"], 3),
                    "v2_recall": round(v2_rec, 3),
                })
    delta_v2_df = pd.DataFrame(delta_v2_rows)
    delta_v2_df.to_csv(OUT / "t029_benchmark_delta_v2.csv", index=False)

    # --- 4. Build delta-over-best table ---
    # For each (segment, budget), find the best method and compute deltas
    delta_best_rows = []
    for seg in ALL_SEGMENTS:
        for br in BUDGETS:
            seg_data = all_data[(all_data["segment_id"] == seg)
                                & (all_data["budget_ratio"] == br)
                                & (all_data["display_name"].isin(methods_order))]
            if len(seg_data) == 0:
                continue
            best_rec = seg_data["event_recall"].max()
            best_prec = seg_data["event_precision"].max()
            best_rec_method = seg_data.loc[seg_data["event_recall"].idxmax(), "display_name"]
            best_prec_method = seg_data.loc[seg_data["event_precision"].idxmax(), "display_name"]
            for m in methods_order:
                sub = seg_data[seg_data["display_name"] == m]
                if len(sub) == 0:
                    continue
                r = sub.iloc[0]
                delta_best_rows.append({
                    "segment": seg, "budget": br, "method": m,
                    "recall_delta_vs_best": round(r["event_recall"] - best_rec, 3),
                    "prec_delta_vs_best": round(r["event_precision"] - best_prec, 3),
                    "recall": round(r["event_recall"], 3),
                    "best_recall": round(best_rec, 3),
                    "best_recall_method": best_rec_method,
                    "prec": round(r["event_precision"], 3),
                    "best_prec": round(best_prec, 3),
                    "best_prec_method": best_prec_method,
                })
    delta_best_df = pd.DataFrame(delta_best_rows)
    delta_best_df.to_csv(OUT / "t029_benchmark_delta_best.csv", index=False)

    # --- 5. Build report ---
    L = []
    L.append("# T029 — ECP-c2-globalcap frozen benchmark\n")
    L.append(
        "Apples-to-apples comparison of ECP-c2 (and c1, v2) against primary baselines. "
        "All data from existing strict-replay runs; no new experiments. "
        "LOSO for ECP variants; fixed-seed strict replay for baselines.\n"
    )

    L.append("## Methods\n")
    for m in methods_order:
        L.append(f"- **{m}**")

    L.append("\n## Table A: Absolute performance (event_recall, event_precision)\n")
    L.append("| segment | budget | " + " | ".join(f"{m[:12]}" for m in methods_order) + " |")
    L.append("| " + " | ".join(["-"] * (3 + len(methods_order))) + " |")
    for seg in ALL_SEGMENTS:
        for br in BUDGETS:
            cells = []
            for m in methods_order:
                sub = abs_df[(abs_df.segment == seg) & (abs_df.budget == br) & (abs_df.method == m)]
                if len(sub):
                    r = sub.iloc[0]
                    cells.append(f"R{r['event_recall']:.3f}/P{r['event_precision']:.3f}")
                else:
                    cells.append("-")
            L.append(f"| {seg} | {br:.2f} | " + " | ".join(cells) + " |")

    L.append("\n## Table B: Recall delta over ECP-v2-LOSO\n")
    L.append("| segment | budget | " + " | ".join(m for m in methods_order if m != "ECP-v2-LOSO") + " |")
    L.append("| " + " | ".join(["-"] * (3 + len(methods_order) - 1)) + " |")
    non_v2 = [m for m in methods_order if m != "ECP-v2-LOSO"]
    for seg in ALL_SEGMENTS:
        for br in BUDGETS:
            cells = []
            for m in non_v2:
                sub = delta_v2_df[(delta_v2_df.segment == seg) & (delta_v2_df.budget == br) & (delta_v2_df.method == m)]
                if len(sub):
                    cells.append(f"{sub.iloc[0]['recall_delta']:+.3f}")
                else:
                    cells.append("-")
            L.append(f"| {seg} | {br:.2f} | " + " | ".join(cells) + " |")

    L.append("\n## Summary: wins/losses vs ECP-v2-LOSO\n")
    for m in non_v2:
        wins = (delta_v2_df[delta_v2_df.method == m]["recall_delta"] > 0.001).sum()
        losses = (delta_v2_df[delta_v2_df.method == m]["recall_delta"] < -0.001).sum()
        ties = (delta_v2_df[delta_v2_df.method == m]["recall_delta"].abs() <= 0.001).sum()
        L.append(f"- **{m}**: {wins} wins / {losses} losses / {ties} ties over v2")

    L.append("\n## Table C: Recall delta over best-per-cell\n")
    L.append("| segment | budget | " + " | ".join(f"{m[:12]}" for m in methods_order) + " | best_method |")
    L.append("| " + " | ".join(["-"] * (4 + len(methods_order))) + " |")
    for seg in ALL_SEGMENTS:
        for br in BUDGETS:
            cells = []
            best_m = ""
            for m in methods_order:
                sub = delta_best_df[(delta_best_df.segment == seg) & (delta_best_df.budget == br) & (delta_best_df.method == m)]
                if len(sub):
                    r = sub.iloc[0]
                    cells.append(f"{r['recall_delta_vs_best']:+.3f}")
                    if m == r["best_recall_method"]:
                        best_m = m[:15]
            if not cells:
                continue
            L.append(f"| {seg} | {br:.2f} | " + " | ".join(cells) + f" | {best_m} |")

    L.append("\n## Per-segment highlight\n")

    # realcartest summary
    rc = abs_df[abs_df.segment.str.startswith("realcartest")]
    d3 = abs_df[abs_df.segment.str.startswith("dataset3")]

    for label, subset in [("realcartest", rc), ("dataset3", d3)]:
        L.append(f"\n### {label}\n")
        for m in methods_order:
            sub = subset[subset.method == m]
            if len(sub) == 0:
                continue
            L.append(f"- **{m}**: mean recall={sub['event_recall'].mean():.3f}, "
                     f"mean precision={sub['event_precision'].mean():.3f} "
                     f"(n={len(sub)} cells)")

    L.append("\n## Compliance\n")
    L.append("- All methods strict-replay compliant (no online use of event_id / reference).")
    L.append("- ECP variants: LOSO cross-segment (6-fold); baselines: fixed-seed strict replay.")
    L.append("- Data sources: hts_ec_v0_strict_v1, ecp_event_coverage_policy_v1.")
    L.append("- No new VLM/GPU/oracle calls. Benchmark is aggregation-only.")

    md = OUT / "t029_benchmark_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT / 't029_benchmark_absolute.csv'}")
    print(f"wrote {OUT / 't029_benchmark_delta_v2.csv'}")
    print(f"wrote {OUT / 't029_benchmark_delta_best.csv'}")
    print(f"wrote {md}")

    return abs_df, delta_v2_df, delta_best_df


if __name__ == "__main__":
    abs_df, delta_v2_df, delta_best_df = build_benchmark()

    # Quick print
    print("\n=== ECP-c2-globalcap recall deltas over v2 ===")
    c2d = delta_v2_df[delta_v2_df.method == "ECP-c2-globalcap"]
    for _, r in c2d.iterrows():
        mark = "**" if r["recall_delta"] > 0 else ""
        print(f"  {r['segment']:25s} @{r['budget']:.2f}  {r['recall']:.3f}  delta={r['recall_delta']:+.3f}  {mark}")
    wins = (c2d["recall_delta"] > 0.001).sum()
    losses = (c2d["recall_delta"] < -0.001).sum()
    nochange = (c2d["recall_delta"].abs() <= 0.001).sum()
    print(f"  wins={wins} losses={losses} nochange={nochange}")
