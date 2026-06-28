#!/usr/bin/env python3
"""Analyze human audit labels for roadclip_budget_v2."""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, load_config, read_csv, to_float, validate_base_paths, write_csv


AUDIT_COLUMNS = [
    "human_label",
    "human_event_type",
    "human_reason",
    "human_confidence",
    "error_type",
]

EVENT_TYPES = [
    "cut_in",
    "crossing",
    "sudden_braking",
    "lane_conflict",
    "close_approach",
    "normal_following",
    "dense_traffic_only",
    "roadside_static",
    "far_vehicle",
    "ambiguous",
    "none",
    "other",
]

ERROR_TYPES = [
    "correct",
    "vlm_false_positive_normal_following",
    "vlm_false_positive_dense_traffic",
    "vlm_false_positive_roadside_static",
    "vlm_false_positive_far_vehicle",
    "vlm_false_positive_ambiguous",
    "vlm_false_negative_cut_in",
    "vlm_false_negative_crossing",
    "vlm_false_negative_close_approach",
    "human_uncertain",
    "other",
]


def norm_text(value: str | None) -> str:
    return (value or "").strip().lower()


def norm_human_label(value: str | None) -> int | None:
    text = norm_text(value)
    if text in {"1", "positive", "pos", "yes", "y", "true"}:
        return 1
    if text in {"0", "negative", "neg", "no", "n", "false"}:
        return 0
    if text in {"-1", "uncertain", "unknown", "unsure", "u"}:
        return -1
    return None


def norm_vlm_positive(row: dict) -> int:
    return 1 if norm_text(row.get("conservative_positive")) == "yes" else 0


def rate(num: float, den: float) -> float:
    return num / den if den else 0.0


def fmt(value: float) -> str:
    if math.isnan(value):
        return "nan"
    return f"{value:.3f}"


def write_todo(output_dir: Path, manifest_path: Path, labeled_path: Path, reason: str) -> Path:
    path = output_dir / "TODO_human_audit.md"
    text = f"""# TODO: Human Audit Labels Needed

Status: AUDIT_INCOMPLETE

Reason: {reason}

Please copy:

```text
{manifest_path}
```

to:

```text
{labeled_path}
```

Then fill these columns:

- `human_label`: `1` = true ego-relevant risk / path conflict; `0` = not ego-relevant risk; `-1` = uncertain.
- `human_event_type`: one of `{', '.join(EVENT_TYPES)}`.
- `human_reason`: short explanation for the human decision.
- `human_confidence`: `low`, `medium`, or `high`.
- `error_type`: one of `{', '.join(ERROR_TYPES)}`.

After labeling, run:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
python experiments/roadclip_budget_v2/08_analyze_human_audit.py --config experiments/roadclip_budget_v2/config.yaml
```

This script does not call VLM, rerun YOLO, or modify pseudo labels.
"""
    path.write_text(text, encoding="utf-8")
    return path


def choose_manifest(output_dir: Path) -> tuple[Path, list[dict], bool]:
    audit_dir = output_dir / "audit_package"
    labeled = audit_dir / "audit_manifest_labeled.csv"
    manifest = audit_dir / "audit_manifest.csv"
    if labeled.is_file():
        return labeled, read_csv(labeled), True
    if manifest.is_file():
        return manifest, read_csv(manifest), False
    raise FileNotFoundError(f"missing audit manifest: {manifest}")


def split_reasons(value: str | None) -> list[str]:
    text = (value or "").strip()
    if not text:
        return ["unspecified"]
    return [part.strip() for part in text.split(";") if part.strip()] or ["unspecified"]


def average_precision(scored_rows: list[dict], score_name: str) -> float:
    rows = sorted(scored_rows, key=lambda r: to_float(r.get(score_name)), reverse=True)
    total_pos = sum(1 for r in rows if r["_human_label"] == 1)
    if total_pos == 0:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for rank, row in enumerate(rows, start=1):
        if row["_human_label"] == 1:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / total_pos


def precision_at_k(scored_rows: list[dict], score_name: str, k: int) -> float:
    if not scored_rows:
        return 0.0
    rows = sorted(scored_rows, key=lambda r: to_float(r.get(score_name)), reverse=True)
    top = rows[: min(k, len(rows))]
    if not top:
        return 0.0
    return sum(1 for r in top if r["_human_label"] == 1) / len(top)


def proxy_ranking_table(labeled_binary: list[dict]) -> list[dict]:
    rows = []
    for score_name in ["score_count", "score_naive", "score_kinematic"]:
        rows.append(
            {
                "score": score_name,
                "precision_at_10": precision_at_k(labeled_binary, score_name, 10),
                "precision_at_20": precision_at_k(labeled_binary, score_name, 20),
                "average_precision": average_precision(labeled_binary, score_name),
            }
        )
    return rows


