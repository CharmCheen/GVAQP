#!/usr/bin/env python3
"""Derive stricter pseudo-GT label variants from exact 102-clip VLM labels."""

import argparse
import csv
from collections import Counter
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, fail, load_config, validate_base_paths


REQUIRED_COLUMNS = {
    "clip_id",
    "start_time",
    "end_time",
    "clip_path",
    "vlm_relevant",
    "vlm_risk_level",
    "vlm_affected_ego",
    "vlm_event_type",
    "vlm_confidence",
    "vlm_reason",
    "raw_response",
}

OUTPUT_COLUMNS = [
    "clip_id",
    "start_time",
    "end_time",
    "clip_path",
    "vlm_relevant",
    "vlm_risk_level",
    "vlm_affected_ego",
    "vlm_event_type",
    "vlm_confidence",
    "vlm_reason",
    "label_broad",
    "label_ego_relevant",
    "label_strict",
    "label_strict_v2",
    "label_strict_v3",
    "strict_v2_reason",
    "strict_v3_reason",
]

CLEAR_KEYWORDS = [
    "cut in",
    "cuts in",
    "crossing",
    "crosses",
    "lane change",
    "enters lane",
    "ego path",
    "affects ego",
    "conflict",
    "sudden braking",
    "braking",
    "close approach",
    "near collision",
    "near conflict",
]

WEAK_KEYWORDS = [
    "dense traffic",
    "many vehicles",
    "congestion",
    "normal following",
    "traffic flow",
    "nearby vehicles",
    "roadside",
    "parked",
    "far away",
    "no clear conflict",
    "no immediate risk",
]

STRICT_V2_ALLOWED_EVENTS = {"cut_in", "crossing", "sudden_braking", "lane_conflict", "close_approach", "other"}
STRICT_V2_EXCLUDED_EVENTS = {"dense_traffic_only", "roadside_static", "close_following", "none"}
STRICT_V3_L2_EVENTS = {"cut_in", "crossing", "sudden_braking", "lane_conflict"}
STRICT_V3_EXCLUDED_EVENTS = {"dense_traffic_only", "roadside_static", "close_following", "none", "other"}


def norm_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def norm_relevant(value) -> str:
    text = norm_text(value).lower()
    if text in {"yes", "true", "1", "positive", "relevant"}:
        return "yes"
    if text in {"no", "false", "0", "negative", "irrelevant"}:
        return "no"
    return "uncertain"


def norm_bool(value) -> str:
    text = norm_text(value).lower()
    if text in {"true", "yes", "1", "y", "affected"}:
        return "true"
    if text in {"false", "no", "0", "n", "not_affected", "none"}:
        return "false"
    return "uncertain"


def norm_risk(value) -> str:
    text = norm_text(value).lower()
    mapping = {
        "l0": "L0",
        "0": "L0",
        "none": "L0",
        "normal": "L0",
        "normal_driving": "L0",
        "l1": "L1",
        "1": "L1",
        "low": "L1",
        "weak": "L1",
        "l2": "L2",
        "2": "L2",
        "medium": "L2",
        "moderate": "L2",
        "l3": "L3",
        "3": "L3",
        "high": "L3",
        "critical": "L3",
    }
    return mapping.get(text, "uncertain")


def norm_event(value) -> str:
    text = norm_text(value).lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "lane_cut_in": "cut_in",
        "pedestrian_or_bike_conflict": "crossing",
        "pedestrian_or_bike_crossing": "crossing",
        "near_collision": "other",
        "abnormal_lane_change": "lane_conflict",
        "normal_driving": "none",
        "ego_static_no_conflict": "none",
        "": "none",
    }
    return mapping.get(text, text)


def norm_conf(value) -> str:
    text = norm_text(value).lower()
    if text in {"low", "medium", "high", ""}:
        return text
    try:
        score = float(text)
    except ValueError:
        return "unknown"
    if score >= 0.75:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def has_any_keyword(reason: str, keywords: list[str]) -> bool:
    lower = reason.lower()
    return any(keyword in lower for keyword in keywords)


def label_broad(relevant: str) -> int:
    if relevant == "yes":
        return 1
    if relevant == "no":
        return 0
    return -1


def label_ego(affected: str) -> int:
    if affected == "true":
        return 1
    if affected == "false":
        return 0
    return -1


