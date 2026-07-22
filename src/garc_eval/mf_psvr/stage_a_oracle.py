"""Pure integrity and support-gate helpers for the MF-PSVR Stage-A oracle."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any, Iterable

import pandas as pd

from .training_pool import QUERY_TYPE_PROJECTIONS, project_generic_label


BASE_SEED = 20260710
PHYSICAL_CALLS = 96


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def seed_for_call(physical_call_id: str) -> int:
    """Map the frozen 001..096 call order to unique deterministic RNG seeds."""

    prefix = "mf_psvr_stage_a_"
    if not physical_call_id.startswith(prefix):
        raise ValueError(f"invalid Stage-A physical_call_id: {physical_call_id}")
    try:
        ordinal = int(physical_call_id.removeprefix(prefix))
    except ValueError as exc:
        raise ValueError(f"invalid Stage-A physical_call_id: {physical_call_id}") from exc
    if ordinal < 1 or ordinal > PHYSICAL_CALLS:
        raise ValueError(f"Stage-A call ordinal outside [1,{PHYSICAL_CALLS}]: {ordinal}")
    if physical_call_id != f"{prefix}{ordinal:03d}":
        raise ValueError(f"non-canonical Stage-A physical_call_id: {physical_call_id}")
    return BASE_SEED + ordinal - 1


def execution_spec(bindings: dict[str, Any]) -> dict[str, Any]:
    """Return the exact pre-call execution policy with external hashes supplied."""

    spec = {
        "execution_id": "MF_PSVR_CYCLE1_STAGE_A_ORACLE_EXECUTION_V1",
        "status": "FROZEN_BEFORE_CANDIDATE_EXTRACTION_OR_ORACLE_CALLS",
        "maximum_physical_calls": PHYSICAL_CALLS,
        "call_order": "physical_call_id ascending, exactly mf_psvr_stage_a_001..096",
        "rng_policy": {
            "base_seed": BASE_SEED,
            "formula": "base_seed + one_based_call_ordinal - 1",
            "unique_seeds": True,
            "do_sample": False,
            "cublas_workspace_config": ":4096:8",
            "torch_deterministic_algorithms": True,
        },
        "input_identity_policy": (
            "Decode and durably hash every selected unit's exact frame indices and RGB content "
            "before loading the model or starting physical call 1."
        ),
        "model_residency": "load once and keep resident across all calls in an invocation",
        "resume_policy": (
            "Reuse only a valid durable raw envelope from the same execution/build/input identity."
        ),
        "interruption_policy": (
            "A STARTED attempt without a valid durable raw envelope becomes RECOVERED_UNCERTAIN; "
            "the run blocks and never retries or replaces that identity without a separately "
            "authorized protocol amendment."
        ),
        "parse_failure_policy": (
            "The physical call remains charged and retained with INVALID_PARSE; projected_label "
            "is empty, the row is excluded from positive/negative gate counts, and no retry or "
            "replacement is permitted."
        ),
        "oracle_abstain_policy": (
            "Retain projected abstain; exclude it from positive/negative gate counts."
        ),
        "projection_policy": {
            query_id: sorted(actors) for query_id, actors in QUERY_TYPE_PROJECTIONS.items()
        },
        "hard_case_quartiles": {
            "population": "all 2,654 eligible unit scores for the query",
            "method": "pandas Series.quantile(q, interpolation='linear')",
            "hard_positive": "projected positive with unit_score <= query q25",
            "hard_negative": "projected negative with unit_score >= query q75",
        },
        "call_accounting": {
            "physical_call_rows": 96,
            "query_projected_label_rows": 192,
            "one_call_shared_by_queries": True,
            "attempt_bound": (
                "accepted durable calls + uncertain started calls; never infer count from label rows"
            ),
        },
        "bindings": dict(bindings),
        "heldout_opened": False,
    }
    spec["execution_spec_hash"] = canonical_hash(spec)
    return spec


def append_hash_chain(events: list[dict[str, Any]], event: dict[str, Any]) -> dict[str, Any]:
    record = {
        **event,
        "previous_event_sha256": events[-1]["event_sha256"] if events else None,
    }
    record["event_sha256"] = canonical_hash(record)
    validate_attempt_events([*events, record])
    return record


def validate_attempt_events(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    previous = None
    started: dict[str, dict[str, Any]] = {}
    terminal: dict[str, dict[str, Any]] = {}
    allowed_terminal = {"ACCEPTED", "RECOVERED_ACCEPTED", "RECOVERED_UNCERTAIN"}
    for event in events:
        claimed = event.get("event_sha256")
        payload = {key: value for key, value in event.items() if key != "event_sha256"}
        if payload.get("previous_event_sha256") != previous or claimed != canonical_hash(payload):
            raise ValueError("Stage-A attempt event hash chain is invalid")
        previous = str(claimed)
        attempt_id = event.get("attempt_id")
        call_id = event.get("physical_call_id")
        if not isinstance(attempt_id, str) or not isinstance(call_id, str):
            raise ValueError("Stage-A attempt event lacks string identities")
        if event.get("event") == "STARTED":
            if attempt_id in started:
                raise ValueError(f"duplicate STARTED event: {attempt_id}")
            if any(row.get("physical_call_id") == call_id for row in started.values()):
                raise ValueError(f"retry prohibited for physical call: {call_id}")
            started[attempt_id] = event
        elif event.get("event") in allowed_terminal:
            if attempt_id not in started or attempt_id in terminal:
                raise ValueError(f"orphan or duplicate terminal event: {attempt_id}")
            if started[attempt_id]["physical_call_id"] != call_id:
                raise ValueError(f"terminal physical-call mismatch: {attempt_id}")
            terminal[attempt_id] = event
        else:
            raise ValueError(f"unknown Stage-A attempt event: {event.get('event')}")
    uncertain = sum(row["event"] == "RECOVERED_UNCERTAIN" for row in terminal.values())
    accepted = sum(row["event"] in {"ACCEPTED", "RECOVERED_ACCEPTED"} for row in terminal.values())
    unresolved = [attempt_id for attempt_id in started if attempt_id not in terminal]
    if len(started) > PHYSICAL_CALLS:
        raise ValueError("Stage-A physical call cap exceeded")
    return {
        "physical_attempts_started": len(started),
        "accepted_durable_calls": accepted,
        "uncertain_started_calls": uncertain,
        "unresolved_attempt_ids": unresolved,
    }


def projected_label(
    generic_label: str,
    involved_object: str,
    query_id: str,
    parse_status: str,
) -> str:
    if parse_status != "ok":
        return ""
    return project_generic_label(generic_label, involved_object, query_id)


def k3_bridge_safe_groups(query_labels: pd.DataFrame) -> list[dict[str, Any]]:
    """Group only directly adjacent positives under the frozen duration cap."""

    positives = query_labels[query_labels["projected_label"] == "positive"].copy()
    results: list[dict[str, Any]] = []
    for (source, session, query_id), part in positives.groupby(
        ["source_dataset", "session_id", "query_id"], sort=True
    ):
        rows = part.sort_values("unit_id").to_dict("records")
        if not rows:
            continue
        groups: list[list[dict[str, Any]]] = [[rows[0]]]
        for row in rows[1:]:
            current = groups[-1]
            directly_adjacent = int(row["unit_id"]) == int(current[-1]["unit_id"]) + 1
            proposed_duration = float(row["unit_end_seconds"]) - float(
                current[0]["unit_start_seconds"]
            )
            if directly_adjacent and proposed_duration <= 40.0 + 1e-9:
                current.append(row)
            else:
                groups.append([row])
        for index, group in enumerate(groups):
            results.append({
                "event_group_id": f"{source}|{session}|{query_id}|k3:{index:03d}",
                "source_dataset": source,
                "session_id": session,
                "query_id": query_id,
                "unit_ids": [int(row["unit_id"]) for row in group],
                "unit_count": len(group),
                "start_seconds": float(group[0]["unit_start_seconds"]),
                "end_seconds": float(group[-1]["unit_end_seconds"]),
            })
    return results


def _label_counts(frame: pd.DataFrame) -> dict[str, int]:
    positives = frame[frame["projected_label"] == "positive"]
    negatives = frame[frame["projected_label"] == "negative"]
    return {
        "positive_units": len(positives),
        "positive_source_videos": len(
            positives[["source_dataset", "session_id"]].drop_duplicates()
        ),
        "negative_units": len(negatives),
        "negative_source_videos": len(
            negatives[["source_dataset", "session_id"]].drop_duplicates()
        ),
        "abstain_units": int((frame["projected_label"] == "abstain").sum()),
        "invalid_parse_units": int((frame["projected_label"] == "").sum()),
    }


def evaluate_support_gates(
    label_rows: pd.DataFrame,
    score_rows: pd.DataFrame,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate the frozen Stage-A support and split-usability decisions."""

    required = {
        "physical_call_id", "source_dataset", "session_id", "model_split_role",
        "unit_id", "unit_start_seconds", "unit_end_seconds", "query_id",
        "verification_key", "projected_label", "parse_status",
    }
    if not required.issubset(label_rows.columns):
        raise ValueError(f"label manifest missing fields: {sorted(required - set(label_rows.columns))}")
    if len(label_rows) != 192 or label_rows["verification_key"].duplicated().any():
        raise ValueError("Stage-A label manifest must have 192 unique verification keys")
    expected_calls = {f"mf_psvr_stage_a_{ordinal:03d}" for ordinal in range(1, 97)}
    if set(label_rows["physical_call_id"]) != expected_calls or set(label_rows["query_id"]) != {"Q1", "Q2"}:
        raise ValueError("Stage-A labels do not map 96 calls to exactly Q1 and Q2")
    query_sets = label_rows.groupby("physical_call_id")["query_id"].agg(set)
    if len(query_sets) != 96 or any(value != {"Q1", "Q2"} for value in query_sets):
        raise ValueError("Each Stage-A physical call must have exactly one Q1 and one Q2 row")
    identity_fields = [
        "source_dataset", "session_id", "model_split_role", "unit_id",
        "unit_start_seconds", "unit_end_seconds",
    ]
    if (label_rows.groupby("physical_call_id")[identity_fields].nunique(dropna=False) != 1).any().any():
        raise ValueError("Q1/Q2 rows disagree on their shared physical-call identity")
    expected_verification = label_rows.apply(
        lambda row: (
            f"{row['source_dataset']}|{row['session_id']}|"
            f"{row['query_id']}|{int(row['unit_id'])}"
        ),
        axis=1,
    )
    if not expected_verification.equals(label_rows["verification_key"]):
        raise ValueError("Stage-A verification-key serialization changed")
    allowed_labels = {"positive", "negative", "abstain", ""}
    if not set(label_rows["projected_label"]).issubset(allowed_labels):
        raise ValueError("Stage-A projected-label domain changed")
    invalid_parse = label_rows["parse_status"] != "ok"
    if (label_rows.loc[invalid_parse, "projected_label"] != "").any():
        raise ValueError("Invalid parses must retain an empty projected label")

    score_required = {"source_dataset", "session_id", "unit_id", "query_id", "unit_score"}
    if not score_required.issubset(score_rows.columns):
        raise ValueError("unit-score table is missing gate fields")
    if score_rows.duplicated(["source_dataset", "session_id", "unit_id", "query_id"]).any():
        raise ValueError("unit-score table contains duplicate query units")
    if len(score_rows) != 5308 or Counter(score_rows["query_id"]) != Counter({"Q1": 2654, "Q2": 2654}):
        raise ValueError("hard-case quartiles require all 2,654 pool units for each query")
    numeric_scores = pd.to_numeric(score_rows["unit_score"], errors="raise")
    if not numeric_scores.map(math.isfinite).all():
        raise ValueError("unit-score table contains a non-finite score")
    score_rows = score_rows.copy()
    score_rows["unit_score"] = numeric_scores
    merged = label_rows.merge(
        score_rows[sorted(score_required)],
        on=["source_dataset", "session_id", "unit_id", "query_id"],
        how="left",
        validate="one_to_one",
    )
    if merged["unit_score"].isna().any():
        raise ValueError("at least one Stage-A label lacks a frozen unit score")

    pilot = protocol["stage_a_support_pilot"]
    existence_thresholds = pilot["support_existence_gate"]
    split_thresholds = pilot["split_specific_usability_gates_per_query"]
    call_splits = label_rows.drop_duplicates("physical_call_id")["model_split_role"]
    expected_split_calls = Counter({
        split: int(count) for split, count in pilot["split_quotas"].items()
    })
    if Counter(call_splits) != expected_split_calls:
        raise ValueError("Stage-A model-split call quotas changed")
    per_query: dict[str, Any] = {}
    all_existence_pass = True
    all_eval_pass = True
    all_train_initial_pass = True
    for query_id in ("Q1", "Q2"):
        query = merged[merged["query_id"] == query_id].copy()
        counts = _label_counts(query)
        nontrain_positive = int(
            (
                (query["projected_label"] == "positive")
                & query["model_split_role"].isin(["model_calibration", "pool_audit"])
            ).sum()
        )
        threshold = existence_thresholds[query_id]
        existence_pass = (
            counts["positive_units"] >= int(threshold["minimum_positive_units"])
            and counts["positive_source_videos"]
            >= int(threshold["minimum_positive_source_videos"])
            and nontrain_positive >= 1
        )
        split_results = {}
        for split, split_threshold in split_thresholds.items():
            split_counts = _label_counts(query[query["model_split_role"] == split])
            passed = all(
                split_counts[key] >= int(split_threshold[f"minimum_{key}"])
                for key in (
                    "positive_units", "positive_source_videos",
                    "negative_units", "negative_source_videos",
                )
            )
            split_results[split] = {**split_counts, "pass": passed}
        q25 = float(
            score_rows[score_rows["query_id"] == query_id]["unit_score"].astype(float).quantile(
                0.25, interpolation="linear"
            )
        )
        q75 = float(
            score_rows[score_rows["query_id"] == query_id]["unit_score"].astype(float).quantile(
                0.75, interpolation="linear"
            )
        )
        hard_positive = int(
            ((query["projected_label"] == "positive") & (query["unit_score"] <= q25)).sum()
        )
        hard_negative = int(
            ((query["projected_label"] == "negative") & (query["unit_score"] >= q75)).sum()
        )
        query_groups = [row for row in k3_bridge_safe_groups(query) if row["query_id"] == query_id]
        per_query[query_id] = {
            **counts,
            "positive_in_calibration_or_audit": nontrain_positive,
            "support_existence_pass": existence_pass,
            "split_usability": split_results,
            "score_q25": q25,
            "score_q75": q75,
            "low_score_hard_positives": hard_positive,
            "high_score_hard_negatives": hard_negative,
            "k3_event_groups": len(query_groups),
            "k3_multi_unit_event_groups": sum(row["unit_count"] >= 2 for row in query_groups),
        }
        all_existence_pass &= existence_pass
        all_eval_pass &= (
            split_results["model_calibration"]["pass"]
            and split_results["pool_audit"]["pass"]
        )
        all_train_initial_pass &= split_results["model_train"]["pass"]

    if not all_existence_pass or not all_eval_pass:
        decision = "STOP_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE"
    else:
        decision = "STAGE_A_PASS_STAGE_B_REQUIRES_SEPARATE_AUTHORITY"
    return {
        "decision": decision,
        "support_existence_all_queries_pass": all_existence_pass,
        "frozen_evaluation_splits_all_queries_pass": all_eval_pass,
        "model_train_initial_all_queries_pass": all_train_initial_pass,
        "per_query": per_query,
        "physical_call_ids": label_rows["physical_call_id"].nunique(),
        "query_verification_keys": len(label_rows),
        "label_domain_counts": dict(Counter(label_rows["projected_label"])),
        "heldout_opened": False,
    }
