#!/usr/bin/env python3
"""Authenticate and evaluate only the gates frozen for AEQ preflight V2."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from garc_eval.accelerated_event_query.oracle_protocol import (
    canonical_hash,
    parse_response_strict,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/accelerated_event_query_v1"
PREREG = OUT / "operational_oracle/PREFLIGHT_V2_PREREGISTRATION.json"
RAW = OUT / "operational_oracle/preflight_v2/raw"
ATTEMPTS = OUT / "operational_oracle/preflight_v2/attempts"
METRICS = OUT / "operational_oracle/preflight_v2/PREFLIGHT_METRICS_V2.json"
RUNNER_PATH = ROOT / "scripts/run_accelerated_event_query_oracle_preflight_v2.py"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_runner():
    spec = importlib.util.spec_from_file_location("aeq_preflight_v2_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import V2 runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_attempt_chain(path: Path) -> list[dict]:
    if not path.exists():
        raise RuntimeError(f"missing attempt ledger: {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    previous = None
    starts = {}
    terminals = set()
    for row in rows:
        claimed = row.get("event_sha256")
        payload = {key: value for key, value in row.items() if key != "event_sha256"}
        if row.get("previous_event_sha256") != previous or claimed != canonical_hash(payload):
            raise RuntimeError(f"invalid attempt hash chain: {path}")
        previous = claimed
        attempt = row.get("attempt_id")
        if row.get("event") == "STARTED":
            if attempt in starts:
                raise RuntimeError("duplicate STARTED attempt")
            starts[attempt] = row
        elif row.get("event") in {"ACCEPTED", "FAILED", "RECOVERED_ACCEPTED", "RECOVERED_UNCERTAIN"}:
            if attempt not in starts or attempt in terminals:
                raise RuntimeError("orphan or duplicate terminal attempt")
            if (row.get("artifact"), row.get("input_identity_sha256")) != (
                starts[attempt].get("artifact"), starts[attempt].get("input_identity_sha256")
            ):
                raise RuntimeError("attempt terminal identity mismatch")
            terminals.add(attempt)
        else:
            raise RuntimeError("unknown attempt event")
    if set(starts) != terminals:
        raise RuntimeError(f"unterminated attempts in {path}")
    return rows


def expected_calls() -> tuple[object, dict, dict, dict, list[dict]]:
    runner = load_runner()
    prereg, _, selection, _, frame_sets = runner.frozen_context()
    calls = []
    for shard in runner.SHARDS:
        for call in runner.schedule_for_shard(prereg, selection, shard):
            frame_set = frame_sets[(call["clip"]["candidate_id"], call["sampling_fps"])]
            calls.append({
                "shard": shard,
                "call": call,
                "frame_set": frame_set,
                "artifact": runner.artifact_name(call),
                "identity": runner.identity_payload(prereg, call, frame_set),
            })
    review = load(ROOT / prereg["bindings"]["review_consensus_path"])
    return runner, prereg, selection, review, calls


def validate_record(runner, expected: dict, record: dict) -> None:
    claimed = record.get("record_sha256")
    payload = {key: value for key, value in record.items() if key != "record_sha256"}
    if claimed != canonical_hash(payload):
        raise RuntimeError(f"record self-hash mismatch: {expected['artifact']}")
    if record.get("identity") != expected["identity"]:
        raise RuntimeError(f"identity payload mismatch: {expected['artifact']}")
    if record.get("input_identity_sha256") != canonical_hash(expected["identity"]):
        raise RuntimeError(f"input identity hash mismatch: {expected['artifact']}")
    if record.get("frames") != expected["frame_set"]["frames"]:
        raise RuntimeError(f"frame identity mismatch: {expected['artifact']}")
    model_hash = runner.model_input_identity(expected["identity"], [
        {**frame, "rgb": None} for frame in expected["frame_set"]["frames"]
    ])
    if record.get("model_input_identity_sha256") != model_hash:
        raise RuntimeError(f"model-input identity mismatch: {expected['artifact']}")
    raw = record.get("raw")
    if not isinstance(raw, str) or record.get("raw_response_sha256") != hashlib.sha256(raw.encode()).hexdigest():
        raise RuntimeError(f"raw hash mismatch: {expected['artifact']}")
    parsed, status = parse_response_strict(raw)
    effective = parsed.get("label") if status == "ok" else "parse_failure"
    if (record.get("parsed"), record.get("parse_status"), record.get("effective_label")) != (parsed, status, effective):
        raise RuntimeError(f"stored parse mismatch: {expected['artifact']}")
    runtime = record.get("runtime", {})
    declared = runtime.get("declared_physical_gpus")
    identities = runtime.get("gpu_identities")
    if not isinstance(declared, list) or len(declared) != 2 or not isinstance(identities, list) or len(identities) != 2:
        raise RuntimeError(f"invalid runtime GPU provenance: {expected['artifact']}")
    if any(not isinstance(text, str) or not text.startswith(f"{index},")
           for text, index in zip(identities, declared)):
        raise RuntimeError(f"GPU identity/declaration mismatch: {expected['artifact']}")


def evaluate_records(prereg: dict, selection: dict, review: dict, records: dict) -> dict:
    """Evaluate authenticated records; keys are (execution_shard, artifact name)."""
    clips = {row["candidate_id"]: row for row in selection["clips"]}
    base = {}
    pairs = []
    reproducible = True
    for candidate, clip in clips.items():
        shard = clip["video_id"]
        left = records[(shard, f"{candidate}_fps2_r0.json")]
        right = records[(shard, f"{candidate}_fps2_r1.json")]
        equal_input = left["model_input_identity_sha256"] == right["model_input_identity_sha256"]
        equal_raw = left["raw_response_sha256"] == right["raw_response_sha256"]
        pair_ok = equal_input and equal_raw and left["parse_status"] == right["parse_status"] == "ok"
        reproducible &= pair_ok
        consensus = left["effective_label"] if pair_ok else None
        base[candidate] = left if consensus is not None else None
        pairs.append({"candidate_id": candidate, "model_input_equal": equal_input,
                      "raw_equal": equal_raw, "reproducible": pair_ok, "consensus_label": consensus})

    anchor = prereg["workload"]["cross_replica_anchor_candidate_id"]
    anchor_rows = [records[("DALI", f"{anchor}_fps2_r0.json")]] + [
        records[(shard, f"{anchor}_fps2_cross_replica_{shard}.json")]
        for shard in ("HANGZHOU", "WUHAN")
    ]
    cross_replica = (
        len({row["model_input_identity_sha256"] for row in anchor_rows}) == 1
        and len({row["raw_response_sha256"] for row in anchor_rows}) == 1
        and all(row["parse_status"] == "ok" for row in anchor_rows)
    )

    consensus_rows = [(candidate, clips[candidate]["video_id"], row["effective_label"])
                      for candidate, row in base.items() if row is not None]
    label_counts = Counter(label for _, _, label in consensus_rows)
    label_videos = defaultdict(set)
    unknown_by_video = Counter()
    for _, video, label in consensus_rows:
        label_videos[label].add(video)
        if label == "unknown":
            unknown_by_video[video] += 1
    gates = prereg["gates"]
    class_support = all([
        label_counts["relevant"] >= gates["minimum_consensus_relevant_clips"],
        len(label_videos["relevant"]) >= gates["minimum_consensus_relevant_videos"],
        label_counts["not_relevant"] >= gates["minimum_consensus_not_relevant_clips"],
        len(label_videos["not_relevant"]) >= gates["minimum_consensus_not_relevant_videos"],
        label_counts["unknown"] <= gates["maximum_consensus_unknown_clips"],
        max(unknown_by_video.values(), default=0) <= gates["maximum_consensus_unknown_per_video"],
    ])

    sensitivity = []
    polarity_failures = unknown_transitions = boundary_failures = response_failures = 0
    for candidate in prereg["workload"]["sensitivity_candidate_ids"]:
        shard = clips[candidate]["video_id"]
        primary = base[candidate]
        dense = records[(shard, f"{candidate}_fps4_sensitivity.json")]
        base_label = primary["effective_label"] if primary else None
        dense_label = dense["effective_label"] if dense["parse_status"] == "ok" else None
        polarity = {base_label, dense_label} == {"relevant", "not_relevant"}
        unknown_transition = base_label != dense_label and "unknown" in {base_label, dense_label}
        boundary_difference = None
        response_equal = None
        if base_label == dense_label == "relevant":
            boundary_difference = max(
                abs(float(primary["parsed"]["event_start_sec"]) - float(dense["parsed"]["event_start_sec"])),
                abs(float(primary["parsed"]["event_end_sec"]) - float(dense["parsed"]["event_end_sec"])),
            )
            response_equal = set(primary["parsed"]["required_response"]) == set(dense["parsed"]["required_response"])
            boundary_failures += int(boundary_difference > gates["sensitivity_relevant_boundary_max_difference_seconds"])
            response_failures += int(not response_equal)
        polarity_failures += int(polarity)
        unknown_transitions += int(unknown_transition)
        sensitivity.append({"candidate_id": candidate, "base_label": base_label,
                            "sensitivity_label": dense_label, "polarity_flip": polarity,
                            "unknown_transition": unknown_transition,
                            "maximum_boundary_difference_seconds": boundary_difference,
                            "response_set_equal": response_equal})

    review_by_id = {row["candidate_id"]: row for row in review["reviews"]}
    semantic = []
    contradictions = []
    model_unknown_on_decided = []
    positive_claims = []
    for candidate, clip in clips.items():
        model = base[candidate]
        model_label = model["effective_label"] if model else None
        review_label = review_by_id[candidate]["label"]
        opposite = {model_label, review_label} == {"relevant", "not_relevant"}
        if opposite:
            contradictions.append({"candidate_id": candidate, "video_id": clip["video_id"],
                                   "model_label": model_label, "review_label": review_label})
        if model_label == "unknown" and review_label in {"relevant", "not_relevant"}:
            model_unknown_on_decided.append(candidate)
        if model_label == "relevant":
            positive_claims.append({"candidate_id": candidate, "cause": model["parsed"]["cause"],
                                    "evidence": model["parsed"]["evidence"]})
        semantic.append({"candidate_id": candidate, "model_label": model_label,
                         "review_label": review_label, "decided_polarity_contradiction": opposite})
    contradiction_videos = {row["video_id"] for row in contradictions}
    systematic = len(contradictions) >= 2 and len(contradiction_videos) >= 2

    all_records = list(records.values())
    parse_success = sum(row["parse_status"] == "ok" for row in all_records) / len(all_records)
    numeric_pass = all([
        parse_success >= gates["parse_success_fraction"], reproducible, cross_replica,
        class_support, polarity_failures == 0, boundary_failures == 0, response_failures == 0,
    ])
    review_required = bool(unknown_transitions or contradictions or model_unknown_on_decided)
    if not numeric_pass:
        overall = "FAIL_NUMERIC_OR_SUPPORT_GATE"
    elif systematic:
        overall = "FAIL_SYSTEMATIC_SEMANTIC_GATE"
    elif review_required:
        overall = "REVIEW_REQUIRED"
    else:
        overall = "PENDING_INDEPENDENT_CLAIM_GROUNDING_REVIEW"
    return {
        "parse_success_fraction": parse_success,
        "same_process_reproducibility_pass": reproducible,
        "cross_replica_reproducibility_pass": cross_replica,
        "class_support_pass": class_support,
        "consensus_label_counts": dict(label_counts),
        "consensus_label_videos": {key: sorted(value) for key, value in label_videos.items()},
        "unknown_counts_by_video": dict(unknown_by_video),
        "sampling_polarity_failures": polarity_failures,
        "sampling_unknown_transitions": unknown_transitions,
        "sampling_boundary_failures": boundary_failures,
        "sampling_response_set_failures": response_failures,
        "semantic_contradictions": contradictions,
        "model_unknown_on_review_decided": model_unknown_on_decided,
        "systematic_semantic_failure": systematic,
        "positive_claims_pending_grounding": positive_claims,
        "numeric_gate_pass": numeric_pass,
        "overall_gate_status": overall,
        "repeat_pairs": pairs,
        "sampling_sensitivity": sensitivity,
        "semantic_screen": semantic,
    }


def write_once(path: Path, value: dict) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite metrics: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-completeness-only", action="store_true")
    args = parser.parse_args()
    runner, prereg, selection, review, calls = expected_calls()
    missing = [str((RAW / row["shard"] / row["artifact"]).relative_to(ROOT))
               for row in calls if not (RAW / row["shard"] / row["artifact"]).exists()]
    completeness = {"expected_calls": len(calls), "observed_calls": len(calls) - len(missing),
                    "missing_artifacts": missing, "complete": not missing}
    if args.check_completeness_only:
        print(json.dumps(completeness, indent=2, sort_keys=True))
        return
    if missing:
        raise RuntimeError(f"preflight incomplete: {len(missing)} missing artifacts")
    records = {}
    runner_hashes = set()
    git_heads = set()
    gpu_pairs_by_shard = defaultdict(set)
    for row in calls:
        record = load(RAW / row["shard"] / row["artifact"])
        validate_record(runner, row, record)
        records[(row["shard"], row["artifact"])] = record
        runner_hashes.add(record["runtime"]["runner_source_sha256"])
        git_heads.add(record["runtime"]["git_head"])
        gpu_pairs_by_shard[row["shard"]].add(tuple(record["runtime"]["declared_physical_gpus"]))
    if len(runner_hashes) != 1 or len(git_heads) != 1:
        raise RuntimeError("mixed runner source or git commits across raw records")
    if any(len(pairs) != 1 for pairs in gpu_pairs_by_shard.values()):
        raise RuntimeError("a shard used multiple physical GPU pairs")
    resolved_pairs = [next(iter(gpu_pairs_by_shard[shard])) for shard in runner.SHARDS]
    if len(set(resolved_pairs)) != 3 or len({gpu for pair in resolved_pairs for gpu in pair}) != 6:
        raise RuntimeError("cross-replica shards did not use three disjoint GPU pairs")
    attempt_counts = {}
    for shard in runner.SHARDS:
        events = validate_attempt_chain(ATTEMPTS / f"{shard}.jsonl")
        accepted_hashes = {row.get("record_sha256") for row in events
                           if row["event"] in {"ACCEPTED", "RECOVERED_ACCEPTED"}}
        required_hashes = {record["record_sha256"] for (record_shard, _), record in records.items()
                           if record_shard == shard}
        if not required_hashes.issubset(accepted_hashes):
            raise RuntimeError(f"raw records lack accepted attempt evidence for {shard}")
        attempt_counts[shard] = len(events)
    result = {**completeness, "artifact_authentication_pass": True,
              "runner_source_sha256": next(iter(runner_hashes)), "git_head": next(iter(git_heads)),
              "attempt_event_counts": attempt_counts,
              **evaluate_records(prereg, selection, review, records)}
    write_once(METRICS, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