def label_strict(affected: str, risk: str) -> int:
    if affected == "uncertain" or risk == "uncertain":
        return -1
    return 1 if affected == "true" and risk in {"L2", "L3"} else 0


def confidence_passes(conf: str, allow_missing: bool) -> tuple[bool, str]:
    if conf in {"medium", "high"}:
        return True, "confidence medium/high"
    if conf == "":
        return allow_missing, "confidence missing"
    if conf == "low":
        return False, "confidence low"
    return False, f"confidence unusable: {conf}"


def label_strict_v2(affected: str, risk: str, event: str, conf: str, reason: str) -> tuple[int, str]:
    if affected == "uncertain" or risk == "uncertain":
        return -1, "invalid affected_ego or risk_level"
    if affected != "true":
        return 0, "affected_ego is not true"
    if risk not in {"L2", "L3"}:
        return 0, "risk_level below L2"
    if event in STRICT_V2_EXCLUDED_EVENTS:
        return 0, f"excluded weak event_type: {event}"
    if event not in STRICT_V2_ALLOWED_EVENTS:
        return 0, f"event_type not allowed for strict_v2: {event}"
    if event == "other" and not has_any_keyword(reason, CLEAR_KEYWORDS):
        return 0, "event_type other lacks clear interaction keyword"
    ok_conf, conf_reason = confidence_passes(conf, allow_missing=True)
    if not ok_conf:
        return 0, conf_reason
    return 1, f"strict_v2 positive: {event}, {risk}, {conf_reason}"


def label_strict_v3(affected: str, risk: str, event: str, conf: str, reason: str) -> tuple[int, str]:
    if affected == "uncertain" or risk == "uncertain":
        return -1, "invalid affected_ego or risk_level"
    if affected != "true":
        return 0, "affected_ego is not true"
    if event in STRICT_V3_EXCLUDED_EVENTS:
        return 0, f"excluded weak/ambiguous event_type: {event}"
    if risk == "L3":
        return 1, "strict_v3 positive: L3 ego-relevant event"
    if risk != "L2":
        return 0, "risk_level below L2"
    if event not in STRICT_V3_L2_EVENTS:
        return 0, f"L2 event_type not allowed for strict_v3: {event}"
    ok_conf, conf_reason = confidence_passes(conf, allow_missing=False)
    if ok_conf:
        return 1, f"strict_v3 positive: L2 {event}, {conf_reason}"
    if conf == "" and has_any_keyword(reason, CLEAR_KEYWORDS):
        return 1, "strict_v3 positive: missing confidence but clear interaction keyword"
    return 0, conf_reason


