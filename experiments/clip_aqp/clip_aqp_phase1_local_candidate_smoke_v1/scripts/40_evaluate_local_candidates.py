#!/usr/bin/env python3
from __future__ import annotations

import math

import matplotlib.pyplot as plt
import pandas as pd

from local_candidate_common import OUT, append_progress, positive_series


def eval_candidate(name: str, cand: pd.DataFrame, units: pd.DataFrame, label_col: str) -> list[dict]:
    merged = cand.merge(units[["unit_id", "duration", label_col]], left_on="returned_clip_id", right_on="unit_id", how="left")
    labels = pd.to_numeric(merged[label_col], errors="coerce").fillna(0).astype(int)
    total_pos = int(pd.to_numeric(units[label_col], errors="coerce").fillna(0).astype(int).sum())
    base_rate = total_pos / len(units) if len(units) else 0.0
    rows = []
    for k in [5, 10, 20, 50, len(merged)]:
        k = min(k, len(merged))
        top = merged.head(k)
        top_labels = labels.head(k)
        positives = int(top_labels.sum())
        positive_rate = positives / k if k else 0.0
        recall = positives / total_pos if total_pos else 0.0
        duration = float(top["duration"].sum()) if "duration" in top else float((top["end_time"] - top["start_time"]).sum())
        runtime = float(top["runtime_seconds"].max()) if "runtime_seconds" in top and not top.empty else 0.0
        rows.append(
            {
                "candidate_name": name,
                "k": k,
                "label_column": label_col,
                "top_k_recall_or_positive_rate": recall,
                "precision_at_k": positive_rate,
                "enrichment_over_random": positive_rate / base_rate if base_rate > 0 else math.nan,
                "event_or_positive_coverage_if_available": recall,
                "returned_duration": duration,
                "runtime": runtime,
                "throughput_fps": "",
                "positive_count_at_k": positives,
                "total_positive_count": total_pos,
                "notes": "unit-level local-pseudo enrichment; no event IoU recall because clean event boundaries are absent",
            }
        )
    return rows


def main() -> int:
    units = pd.read_csv(OUT / "tables/local_smoke_units.csv")
    if units["human_label"].notna().any():
        label_col = "human_label_eval"
        units[label_col] = pd.to_numeric(units["human_label"], errors="coerce")
        units[label_col] = units[label_col].where(units[label_col].notna(), pd.to_numeric(units["oracle_label"], errors="coerce").fillna(0))
    else:
        label_col = "oracle_label"
    units[label_col] = pd.to_numeric(units[label_col], errors="coerce").fillna(0).astype(int)
    eval_rows = []
    for path in sorted((OUT / "candidates").glob("*.csv")):
        cand = pd.read_csv(path)
        if cand.empty or "optional_clip" in path.name:
            continue
        eval_rows.extend(eval_candidate(path.stem, cand, units, label_col))
    results = pd.DataFrame(eval_rows)
    results.to_csv(OUT / "tables/local_candidate_eval_results.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name, group in results.groupby("candidate_name"):
        ax.plot(group["k"], group["top_k_recall_or_positive_rate"], marker="o", label=name)
    ax.set_xlabel("top-k units")
    ax.set_ylabel("positive coverage")
    ax.set_title("Local Candidate Positive Coverage")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "figures/local_candidate_recall_or_enrichment.png", dpi=150)
    plt.close(fig)

    runtime = results.groupby("candidate_name", as_index=False)["runtime"].max().sort_values("runtime")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(runtime["candidate_name"], runtime["runtime"])
    ax.set_ylabel("runtime seconds")
    ax.set_title("Local Candidate Runtime")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(OUT / "figures/local_candidate_runtime.png", dpi=150)
    plt.close(fig)

    append_progress("evaluate_candidates", "python scripts/40_evaluate_local_candidates.py", f"rows={len(results)}, label_col={label_col}", next_action="generate report")
    print(f"eval_rows={len(results)} label_col={label_col}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

