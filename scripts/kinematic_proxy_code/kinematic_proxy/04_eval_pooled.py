#!/usr/bin/env python3
"""Evaluate manually labeled pooled review results."""

import argparse
from itertools import combinations
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, load_config, read_csv, to_float, validate_base_paths


METHODS = {
    "count": "score_count",
    "naive": "score_naive",
    "kinematic": "score_kinematic",
    "random": None,
}


def parse_label(row: dict) -> int | None:
    value = (row.get("label") or "").strip()
    if value == "":
        return None
    try:
        label = int(float(value))
    except ValueError:
        return None
    return label if label in {-1, 0, 1} else None


def method_rows(rows: list[dict], method: str) -> list[dict]:
    selected = [r for r in rows if method in (r.get("selected_by") or "").split("|")]
    score_col = METHODS[method]
    if score_col is None:
        return selected
    return sorted(selected, key=lambda r: to_float(r.get(score_col)), reverse=True)


def precision_at(rows: list[dict], k: int) -> float | None:
    labeled = [r for r in rows if parse_label(r) in {0, 1}]
    top = labeled[:k]
    if not top:
        return None
    return sum(1 for r in top if parse_label(r) == 1) / len(top)


def format_precision(value: float | None) -> str:
    return "NA" if value is None else f"{value:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate manually labeled pooled review CSV.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    rows = read_csv(output_dir / "review_pool.csv")

    method_sets = {m: {r["clip_id"] for r in method_rows(rows, m)} for m in METHODS}
    random_p50 = precision_at(method_rows(rows, "random"), 50)

    lines = [
        "# Kinematic Proxy Pooled Evaluation",
        "",
        "This report evaluates only the manually labeled pooled review set. Labels with `-1` are ignored.",
        "",
        "## Precision",
        "",
        "| method | labeled_n | Precision@Top-30 | Precision@Top-50 | Positive enrichment vs random@50 | unique positives found |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    positive_sets = {}
    for method in METHODS:
        ranked = method_rows(rows, method)
        labeled = [r for r in ranked if parse_label(r) in {0, 1}]
        positives = {r["clip_id"] for r in labeled if parse_label(r) == 1}
        positive_sets[method] = positives
    for method in METHODS:
        ranked = method_rows(rows, method)
        p30 = precision_at(ranked, 30)
        p50 = precision_at(ranked, 50)
        enrichment = None if p50 is None or random_p50 in {None, 0} else p50 / random_p50
        other_pos = set().union(*(positive_sets[m] for m in METHODS if m != method))
        unique_pos = len(positive_sets[method] - other_pos)
        labeled_n = sum(1 for r in ranked if parse_label(r) in {0, 1})
        lines.append(
            f"| {method} | {labeled_n} | {format_precision(p30)} | {format_precision(p50)} | "
            f"{format_precision(enrichment)} | {unique_pos} |"
        )

    lines.extend(["", "## Method Overlap", "", "| methods | overlap_n |", "|---|---:|"])
    for a, b in combinations(METHODS, 2):
        lines.append(f"| {a} & {b} | {len(method_sets[a] & method_sets[b])} |")

    lines.extend(["", "## False Positive Cases", ""])
    false_positives = [r for r in rows if parse_label(r) == 0 and any(m != "random" for m in r["selected_by"].split("|"))]
    if not false_positives:
        lines.append("No labeled false positives in the current review pool.")
    else:
        lines.append("| clip_id | selected_by | notes |")
        lines.append("|---|---|---|")
        for row in false_positives:
            notes = (row.get("notes") or "").replace("|", "\\|")
            lines.append(f"| {row['clip_id']} | {row['selected_by']} | {notes} |")

    out_path = output_dir / "eval_report.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"eval_report={out_path}")


if __name__ == "__main__":
    main()