def sample_reason_precision(rows: list[dict]) -> list[dict]:
    stats: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        human = row["_human_label"]
        if human not in {0, 1}:
            continue
        vlm = row["_vlm_positive"]
        for reason in split_reasons(row.get("sample_reason")):
            if vlm == 1:
                stats[reason]["vlm_positive"] += 1
                if human == 1:
                    stats[reason]["tp"] += 1
                else:
                    stats[reason]["fp"] += 1
            stats[reason]["audited_binary"] += 1
            if human == 1:
                stats[reason]["human_positive"] += 1
    out = []
    for reason, counter in sorted(stats.items()):
        out.append(
            {
                "sample_reason": reason,
                "audited_binary": counter["audited_binary"],
                "human_positive": counter["human_positive"],
                "vlm_positive": counter["vlm_positive"],
                "tp": counter["tp"],
                "fp": counter["fp"],
                "vlm_precision": rate(counter["tp"], counter["vlm_positive"]),
            }
        )
    return out


def make_markdown_table(rows: list[dict], columns: list[str], float_cols: set[str] | None = None) -> str:
    if not rows:
        return "_No rows._"
    float_cols = float_cols or set()
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        values = []
        for col in columns:
            value = row.get(col, "")
            if col in float_cols:
                value = fmt(float(value))
            values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def determine_status(
    audited_count: int,
    precision: float,
    fn: int,
    human_pos: int,
    high_score_fn: int,
    fp_error_counts: Counter,
) -> tuple[str, list[str]]:
    reasons = []
    if audited_count < 20:
        return "AUDIT_INCOMPLETE", ["audited clips < 20"]
    fn_rate = rate(fn, human_pos)
    if precision < 0.5:
        reasons.append("VLM precision < 0.5")
    if fn_rate > 0.25 or high_score_fn >= 5:
        reasons.append("many human positives were VLM negatives")
    if reasons:
        return "AUDIT_FAIL", reasons
    broad_fp = (
        fp_error_counts["vlm_false_positive_normal_following"]
        + fp_error_counts["vlm_false_positive_dense_traffic"]
    )
    if 0.5 <= precision < 0.75:
        reasons.append("VLM precision between 0.5 and 0.75")
    if broad_fp and broad_fp >= max(3, sum(fp_error_counts.values()) * 0.5):
        reasons.append("false positives concentrated in normal_following / dense_traffic")
    if reasons:
        return "AUDIT_WEAK", reasons
    if audited_count >= 50 and precision >= 0.75 and high_score_fn < 5:
        return "AUDIT_PASS", ["audited clips >= 50, precision >= 0.75, no large high-score FN cluster"]
    return "AUDIT_WEAK", ["audited clips < 50 or residual uncertainty remains"]