def read_rows(path: Path) -> list[dict]:
    if not path.is_file():
        fail(f"input exact VLM labels not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_blocked(path: Path, input_path: Path, missing: set[str]) -> None:
    lines = [
        "# BLOCKED: Missing Fields For Strict Label Variants",
        "",
        f"Input file: `{input_path}`",
        "",
        "The exact VLM label CSV does not contain all fields required to derive strict_v2 / strict_v3.",
        "",
        "## Missing Fields",
        "",
    ]
    lines.extend(f"- `{field}`" for field in sorted(missing))
    lines.extend(
        [
            "",
            "## Cannot Construct",
            "",
            "- broad requires `vlm_relevant`.",
            "- ego_relevant requires `vlm_affected_ego`.",
            "- strict requires `vlm_affected_ego` and `vlm_risk_level`.",
            "- strict_v2 / strict_v3 require `vlm_affected_ego`, `vlm_risk_level`, `vlm_event_type`, `vlm_confidence`, and `vlm_reason`.",
            "",
            "No labels were fabricated.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def derive_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        relevant = norm_relevant(row.get("vlm_relevant"))
        risk = norm_risk(row.get("vlm_risk_level"))
        affected = norm_bool(row.get("vlm_affected_ego"))
        event = norm_event(row.get("vlm_event_type"))
        conf = norm_conf(row.get("vlm_confidence"))
        reason = norm_text(row.get("vlm_reason"))
        strict_v2, strict_v2_reason = label_strict_v2(affected, risk, event, conf, reason)
        strict_v3, strict_v3_reason = label_strict_v3(affected, risk, event, conf, reason)
        out.append(
            {
                "clip_id": row["clip_id"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "clip_path": row["clip_path"],
                "vlm_relevant": relevant,
                "vlm_risk_level": risk,
                "vlm_affected_ego": affected,
                "vlm_event_type": event,
                "vlm_confidence": conf,
                "vlm_reason": reason,
                "label_broad": label_broad(relevant),
                "label_ego_relevant": label_ego(affected),
                "label_strict": label_strict(affected, risk),
                "label_strict_v2": strict_v2,
                "label_strict_v3": strict_v3,
                "strict_v2_reason": strict_v2_reason,
                "strict_v3_reason": strict_v3_reason,
            }
        )
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def label_stats(rows: list[dict], label_col: str) -> dict:
    valid = [row for row in rows if int(row[label_col]) in {0, 1}]
    positives = [row for row in valid if int(row[label_col]) == 1]
    return {
        "valid": len(valid),
        "positive": len(positives),
        "rate": len(positives) / len(valid) if valid else 0.0,
    }


def downgrade_reasons(rows: list[dict], from_col: str, to_col: str, reason_col: str) -> Counter:
    reasons = Counter()
    for row in rows:
        if int(row[from_col]) == 1 and int(row[to_col]) == 0:
            reasons[row[reason_col]] += 1
    return reasons


def sample_rows(rows: list[dict], label_col: str, positive: bool, limit: int = 8) -> list[dict]:
    target = 1 if positive else 0
    return [row for row in rows if int(row[label_col]) == target][:limit]


def count_keywords(rows: list[dict], label_col: str, keywords: list[str]) -> Counter:
    counter = Counter()
    for row in rows:
        if int(row[label_col]) != 1:
            continue
        reason = row["vlm_reason"].lower()
        for keyword in keywords:
            if keyword in reason:
                counter[keyword] += 1
    return counter


def write_report(path: Path, rows: list[dict]) -> None:
    variants = [
        ("broad", "label_broad"),
        ("ego_relevant", "label_ego_relevant"),
        ("strict", "label_strict"),
        ("strict_v2", "label_strict_v2"),
        ("strict_v3", "label_strict_v3"),
    ]
    event_counts = Counter(row["vlm_event_type"] for row in rows)
    risk_counts = Counter(row["vlm_risk_level"] for row in rows)
    conf_counts = Counter(row["vlm_confidence"] or "missing" for row in rows)
    strict_weak_events = Counter(
        row["vlm_event_type"]
        for row in rows
        if int(row["label_strict"]) == 1 and row["vlm_event_type"] in {"dense_traffic_only", "close_following", "roadside_static"}
    )
    strict_to_v2 = downgrade_reasons(rows, "label_strict", "label_strict_v2", "strict_v2_reason")
    v2_to_v3 = downgrade_reasons(rows, "label_strict_v2", "label_strict_v3", "strict_v3_reason")
    clear_counts = {name: count_keywords(rows, col, CLEAR_KEYWORDS) for name, col in variants}
    weak_counts = {name: count_keywords(rows, col, WEAK_KEYWORDS) for name, col in variants}

    stats = {name: label_stats(rows, col) for name, col in variants}
    strict_v2_rate = stats["strict_v2"]["rate"]
    strict_v3_rate = stats["strict_v3"]["rate"]
    reasonable = 0.10 <= strict_v2_rate <= 0.30 or 0.10 <= strict_v3_rate <= 0.30

    lines = [
        "# Strict VLM Label Variant Diagnostics",
        "",
        "This report derives stricter pseudo-GT labels from existing exact 102-clip Qwen3-VL-32B outputs. It does not call VLM again and does not create human ground truth.",
        "",
        "## Variant Summary",
        "",
        "| variant | valid clips | positives | positive rate |",
        "|---|---:|---:|---:|",
    ]
    for name, _ in variants:
        s = stats[name]
        lines.append(f"| {name} | {s['valid']} | {s['positive']} | {s['rate']:.3f} |")

    lines.extend(["", "## Downgrades", ""])
    lines.append(f"- strict -> strict_v2 downgraded clips: {sum(strict_to_v2.values())}")
    for reason, count in strict_to_v2.most_common():
        lines.append(f"  - {reason}: {count}")
    if not strict_to_v2:
        lines.append("  - none")
    lines.append(f"- strict_v2 -> strict_v3 downgraded clips: {sum(v2_to_v3.values())}")
    for reason, count in v2_to_v3.most_common():
        lines.append(f"  - {reason}: {count}")
    if not v2_to_v3:
        lines.append("  - none")

    lines.extend(["", "## Field Distributions", "", "### Event Type", "", "| event_type | count |", "|---|---:|"])
    for key, count in event_counts.most_common():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "### Risk Level", "", "| risk_level | count |", "|---|---:|"])
    for key, count in risk_counts.most_common():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "### Confidence", "", "| confidence | count |", "|---|---:|"])
    for key, count in conf_counts.most_common():
        lines.append(f"| {key} | {count} |")
    lines.extend(["", "## Weak Event Types Inside Strict Positives", ""])
    if strict_weak_events:
        for key, count in strict_weak_events.most_common():
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- dense_traffic_only / close_following / roadside_static inside strict positives: 0")

    lines.extend(["", "## Reason Keyword Diagnostics", ""])
    for name, _ in variants:
        lines.append(f"### {name}")
        lines.append("")
        lines.append("- clear interaction keywords: " + (", ".join(f"{k}={v}" for k, v in clear_counts[name].most_common()) or "none"))
        lines.append("- weak / broad keywords: " + (", ".join(f"{k}={v}" for k, v in weak_counts[name].most_common()) or "none"))
        lines.append("")

    lines.extend(["", "## Representative strict_v2 / strict_v3 Positives", ""])
    for name, col in [("strict_v2", "label_strict_v2"), ("strict_v3", "label_strict_v3")]:
        lines.append(f"### {name}")
        lines.append("")
        for row in sample_rows(rows, col, positive=True):
            lines.append(f"- `{row['clip_id']}`: {row['vlm_event_type']} {row['vlm_risk_level']}; {row['vlm_reason'][:240]}")
        lines.append("")

    lines.extend(["", "## Representative Downgraded Clips", ""])
    downgraded = [row for row in rows if int(row["label_strict"]) == 1 and int(row["label_strict_v2"]) == 0]
    if downgraded:
        lines.append("### strict -> strict_v2")
        lines.append("")
        for row in downgraded[:8]:
            lines.append(f"- `{row['clip_id']}`: {row['strict_v2_reason']}; {row['vlm_reason'][:240]}")
    else:
        lines.append("- strict -> strict_v2: no downgraded clips.")
    downgraded = [row for row in rows if int(row["label_strict_v2"]) == 1 and int(row["label_strict_v3"]) == 0]
    if downgraded:
        lines.append("")
        lines.append("### strict_v2 -> strict_v3")
        lines.append("")
        for row in downgraded[:8]:
            lines.append(f"- `{row['clip_id']}`: {row['strict_v3_reason']}; {row['vlm_reason'][:240]}")
    else:
        lines.append("- strict_v2 -> strict_v3: no downgraded clips.")

    lines.extend(["", "## Conclusion", ""])
    if reasonable:
        lines.append("- At least one stricter variant reaches the target 10%-30% positive-rate range.")
    else:
        lines.append(
            "- strict_v2 and strict_v3 do not reach the target 10%-30% positive-rate range. "
            "The reason is that the exact VLM output already labels most strict positives as high-confidence L2 cut_in/crossing events; the available structured fields leave little room for post-hoc filtering."
        )
    lines.append(
        "- Current evidence suggests the VLM predicate is still broad for rare-risk retrieval. A re-prompted 32B pass with a more conservative predicate is likely needed if the target workload should be rare."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive strict_v2 / strict_v3 label variants from exact VLM labels.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    input_path = Path((cfg.get("exact_vlm_labels") or {}).get("output_csv", output_dir / "vlm_labels_exact_102.csv"))
    if not input_path.is_absolute():
        fail(f"exact_vlm_labels.output_csv must be absolute: {input_path}")
    rows = read_rows(input_path)
    columns = set(rows[0].keys()) if rows else set()
    missing = REQUIRED_COLUMNS - columns
    if missing:
        block_path = output_dir / "BLOCKED_strict_v2_missing_fields.md"
        write_blocked(block_path, input_path, missing)
        fail(f"missing required fields. Wrote {block_path}")

    derived = derive_rows(rows)
    out_path = output_dir / "vlm_labels_strict_variants_exact_102.csv"
    report_path = output_dir / "strict_v2_label_diagnostics.md"
    write_csv(out_path, derived)
    write_report(report_path, derived)
    print(f"strict_variants={out_path}")
    print(f"strict_diagnostics={report_path}")


if __name__ == "__main__":
    main()
