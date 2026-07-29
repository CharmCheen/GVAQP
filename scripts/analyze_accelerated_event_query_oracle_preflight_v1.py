#!/usr/bin/env python3
"""Evaluate only the gates frozen before AEQ oracle-preflight execution."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
PREREG = OUT / "operational_oracle/PREFLIGHT_V1_PREREGISTRATION.json"
RAW = OUT / "operational_oracle/preflight_v1/raw"
METRICS = OUT / "operational_oracle/preflight_v1/PREFLIGHT_METRICS.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, value: dict) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite preflight analysis: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-completeness-only", action="store_true")
    args = parser.parse_args()
    prereg = load(PREREG)
    sensitivity_ids = set(prereg["frame_sampling_sensitivity"]["single_sensitivity_call_candidate_ids"])
    expected = []
    for clip in prereg["clips"]:
        for repeat in range(int(prereg["repeat_policy"]["repeats_per_clip"])):
            expected.append((clip, "base", 2.0, repeat, f"{clip['candidate_id']}_fps2_r{repeat}.json"))
        if clip["candidate_id"] in sensitivity_ids:
            expected.append((clip, "fps_sensitivity", 4.0, 0, f"{clip['candidate_id']}_fps4_sensitivity.json"))
    missing = [str(RAW / clip["video_id"] / name) for clip, _, _, _, name in expected
               if not (RAW / clip["video_id"] / name).exists()]
    completeness = {
        "expected_calls": len(expected),
        "observed_calls": len(expected) - len(missing),
        "missing_artifacts": missing,
        "complete": not missing,
    }
    if args.check_completeness_only:
        print(json.dumps(completeness, indent=2, sort_keys=True))
        return
    if missing:
        raise RuntimeError(f"preflight incomplete: {len(missing)} missing calls")

    records = {}
    for clip, variant, fps, repeat, name in expected:
        record = load(RAW / clip["video_id"] / name)
        key = (clip["candidate_id"], variant, fps, repeat)
        records[key] = record

    all_rows = list(records.values())
    parse_successes = sum(row["parse_status"] == "ok" for row in all_rows)
    pair_rows = []
    exact_labels = 0
    high_confidence_polarity_flips = 0
    boundary_failures = 0
    response_set_failures = 0
    for clip in prereg["clips"]:
        left = records[(clip["candidate_id"], "base", 2.0, 0)]
        right = records[(clip["candidate_id"], "base", 2.0, 1)]
        label_equal = left["effective_label"] == right["effective_label"]
        exact_labels += int(label_equal)
        polarity = {left["effective_label"], right["effective_label"]} == {"relevant", "not_relevant"}
        both_high = left["parsed"].get("confidence") == right["parsed"].get("confidence") == "high"
        high_flip = polarity and both_high
        high_confidence_polarity_flips += int(high_flip)
        boundary_difference = None
        response_equal = None
        if left["effective_label"] == right["effective_label"] == "relevant":
            boundary_difference = max(
                abs(float(left["parsed"]["event_start_sec"]) - float(right["parsed"]["event_start_sec"])),
                abs(float(left["parsed"]["event_end_sec"]) - float(right["parsed"]["event_end_sec"])),
            )
            response_equal = set(left["parsed"]["required_response"]) == set(right["parsed"]["required_response"])
            boundary_failures += int(boundary_difference > float(
                prereg["pass_gate"]["maximum_repeat_boundary_difference_seconds_for_relevant_pairs"]
            ))
            response_set_failures += int(not response_equal)
        pair_rows.append({
            "candidate_id": clip["candidate_id"],
            "label_0": left["effective_label"],
            "label_1": right["effective_label"],
            "label_equal": label_equal,
            "raw_byte_equal": left["raw_response_sha256"] == right["raw_response_sha256"],
            "high_confidence_polarity_flip": high_flip,
            "maximum_boundary_difference_seconds": boundary_difference,
            "response_set_equal": response_equal,
        })

    sensitivity_rows = []
    sensitivity_high_flips = 0
    for candidate_id in sorted(sensitivity_ids):
        base = records[(candidate_id, "base", 2.0, 0)]
        sensitive = records[(candidate_id, "fps_sensitivity", 4.0, 0)]
        polarity = {base["effective_label"], sensitive["effective_label"]} == {"relevant", "not_relevant"}
        both_high = base["parsed"].get("confidence") == sensitive["parsed"].get("confidence") == "high"
        high_flip = polarity and both_high
        sensitivity_high_flips += int(high_flip)
        sensitivity_rows.append({
            "candidate_id": candidate_id,
            "base_label": base["effective_label"],
            "sensitivity_label": sensitive["effective_label"],
            "high_confidence_polarity_flip": high_flip,
        })

    gate = prereg["pass_gate"]
    numeric_pass = all([
        parse_successes / len(all_rows) >= float(gate["parse_success_fraction"]),
        exact_labels / len(pair_rows) >= float(gate["minimum_exact_repeat_label_agreement"]),
        high_confidence_polarity_flips <= int(gate["maximum_high_confidence_polarity_flips"]),
        boundary_failures == 0,
        response_set_failures == 0,
        sensitivity_high_flips == 0,
    ])
    result = {
        **completeness,
        "parse_success_fraction": parse_successes / len(all_rows),
        "exact_repeat_label_agreement": exact_labels / len(pair_rows),
        "high_confidence_repeat_polarity_flips": high_confidence_polarity_flips,
        "repeat_boundary_failures": boundary_failures,
        "repeat_response_set_failures": response_set_failures,
        "high_confidence_sampling_polarity_flips": sensitivity_high_flips,
        "numeric_gate_pass": numeric_pass,
        "visual_review_status": "PENDING_ADVERSARIAL_CONTACT_SHEET_REVIEW",
        "overall_gate_status": "PENDING_VISUAL_REVIEW" if numeric_pass else "FAIL_NUMERIC_GATE",
        "repeat_pairs": pair_rows,
        "sampling_sensitivity": sensitivity_rows,
    }
    write_once(METRICS, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
