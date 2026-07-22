#!/usr/bin/env python3
"""Audit whether native ARC low-budget overlap_any gains come from overcoverage."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


F1 = "event_detection@overlap_any_F1"
PRECISION = "event_detection@overlap_any_precision"
RECALL = "event_detection@overlap_any_recall"


METRIC_COLS = [
    "budget",
    "method",
    "selector",
    "variant",
    F1,
    PRECISION,
    RECALL,
    "avg_segment_duration",
    "max_segment_duration",
    "overcoverage_ratio",
    "overmerge_multiplicity",
    "references_per_predicted_segment",
    "prediction_count_error",
    "matched_mean_iou",
    "iou_0.3",
    "iou_0.5",
    "predicted_segment_count",
    "reference_event_count",
    "unique_reference_event_recall",
]


def fmt(x: float) -> str:
    if pd.isna(x):
        return "NA"
    return f"{float(x):.6f}"


def label_row(row: pd.Series) -> str:
    if row["variant"] == "native" and row["selector"].startswith("ARC-refinement@"):
        return f"{row['selector']} native"
    if row["method"] == "MAP-anchor-only + K3 BB-EM":
        return "MAP-anchor-only + K3"
    if row["variant"] == "strengthened_K3":
        return f"{row['selector']} + K3"
    return str(row["method"])


def load_rows(metrics_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(metrics_path)
    df = df[(df["aggregation"] == "mean") & (df["budget"].isin([5, 10, 20]))].copy()

    arc_native = df[
        (df["selector"].isin(["ARC-refinement@th0.3", "ARC-refinement@th0.4"]))
        & (df["variant"] == "native")
    ]
    map_k3 = df[
        (df["method"] == "MAP-anchor-only + K3 BB-EM")
        & (df["variant"] == "MAP_anchor_only_K3")
    ]

    strengthened = df[
        (df["variant"] == "strengthened_K3")
        & ~df["method"].str.contains("Ours", regex=False)
        & ~df["method"].str.contains("MAP", regex=False)
    ].copy()
    best_k3_idx = strengthened.groupby("budget")[F1].idxmax()
    best_k3 = strengthened.loc[best_k3_idx]

    selected = pd.concat([arc_native, map_k3, best_k3], ignore_index=True)
    selected = selected[METRIC_COLS].copy()
    selected["diagnostic_label"] = selected.apply(label_row, axis=1)
    selected = selected.sort_values(["budget", F1], ascending=[True, False])

    return selected, best_k3[METRIC_COLS].copy()


def build_pairwise(selected: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for budget in [5, 10, 20]:
        sub = selected[selected["budget"] == budget]
        map_row = sub[sub["diagnostic_label"] == "MAP-anchor-only + K3"].iloc[0]
        for _, comp in sub[sub["diagnostic_label"] != "MAP-anchor-only + K3"].iterrows():
            rows.append(
                {
                    "budget": budget,
                    "comparison": f"{comp['diagnostic_label']} minus MAP-anchor-only + K3",
                    "delta_F1": comp[F1] - map_row[F1],
                    "delta_precision": comp[PRECISION] - map_row[PRECISION],
                    "delta_recall": comp[RECALL] - map_row[RECALL],
                    "duration_ratio_avg": comp["avg_segment_duration"]
                    / max(map_row["avg_segment_duration"], 1e-9),
                    "duration_ratio_max": comp["max_segment_duration"]
                    / max(map_row["max_segment_duration"], 1e-9),
                    "overcoverage_ratio_multiple": comp["overcoverage_ratio"]
                    / max(map_row["overcoverage_ratio"], 1e-9),
                    "delta_matched_mean_iou": comp["matched_mean_iou"]
                    - map_row["matched_mean_iou"],
                    "delta_iou_0.3": comp["iou_0.3"] - map_row["iou_0.3"],
                    "delta_iou_0.5": comp["iou_0.5"] - map_row["iou_0.5"],
                    "delta_prediction_count_error": comp["prediction_count_error"]
                    - map_row["prediction_count_error"],
                }
            )
    return pd.DataFrame(rows)


def decision(selected: pd.DataFrame) -> str:
    arc_wins_f1 = False
    arc_boundary_bad = False
    for budget in [5, 10]:
        sub = selected[selected["budget"] == budget]
        map_row = sub[sub["diagnostic_label"] == "MAP-anchor-only + K3"].iloc[0]
        for arc_label in ["ARC-refinement@th0.3 native", "ARC-refinement@th0.4 native"]:
            arc = sub[sub["diagnostic_label"] == arc_label].iloc[0]
            if arc[F1] > map_row[F1]:
                arc_wins_f1 = True
                worse_duration = arc["max_segment_duration"] >= 3.0 * max(
                    map_row["max_segment_duration"], 1e-9
                )
                worse_coverage = arc["overcoverage_ratio"] >= 3.0 * max(
                    map_row["overcoverage_ratio"], 1e-9
                )
                worse_boundary = arc["iou_0.5"] <= map_row["iou_0.5"]
                if worse_duration or worse_coverage or worse_boundary:
                    arc_boundary_bad = True

    if arc_wins_f1 and arc_boundary_bad:
        return "MAP_BBEM_DEFENSIBLE_AS_BOUNDED_EVENT_SET_MATERIALIZATION"
    if arc_wins_f1:
        return "MAP_BBEM_LOW_BUDGET_CLAIM_LIMITED_ARC_NATIVE_STRONG"
    return "MAP_BBEM_WINS_LOW_BUDGET_DIAGNOSTIC"


def write_report(out_path: Path, selected: pd.DataFrame, pairwise: pd.DataFrame, dec: str) -> None:
    lines: list[str] = []
    lines.append("# Stage 1A Diagnostic: Native ARC vs MAP-BBEM Output Quality Audit")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append(
        "This diagnostic only reads Stage 1A aggregated metrics. It does not change oracle allocation, selected units, baseline outputs, or materialization."
    )
    lines.append("")
    lines.append("## Main Metrics")
    lines.append("")
    lines.append(
        "| budget | method | F1 | precision | recall | avg_dur | max_dur | overcoverage | overmerge | refs/pred | count_err | mean_iou | IoU@0.3 | IoU@0.5 |"
    )
    lines.append(
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    for _, r in selected.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(r["budget"])),
                    str(r["diagnostic_label"]),
                    fmt(r[F1]),
                    fmt(r[PRECISION]),
                    fmt(r[RECALL]),
                    fmt(r["avg_segment_duration"]),
                    fmt(r["max_segment_duration"]),
                    fmt(r["overcoverage_ratio"]),
                    fmt(r["overmerge_multiplicity"]),
                    fmt(r["references_per_predicted_segment"]),
                    fmt(r["prediction_count_error"]),
                    fmt(r["matched_mean_iou"]),
                    fmt(r["iou_0.3"]),
                    fmt(r["iou_0.5"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Pairwise Deltas vs MAP-anchor-only + K3")
    lines.append("")
    lines.append(
        "| budget | comparison | delta_F1 | max_dur_ratio | overcoverage_multiple | delta_mean_iou | delta_IoU@0.3 | delta_IoU@0.5 |"
    )
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|")
    for _, r in pairwise.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(r["budget"])),
                    str(r["comparison"]),
                    fmt(r["delta_F1"]),
                    fmt(r["duration_ratio_max"]),
                    fmt(r["overcoverage_ratio_multiple"]),
                    fmt(r["delta_matched_mean_iou"]),
                    fmt(r["delta_iou_0.3"]),
                    fmt(r["delta_iou_0.5"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "ARC-refinement@th0.3 native has the strongest B=5/10 overlap_any F1, but it uses much longer and broader predictions: max duration is 150s and overcoverage is about 4.5x reference duration. Its IoU@0.5 is 0 at B=5/10."
    )
    lines.append(
        "ARC-refinement@th0.4 native is less extreme, but at B=5/10 it still has 50s max duration and materially higher overcoverage than MAP+K3. At B=10 its F1 is effectively tied with MAP+K3, while MAP+K3 has precision 1.0, 10s max duration, lower overcoverage, and slightly higher IoU@0.5."
    )
    lines.append(
        "At B=20, MAP+K3 has the best F1 among the audited rows and keeps bounded durations, lower overcoverage, and better IoU@0.5 than ARC native."
    )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(dec)
    lines.append("")
    if dec == "MAP_BBEM_DEFENSIBLE_AS_BOUNDED_EVENT_SET_MATERIALIZATION":
        lines.append(
            "Conclusion: native ARC's B=5/10 overlap_any advantage is not clean evidence of better event localization. It is strongly coupled to aggressive output duration/overcoverage, especially ARC@th0.3. MAP-BBEM should be defended as bounded event-set materialization; low-budget claims should still state that native ARC can win overlap_any at B=5/10 under permissive overlap_any scoring."
        )
    else:
        lines.append(
            "Conclusion: MAP-BBEM's low-budget claim should be limited according to the diagnostic decision above."
        )
    out_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metrics_csv",
        default="outputs/stage_1a_map_anchor_only/metrics_by_run.csv",
    )
    parser.add_argument(
        "--out_dir",
        default="outputs/stage_1a_diagnostic_native_arc_vs_map_bbem",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    selected, best_k3 = load_rows(Path(args.metrics_csv))
    pairwise = build_pairwise(selected)
    dec = decision(selected)

    selected.to_csv(out_dir / "diagnostic_metrics.csv", index=False)
    best_k3.to_csv(out_dir / "best_baseline_k3_by_budget.csv", index=False)
    pairwise.to_csv(out_dir / "pairwise_vs_map.csv", index=False)
    write_report(out_dir / "FINAL_REPORT.md", selected, pairwise, dec)

    print(f"wrote {out_dir}")
    print(f"decision={dec}")


if __name__ == "__main__":
    main()