def analyze(output_dir: Path, manifest_path: Path, rows: list[dict]) -> dict:
    for row in rows:
        row["_human_label"] = norm_human_label(row.get("human_label"))
        row["_vlm_positive"] = norm_vlm_positive(row)

    audited = [r for r in rows if r["_human_label"] is not None]
    binary = [r for r in audited if r["_human_label"] in {0, 1}]
    uncertain = [r for r in audited if r["_human_label"] == -1]

    human_pos = sum(1 for r in binary if r["_human_label"] == 1)
    human_neg = sum(1 for r in binary if r["_human_label"] == 0)
    vlm_pos = sum(1 for r in binary if r["_vlm_positive"] == 1)
    vlm_neg = sum(1 for r in binary if r["_vlm_positive"] == 0)

    tp = sum(1 for r in binary if r["_human_label"] == 1 and r["_vlm_positive"] == 1)
    fp = sum(1 for r in binary if r["_human_label"] == 0 and r["_vlm_positive"] == 1)
    tn = sum(1 for r in binary if r["_human_label"] == 0 and r["_vlm_positive"] == 0)
    fn = sum(1 for r in binary if r["_human_label"] == 1 and r["_vlm_positive"] == 0)

    precision = rate(tp, tp + fp)
    recall = rate(tp, tp + fn)
    specificity = rate(tn, tn + fp)
    f1 = rate(2 * precision * recall, precision + recall)

    false_positives = [r for r in binary if r["_human_label"] == 0 and r["_vlm_positive"] == 1]
    false_negatives = [r for r in binary if r["_human_label"] == 1 and r["_vlm_positive"] == 0]
    fp_error_counts = Counter(norm_text(r.get("error_type")) or "unspecified" for r in false_positives)
    fn_error_counts = Counter(norm_text(r.get("error_type")) or "unspecified" for r in false_negatives)
    human_event_counts = Counter(norm_text(r.get("human_event_type")) or "unspecified" for r in audited)

    count_sorted_vlm_neg = sorted(
        [r for r in binary if r["_vlm_positive"] == 0],
        key=lambda r: to_float(r.get("score_count")),
        reverse=True,
    )
    top20_vlm_neg = count_sorted_vlm_neg[:20]
    high_score_count_human_pos = [r for r in top20_vlm_neg if r["_human_label"] == 1]
    top_count_negative_sample_human_pos = [
        r
        for r in binary
        if r["_human_label"] == 1
        and r["_vlm_positive"] == 0
        and "top_count_high_score_negative" in (r.get("sample_reason") or "")
    ]

    proxy_rows = proxy_ranking_table(binary)
    reason_rows = sample_reason_precision(audited)

    status, status_reasons = determine_status(
        len(audited),
        precision,
        fn,
        human_pos,
        len(high_score_count_human_pos),
        fp_error_counts,
    )

    confusion_rows = [
        {"vlm_prediction": "positive", "human_label": "positive", "count": tp},
        {"vlm_prediction": "positive", "human_label": "negative", "count": fp},
        {"vlm_prediction": "negative", "human_label": "positive", "count": fn},
        {"vlm_prediction": "negative", "human_label": "negative", "count": tn},
        {"vlm_prediction": "any", "human_label": "uncertain", "count": len(uncertain)},
    ]
    write_csv(output_dir / "human_audit_confusion.csv", confusion_rows, ["vlm_prediction", "human_label", "count"])

    error_rows = []
    for kind, error_group in [("false_positive", false_positives), ("false_negative", false_negatives)]:
        for r in error_group:
            error_rows.append(
                {
                    "error_kind": kind,
                    "clip_id": r.get("clip_id", ""),
                    "sample_reason": r.get("sample_reason", ""),
                    "conservative_positive": r.get("conservative_positive", ""),
                    "event_type": r.get("event_type", ""),
                    "negative_reason": r.get("negative_reason", ""),
                    "human_label": r.get("human_label", ""),
                    "human_event_type": r.get("human_event_type", ""),
                    "error_type": r.get("error_type", ""),
                    "score_count": r.get("score_count", ""),
                    "score_naive": r.get("score_naive", ""),
                    "score_kinematic": r.get("score_kinematic", ""),
                    "human_reason": r.get("human_reason", ""),
                    "evidence": r.get("evidence", ""),
                    "clip_path": r.get("clip_path", ""),
                }
            )
    write_csv(
        output_dir / "human_audit_errors.csv",
        error_rows,
        [
            "error_kind",
            "clip_id",
            "sample_reason",
            "conservative_positive",
            "event_type",
            "negative_reason",
            "human_label",
            "human_event_type",
            "error_type",
            "score_count",
            "score_naive",
            "score_kinematic",
            "human_reason",
            "evidence",
            "clip_path",
        ],
    )

    report = []
    report.append("# Roadclip V2 Human Audit Analysis\n")
    report.append(f"STATUS: {status}\n")
    report.append("These metrics use human labels only inside the audit package. They are not full 500-clip human GT.\n")
    report.append("## Inputs\n")
    report.append(f"- manifest: `{manifest_path}`")
    report.append(f"- rows in manifest: {len(rows)}")
    report.append(f"- audited clips with valid human_label: {len(audited)}")
    report.append(f"- binary audited clips: {len(binary)}")
    report.append(f"- uncertain clips: {len(uncertain)}\n")

    report.append("## Label Counts\n")
    report.append(f"- human positives: {human_pos}")
    report.append(f"- human negatives: {human_neg}")
    report.append(f"- human positive rate among binary labels: {fmt(rate(human_pos, len(binary)))}")
    report.append(f"- conservative VLM positives among binary labels: {vlm_pos}")
    report.append(f"- conservative VLM negatives among binary labels: {vlm_neg}\n")

    report.append("## VLM Confusion And Quality\n")
    report.append(f"- TP: {tp}")
    report.append(f"- FP: {fp}")
    report.append(f"- TN: {tn}")
    report.append(f"- FN: {fn}")
    report.append(f"- precision: {fmt(precision)}")
    report.append(f"- recall: {fmt(recall)}")
    report.append(f"- specificity: {fmt(specificity)}")
    report.append(f"- F1: {fmt(f1)}\n")

    report.append("## Error Distributions\n")
    report.append("### False Positive error_type\n")
    report.append(make_markdown_table([{"error_type": k, "count": v} for k, v in fp_error_counts.most_common()], ["error_type", "count"]))
    report.append("\n### False Negative error_type\n")
    report.append(make_markdown_table([{"error_type": k, "count": v} for k, v in fn_error_counts.most_common()], ["error_type", "count"]))
    report.append("\n### human_event_type\n")
    report.append(make_markdown_table([{"human_event_type": k, "count": v} for k, v in human_event_counts.most_common()], ["human_event_type", "count"]))
    report.append("")

    report.append("## Sample-Reason VLM Precision\n")
    report.append(
        make_markdown_table(
            reason_rows,
            ["sample_reason", "audited_binary", "human_positive", "vlm_positive", "tp", "fp", "vlm_precision"],
            {"vlm_precision"},
        )
    )
    report.append("")

    report.append("## High score_count Negative Check\n")
    report.append(f"- human positives among top-20 VLM-negative clips ranked by score_count: {len(high_score_count_human_pos)}")
    report.append(f"- human positives in `top_count_high_score_negative` sample and VLM-negative: {len(top_count_negative_sample_human_pos)}")
    if high_score_count_human_pos:
        report.append("")
        report.append(
            make_markdown_table(
                [
                    {
                        "clip_id": r.get("clip_id", ""),
                        "score_count": to_float(r.get("score_count")),
                        "human_event_type": r.get("human_event_type", ""),
                        "error_type": r.get("error_type", ""),
                    }
                    for r in high_score_count_human_pos[:10]
                ],
                ["clip_id", "score_count", "human_event_type", "error_type"],
                {"score_count"},
            )
        )
    report.append("")

    report.append("## Audited-Subset Proxy Ranking Sanity Check\n")
    report.append(
        make_markdown_table(
            proxy_rows,
            ["score", "precision_at_10", "precision_at_20", "average_precision"],
            {"precision_at_10", "precision_at_20", "average_precision"},
        )
    )
    report.append("")

    report.append("## Decision\n")
    for reason in status_reasons:
        report.append(f"- status reason: {reason}")
    if status == "AUDIT_PASS":
        report.append("- roadclip_v2 preliminary acceleration can be retained as pseudo-GT-based evidence, with human-audit caveats.")
        report.append("- no immediate conservative VLM re-prompt is required before expanding to more videos.")
        report.append("- count / temporal allocation remains a valid main line.")
    elif status == "AUDIT_WEAK":
        report.append("- roadclip_v2 preliminary acceleration should be kept as weak evidence only.")
        report.append("- inspect error clusters before relying on conservative VLM as pseudo-oracle.")
        report.append("- count / temporal allocation can continue, but claims should be qualified.")
    elif status == "AUDIT_FAIL":
        report.append("- roadclip_v2 preliminary acceleration should not be treated as reliable.")
        report.append("- re-prompt or redesign conservative VLM labeling before scaling.")
        report.append("- budget allocation results may be dominated by pseudo-label errors.")
    else:
        report.append("- audit is incomplete; no conclusion about pseudo-GT quality yet.")
    report.append("- expand to more videos only after audit status is not AUDIT_FAIL.\n")

    report_path = output_dir / "human_audit_analysis.md"
    report_path.write_text("\n".join(report), encoding="utf-8")

    return {
        "status": status,
        "audited": len(audited),
        "binary": len(binary),
        "human_pos": human_pos,
        "human_neg": human_neg,
        "uncertain": len(uncertain),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "report": report_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    audit_dir = output_dir / "audit_package"
    labeled_path = audit_dir / "audit_manifest_labeled.csv"
    manifest_path = audit_dir / "audit_manifest.csv"

    try:
        chosen_path, rows, using_labeled_file = choose_manifest(output_dir)
    except FileNotFoundError as exc:
        todo = write_todo(output_dir, manifest_path, labeled_path, str(exc))
        print(f"status=AUDIT_INCOMPLETE todo={todo}")
        return

    missing_cols = [col for col in AUDIT_COLUMNS if rows and col not in rows[0]]
    if missing_cols:
        todo = write_todo(output_dir, manifest_path, labeled_path, f"missing audit columns: {missing_cols}")
        print(f"status=AUDIT_INCOMPLETE todo={todo}")
        return

    valid_labels = sum(1 for row in rows if norm_human_label(row.get("human_label")) is not None)
    if valid_labels == 0:
        source_note = "audit_manifest_labeled.csv not found" if not using_labeled_file else "no valid human_label values"
        todo = write_todo(output_dir, manifest_path, labeled_path, source_note)
        print(f"status=AUDIT_INCOMPLETE todo={todo}")
        return

    result = analyze(output_dir, chosen_path, rows)
    print(f"status={result['status']}")
    print(f"audited={result['audited']} binary={result['binary']} human_pos={result['human_pos']}")
    print(f"precision={fmt(result['precision'])} recall={fmt(result['recall'])} f1={fmt(result['f1'])}")
    print(f"report={result['report']}")


if __name__ == "__main__":
    main()
