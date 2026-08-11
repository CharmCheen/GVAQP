#!/usr/bin/env python3
"""Frozen cached-replay P0: selector x K0/K3 event materialization.

This is deliberately experiment-only code.  It consumes a *released* V10
model-relative unit reference and the separately frozen prospective V3
candidate/proxy substrate.  It does not invoke the oracle, alter production
K3, tune a threshold, or consult a result while constructing its protocol.

Usage::

    .venv-v7-oracle/bin/python scripts/run_p0_v3_materializer_validation.py self-test
    .venv-v7-oracle/bin/python scripts/run_p0_v3_materializer_validation.py freeze
    .venv-v7-oracle/bin/python scripts/run_p0_v3_materializer_validation.py run

``freeze`` is intentionally a separate operation: the protocol includes the
runner hash, source artifacts, selectors, budgets and metric before replay
materializes any K0/K3 result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import platform
import random
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from garc_eval.accelerated_event_query.k3_unit_event_adapter import (  # noqa: E402
    K3UnitEventAdapter,
    K3UnitEventConfig,
)
from garc_eval.accelerated_event_query.matching import (  # noqa: E402
    MatchConfig,
    match_events,
    summarize_matches,
)
from garc_eval.accelerated_event_query.model_relative_labels import (  # noqa: E402
    ModelRelativeUnitLabel,
)
from garc_eval.accelerated_event_query.types import EventRecord  # noqa: E402


OUT = ROOT / "outputs/p0_materializer_validation_v3"
V10 = ROOT / "outputs/v10_multiseal_reference_v1"
SCAN = ROOT / "outputs/v3_scan_proxy_preregistration_v1"
QUERY_ID = "Q_DRIVER_RESPONSE_V1"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
BUDGETS = (5, 10, 20, 50, 80, 100)
SELECTORS = (
    {
        "name": "UniformTemporal",
        "kind": "uniform_temporal",
        "description": "Fixed evenly spaced temporal ordering over the frozen candidate universe.",
        "uses_proxy": False,
    },
    {
        "name": "StaticProxyRank",
        "kind": "static_proxy_rank",
        "description": "Descending frozen cheap proxy_score; deterministic candidate-order/id ties.",
        "uses_proxy": True,
    },
    {
        "name": "TemporalCoverage",
        "kind": "temporal_coverage",
        "description": "Static recursive temporal bisection order; no oracle feedback or proxy labels.",
        "uses_proxy": False,
    },
)
PRIMARY_MATCH = {
    "name": "v3_one_to_one_max_cardinality_then_tiou",
    "minimum_tiou": 0.0,
    "boundary_tolerance_sec": 0.0,
    "eligibility": "strict_positive_temporal_overlap",
    "duplicate_rule": "unmatched_overlapping_prediction_is_false_positive",
    "source": "K3_UNIT_EVENT_CONFIG_V3.json and accelerated_event_query.matching.MatchConfig",
}
SENSITIVITY_MATCH = {
    "name": "one_to_one_tiou_at_least_0_30",
    "minimum_tiou": 0.30,
    "boundary_tolerance_sec": 0.0,
}
K0_DEFINITION = (
    "For one video/query trace, emit exactly one VERIFIED_EVENT spanning min(start) to max(end) "
    "of every queried relevant unit; emit no event with no queried relevant units.  It deliberately "
    "does not inspect queried negatives, unknowns, parse failures, gaps, or duration caps.  This is the "
    "V3-compatible expression of historical Stage-0 C0 common_naive_merge / merge_all_anchors."
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_once(path: Path, value: Any) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def write_text_once(path: Path, value: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != value:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_csv_once(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import io

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(fields), extrasaction="raise")
    writer.writeheader()
    writer.writerows(rows)
    payload = buf.getvalue()
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RuntimeError(f"immutable artifact mismatch: {path}")
        return
    path.write_text(payload, encoding="utf-8")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def frozen_k3_config() -> tuple[K3UnitEventConfig, Path, dict[str, Any]]:
    path = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative/k3_eventization/K3_UNIT_EVENT_CONFIG_V3.json"
    raw = read_json(path)
    config = K3UnitEventConfig(**raw["parameters"])
    if raw["k3_config_sha256"] != config.sha256:
        raise RuntimeError("frozen K3 configuration hash does not reconstruct")
    return config, path, raw


def reference_preflight() -> dict[str, Any]:
    manifest_path = V10 / "REFERENCE_MANIFEST.json"
    manifest = read_json(manifest_path)
    if not manifest.get("complete") or manifest.get("expected_units") != 1475:
        raise RuntimeError("V10 reference is not a complete 1475-unit release")
    if manifest.get("cross_seal_compatibility") not in {"PASS", "QUALIFIED_PASS"}:
        raise RuntimeError("cross-seal compatibility does not permit P0 replay")
    if manifest.get("status") != "FORMAL_MULTI_SEAL_MODEL_RELATIVE_REFERENCE_RELEASE":
        raise RuntimeError("unexpected V10 reference-release status")
    circularity = (V10 / "REFERENCE_CIRCULARITY_AUDIT.md").read_text(encoding="utf-8")
    if "QUALIFIED_BUT_VALID" not in circularity and "NO_FATAL_CIRCULARITY" not in circularity:
        raise RuntimeError("reference circularity decision is not usable for a qualified P0 study")
    cfg, cfg_path, raw_cfg = frozen_k3_config()
    if manifest["k3_config_hash"] != cfg.sha256:
        raise RuntimeError("released reference K3 hash differs from frozen current V3 K3")
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "circularity_path": V10 / "REFERENCE_CIRCULARITY_AUDIT.md",
        "unit_path": V10 / "FINAL_UNIT_REFERENCE.parquet",
        "relation_path": V10 / "K3_MODEL_RELATIVE_EVENT_RELATION.parquet",
        "k3_config": cfg,
        "k3_config_path": cfg_path,
        "k3_config_raw": raw_cfg,
    }


def input_artifacts() -> dict[str, Any]:
    ref = reference_preflight()
    scan_protocol_path = SCAN / "FROZEN_V3_SCAN_PROXY_PROTOCOL.json"
    scan_protocol = read_json(scan_protocol_path)
    if not scan_protocol.get("PROTOCOL_FROZEN") or not scan_protocol.get("THIS_IS_NOT_A_RECOVERED_HISTORICAL_PREREGISTRATION"):
        raise RuntimeError("the prospective scan/proxy contract is not frozen as expected")
    if tuple(scan_protocol["video_ids"]) != VIDEOS:
        raise RuntimeError("scan protocol video set differs from P0 contract")
    entries: dict[str, Any] = {
        "v10_reference_manifest": {"path": relative(ref["manifest_path"]), "sha256": sha256_file(ref["manifest_path"])},
        "final_unit_reference": {"path": relative(ref["unit_path"]), "sha256": sha256_file(ref["unit_path"])},
        "reference_event_relation": {"path": relative(ref["relation_path"]), "sha256": sha256_file(ref["relation_path"])},
        "reference_circularity_audit": {"path": relative(ref["circularity_path"]), "sha256": sha256_file(ref["circularity_path"])},
        "frozen_k3_config": {"path": relative(ref["k3_config_path"]), "sha256": sha256_file(ref["k3_config_path"])},
        "scan_proxy_protocol": {"path": relative(scan_protocol_path), "sha256": sha256_file(scan_protocol_path)},
    }
    for video in VIDEOS:
        for name in ("candidate_table", "proxy_table"):
            path = SCAN / "frozen_tables" / video / f"{name}.parquet"
            if not path.exists():
                raise RuntimeError(f"missing frozen {name} for {video}")
            entries[f"{video}_{name}"] = {"path": relative(path), "sha256": sha256_file(path)}
    return {"reference": ref, "scan_protocol": scan_protocol, "entries": entries}


def p0_protocol() -> dict[str, Any]:
    assets = input_artifacts()
    protocol = {
        "protocol_id": "P0_V3_SELECTOR_X_MATERIALIZER_CONTROLLED_REPLAY_V3",
        "status": "FROZEN_BEFORE_P0_RESULT_REPLAY",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "downstream_result_inputs_used_to_design_protocol": False,
        "semantic_oracle_invocations": 0,
        "evaluation_kind": "MODEL_RELATIVE_EVALUATION",
        "reference_circularity": "QUALIFIED_BUT_VALID; disclose that reference events use full-grid K3 grouping",
        "videos": list(VIDEOS),
        "query_id": QUERY_ID,
        "candidate_universe": "one frozen prospective V3 candidate per V3 unit; same candidate table for all selectors/materializers",
        "selectors": list(SELECTORS),
        "seeds": [0],
        "budgets": list(BUDGETS),
        "budget_semantics": "QUERY_BUDGET: cached semantic/oracle invocation count; not wall-clock and not a hard deadline",
        "materializers": {
            "K0": {"name": "NaiveAllPositiveSpan", "definition": K0_DEFINITION, "experiment_only": True,
                   "historical_lineage": "scripts/stage0_6_materializer_ablation.py:C0_common_naive_merge"},
            "K3": {"name": "CurrentV3K3UnitEventAdapter", "config_sha256": assets["reference"]["k3_config"].sha256,
                   "source": "src/garc_eval/accelerated_event_query/k3_unit_event_adapter.py"},
        },
        "controlled_pair_invariant": [
            "same candidate universe", "same selected unit ids", "same query order", "same oracle outcomes",
            "same oracle call count", "same evaluator", "only materialization policy differs",
        ],
        "primary_matcher": PRIMARY_MATCH,
        "sensitivity_matcher": SENSITIVITY_MATCH,
        "statistics": {
            "bootstrap_seed": 20260811,
            "bootstrap_resamples": 10000,
            "analysis_unit": "selector x video x budget deterministic paired cell",
            "material_effect_threshold_f1": 0.02,
            "accept_direction_threshold": 0.75,
        },
        "input_artifacts": assets["entries"],
        "runner": {"path": relative(Path(__file__)), "sha256": sha256_file(Path(__file__))},
        "source_commit": git("rev-parse", "HEAD"),
        "dirty_worktree": git("status", "--short").splitlines(),
    }
    # Timestamp is provenance but must not prevent deterministic verification of the stored object.
    protocol["protocol_hash"] = canonical_hash({k: v for k, v in protocol.items() if k not in {"created_at_utc", "protocol_hash"}})
    return protocol


def freeze() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"refusing to overwrite/replace existing P0 v2 output directory: {OUT}")
    p = p0_protocol()
    OUT.mkdir(parents=True)
    write_json_once(OUT / "EXPERIMENT_PROTOCOL.json", p)
    write_text_once(OUT / "PROTOCOL_HASH.txt", p["protocol_hash"] + "\n")
    manifest = {
        "protocol_hash": p["protocol_hash"],
        "repo": str(ROOT),
        "branch": git("branch", "--show-current"),
        "commit": git("rev-parse", "HEAD"),
        "python": sys.version,
        "platform": platform.platform(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "semantic_oracle_invocations": 0,
        "note": "P0 v2 protocol frozen before the runner reads model-relative semantic outcome labels for replay results.",
    }
    write_json_once(OUT / "RUN_MANIFEST.json", manifest)
    write_text_once(OUT / "PROTOCOL_FREEZE.md", "# P0 V2 Protocol Freeze\n\n"
                    f"Protocol hash: `{p['protocol_hash']}`\n\n"
                    "This protocol was created after the V10 reference release but before this runner generated "
                    "any K0/K3 event metric, selector ranking, materializer gain, or downstream P0 result. "
                    "It fixes three deterministic selector families, the candidate universe, budgets, K0 and current V3 K3, "
                    "and the primary/sensitivity matchers.\n")
    print(json.dumps({"status": "FROZEN", "protocol_hash": p["protocol_hash"], "output": str(OUT)}, sort_keys=True))


def load_protocol() -> dict[str, Any]:
    path = OUT / "EXPERIMENT_PROTOCOL.json"
    if not path.exists():
        raise RuntimeError("run `freeze` before `run`")
    p = read_json(path)
    actual = canonical_hash({k: v for k, v in p.items() if k not in {"created_at_utc", "protocol_hash"}})
    if p.get("protocol_hash") != actual:
        raise RuntimeError("stored P0 protocol hash does not verify")
    if (OUT / "PROTOCOL_HASH.txt").read_text(encoding="utf-8").strip() != actual:
        raise RuntimeError("PROTOCOL_HASH.txt differs from protocol")
    if sha256_file(Path(__file__)) != p["runner"]["sha256"]:
        raise RuntimeError("runner source changed after protocol freeze; create a new protocol revision rather than replay")
    current = input_artifacts()["entries"]
    if current != p["input_artifacts"]:
        raise RuntimeError("a frozen input artifact has changed after P0 protocol freeze")
    return p


def load_data() -> tuple[dict[str, ModelRelativeUnitLabel], dict[str, list[dict[str, Any]]], dict[str, list[EventRecord]]]:
    unit = pd.read_parquet(V10 / "FINAL_UNIT_REFERENCE.parquet")
    relation = pd.read_parquet(V10 / "K3_MODEL_RELATIVE_EVENT_RELATION.parquet")
    labels: dict[str, ModelRelativeUnitLabel] = {}
    for row in unit.to_dict(orient="records"):
        labels[row["unit_id"]] = ModelRelativeUnitLabel(
            unit_id=row["unit_id"], query_id=QUERY_ID, video_id=row["video_id"],
            start_time=float(row["start_time"]), end_time=float(row["end_time"]),
            outcome=row["authoritative_label"], confidence=(None if pd.isna(row["diagnostic_confidence"]) else row["diagnostic_confidence"]),
            evidence=(None if pd.isna(row["diagnostic_evidence"]) else row["diagnostic_evidence"]),
        )
    candidates: dict[str, list[dict[str, Any]]] = {}
    for video in VIDEOS:
        cand = pd.read_parquet(SCAN / "frozen_tables" / video / "candidate_table.parquet")
        proxy = pd.read_parquet(SCAN / "frozen_tables" / video / "proxy_table.parquet")
        merged = cand.merge(proxy, on=["video_id", "candidate_id"], how="inner", validate="one_to_one")
        if len(merged) != len(cand) or len(merged) != len(proxy):
            raise RuntimeError(f"candidate/proxy cardinality mismatch for {video}")
        rows = []
        for row in merged.sort_values("candidate_order").to_dict(orient="records"):
            source = list(row["source_unit_ids"])
            if len(source) != 1 or source[0] not in labels:
                raise RuntimeError(f"candidate cannot bind exactly one frozen unit: {row['candidate_id']}")
            unit_label = labels[source[0]]
            if row["video_id"] != unit_label.video_id or float(row["start_sec"]) != unit_label.start_time or float(row["end_sec"]) != unit_label.end_time:
                raise RuntimeError(f"candidate/unit temporal identity mismatch: {row['candidate_id']}")
            rows.append({**row, "unit_id": source[0]})
        candidates[video] = rows
    refs: dict[str, list[EventRecord]] = defaultdict(list)
    for row in relation.to_dict(orient="records"):
        refs[row["video_id"]].append(EventRecord(
            event_id=row["event_id"], query_id=row["query_id"], video_id=row["video_id"],
            start_time=float(row["start_time"]), end_time=float(row["end_time"]), event_score=1.0,
            evidence_status=row["evidence_status"], source_candidate_ids=tuple(row["source_unit_ids"]),
            verification_history=(), k3_group=row["k3_group"], commit_time=None,
        ))
    if set(candidates) != set(VIDEOS) or set(refs) != set(VIDEOS):
        raise RuntimeError("P0 video coverage is incomplete")
    return labels, candidates, refs


def temporal_coverage_order(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Outcome-blind recursive-bisection ordering over canonical temporal ordinals."""
    ordered = list(sorted(rows, key=lambda x: (int(x["candidate_order"]), x["candidate_id"])))
    out: list[dict[str, Any]] = []
    def visit(lo: int, hi: int) -> None:
        if lo >= hi:
            return
        mid = (lo + hi) // 2
        out.append(ordered[mid])
        visit(lo, mid)
        visit(mid + 1, hi)
    visit(0, len(ordered))
    return out


def ranked_candidates(selector: str, rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    if selector == "UniformTemporal":
        # The prefix of this rank is only an ordering.  Exact evenly spaced subsets
        # are chosen for each B below, so it cannot silently favor early units.
        return list(sorted(rows, key=lambda x: (int(x["candidate_order"]), x["candidate_id"])))
    if selector == "StaticProxyRank":
        return list(sorted(rows, key=lambda x: (-float(x["proxy_score"]), int(x["candidate_order"]), x["candidate_id"])))
    if selector == "TemporalCoverage":
        return temporal_coverage_order(rows)
    raise ValueError(f"unknown selector: {selector}")


def select_trace(selector: str, rows: Sequence[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    if budget > len(rows):
        raise ValueError("budget exceeds candidate universe")
    if selector == "UniformTemporal":
        base = list(sorted(rows, key=lambda x: (int(x["candidate_order"]), x["candidate_id"])))
        if budget == 1:
            return [base[0]]
        indexes = [round(i * (len(base) - 1) / (budget - 1)) for i in range(budget)]
        if len(set(indexes)) != budget:
            raise RuntimeError("uniform temporal selection produced duplicate positions")
        # Query execution respects increasing time for this static selector.
        return [base[i] for i in indexes]
    return ranked_candidates(selector, rows)[:budget]


def trace_payload(selector: str, selected: Sequence[dict[str, Any]], labels: dict[str, ModelRelativeUnitLabel]) -> dict[str, Any]:
    units = [labels[row["unit_id"]] for row in selected]
    return {
        "selector": selector,
        "queried_unit_ids": [x.unit_id for x in units],
        "query_order": [x.unit_id for x in units],
        "oracle_outcomes": [x.outcome for x in units],
        "oracle_call_count": len(units),
    }


def k0_materialize(video: str, units: Sequence[ModelRelativeUnitLabel]) -> list[EventRecord]:
    positives = sorted((u for u in units if u.outcome == "relevant"), key=lambda u: (u.start_time, u.end_time, u.unit_id))
    if not positives:
        return []
    token = canonical_hash({"kind": "K0", "video": video, "units": [u.unit_id for u in positives]})[:16]
    return [EventRecord(
        event_id=f"p0_k0_{token}", query_id=QUERY_ID, video_id=video,
        start_time=min(u.start_time for u in positives), end_time=max(u.end_time for u in positives),
        event_score=1.0, evidence_status="VERIFIED_EVENT", source_candidate_ids=tuple(u.unit_id for u in positives),
        verification_history=(), k3_group="P0_K0_NAIVE_ALL_POSITIVE_SPAN", commit_time=None,
    )]


def k3_materialize(units: Sequence[ModelRelativeUnitLabel], config: K3UnitEventConfig) -> list[EventRecord]:
    return list(K3UnitEventAdapter(QUERY_ID, config).materialize(units).events)


def metric_row(predicted: Sequence[EventRecord], reference: Sequence[EventRecord], config: MatchConfig) -> dict[str, Any]:
    matches = match_events(predicted, reference, config)
    metrics = summarize_matches(predicted, reference, matches)
    tp = int(metrics["matched_events"])
    return {
        "TP": tp,
        "FP": len(predicted) - tp,
        "FN": len(reference) - tp,
        "precision": float(metrics["32b_operational_oracle_relative_event_precision"]),
        "recall": float(metrics["32b_operational_oracle_relative_event_recall"]),
        "F1": float(metrics["event_f1"]),
        "event_count": len(predicted),
        "reference_event_count": len(reference),
        "mean_event_boundary_tiou": float(metrics["mean_event_boundary_tiou"]),
    }


def interval_overlap(left: EventRecord, right: EventRecord) -> bool:
    return max(left.start_time, right.start_time) < min(left.end_time, right.end_time)


def diagnostics(predicted: Sequence[EventRecord], reference: Sequence[EventRecord], queried: Sequence[ModelRelativeUnitLabel]) -> dict[str, int]:
    relevant = [u for u in queried if u.outcome == "relevant"]
    negative = [u for u in queried if u.outcome == "not_relevant"]
    unknown = [u for u in queried if u.outcome == "unknown"]
    parse = [u for u in queried if u.outcome == "parse_failure"]
    cross_negative = 0
    for event in predicted:
        anchors = [u for u in relevant if u.unit_id in set(event.source_candidate_ids)]
        if len(anchors) < 2:
            continue
        for neg in negative:
            if neg.start_time >= event.start_time and neg.end_time <= event.end_time:
                cross_negative += 1
    fragmentation = sum(1 for ref in reference if sum(interval_overlap(pred, ref) for pred in predicted) > 1)
    unknown_bridges = sum(1 for event in predicted for row in unknown if row.start_time >= event.start_time and row.end_time <= event.end_time)
    parse_barriers = sum(1 for event in predicted for row in parse if row.start_time >= event.start_time and row.end_time <= event.end_time)
    return {
        "cross_negative_overmerge": cross_negative,
        "long_span_overmerge": sum(1 for event in predicted if event.end_time - event.start_time > 60.0),
        "positive_fragmentation": fragmentation,
        "unknown_gap_bridges": unknown_bridges,
        "parse_failure_barrier_crossings": parse_barriers,
        "selected_relevant": len(relevant),
        "selected_negative": len(negative),
        "selected_unknown": len(unknown),
        "selected_parse_failure": len(parse),
    }


def bootstrap_ci(values: Sequence[float], *, statistic: str, seed: int = 20260811, n: int = 10000) -> tuple[float, float]:
    if not values:
        return (float("nan"), float("nan"))
    data = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    samples = np.empty(n, dtype=float)
    for i in range(n):
        draw = rng.choice(data, size=len(data), replace=True)
        samples[i] = np.mean(draw) if statistic == "mean" else np.median(draw)
    return (float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975)))


def compact(value: float) -> str:
    return "NA" if math.isnan(value) else f"{value:.4f}"


def paired_effects(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in metrics:
        key = (row["video_id"], row["query_id"], row["selector"], row["budget"], row["seed"])
        by_key[key][row["materializer"]] = row
    rows = []
    for key, pair in sorted(by_key.items()):
        if set(pair) != {"K0", "K3"}:
            raise RuntimeError(f"incomplete materializer pair: {key}")
        k0, k3 = pair["K0"], pair["K3"]
        valid = all(k0[field] == k3[field] for field in ("trace_hash", "queried_units_hash", "query_order_hash", "oracle_outcomes_hash", "oracle_calls"))
        rows.append({
            "video_id": key[0], "query_id": key[1], "selector": key[2], "budget": key[3], "seed": key[4],
            "F1_K0": k0["F1"], "F1_K3": k3["F1"], "Delta_F1": k3["F1"] - k0["F1"],
            "Precision_K0": k0["precision"], "Precision_K3": k3["precision"],
            "Recall_K0": k0["recall"], "Recall_K3": k3["recall"], "Delta_Recall": k3["recall"] - k0["recall"],
            "FP_K0": k0["FP"], "FP_K3": k3["FP"],
            "overmerge_K0": k0["cross_negative_overmerge"], "overmerge_K3": k3["cross_negative_overmerge"],
            "fragmentation_K0": k0["positive_fragmentation"], "fragmentation_K3": k3["positive_fragmentation"],
            "valid_controlled_pair": valid,
            "invalid_reason": "" if valid else "TRACE_IDENTITY_MISMATCH",
        })
    return rows


def selector_effect_rows(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    k3 = [row for row in metrics if row["materializer"] == "K3"]
    by = defaultdict(list)
    for row in k3:
        by[(row["video_id"], row["query_id"], row["budget"], row["seed"])].append(row)
    out = []
    for key, rows in sorted(by.items()):
        if len(rows) != len(SELECTORS):
            raise RuntimeError(f"selector coverage incomplete for {key}")
        rows = sorted(rows, key=lambda x: x["selector"])
        for left, right in itertools.combinations(rows, 2):
            out.append({"video_id": key[0], "query_id": key[1], "budget": key[2], "seed": key[3],
                        "materializer": "K3", "selector_a": left["selector"], "selector_b": right["selector"],
                        "F1_a": left["F1"], "F1_b": right["F1"], "Delta_F1_a_minus_b": left["F1"] - right["F1"],
                        "abs_selector_difference": abs(left["F1"] - right["F1"])})
        out.append({"video_id": key[0], "query_id": key[1], "budget": key[2], "seed": key[3],
                    "materializer": "K3", "selector_a": "__spread_min__", "selector_b": "__spread_max__",
                    "F1_a": min(x["F1"] for x in rows), "F1_b": max(x["F1"] for x in rows),
                    "Delta_F1_a_minus_b": min(x["F1"] for x in rows) - max(x["F1"] for x in rows),
                    "abs_selector_difference": max(x["F1"] for x in rows) - min(x["F1"] for x in rows)})
    return out


def make_plots(metrics: list[dict[str, Any]], effects: list[dict[str, Any]], selector_effects: list[dict[str, Any]]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_dir = OUT / "plots"; plot_dir.mkdir(exist_ok=True)
    # Per-selector quality curves, retaining each independent video rather than pooled-only display.
    fig, axes = plt.subplots(1, 3, figsize=(15, 4), sharey=True)
    for ax, selector in zip(axes, [x["name"] for x in SELECTORS]):
        for video in VIDEOS:
            for materializer, style in (("K0", "--"), ("K3", "-")):
                sub = [r for r in metrics if r["selector"] == selector and r["video_id"] == video and r["materializer"] == materializer]
                ax.plot([r["budget"] for r in sub], [r["F1"] for r in sub], linestyle=style, marker="o", label=f"{video} {materializer}")
        ax.set_title(selector); ax.set_xlabel("oracle invocation budget"); ax.set_ylim(0, 1.02); ax.grid(alpha=.25)
    axes[0].set_ylabel("event F1 (model-relative; overlap-any primary)")
    axes[-1].legend(fontsize=7, ncol=2, loc="lower right")
    fig.suptitle("P0 V2: frozen same-trace K0/K3 quality curves")
    fig.tight_layout(); fig.savefig(plot_dir / "event_f1_by_selector_video.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    positions, labels = [], []
    for selector_i, selector in enumerate([x["name"] for x in SELECTORS]):
        for video_i, video in enumerate(VIDEOS):
            vals = [r["Delta_F1"] for r in effects if r["selector"] == selector and r["video_id"] == video]
            pos = selector_i * 4 + video_i
            ax.scatter([pos] * len(vals), vals, alpha=.8)
            positions.append(pos); labels.append(f"{selector}\n{video}")
    ax.axhline(0, color="black", linewidth=.8); ax.set_xticks(positions, labels, rotation=35, ha="right")
    ax.set_ylabel("Delta F1 (K3 - K0)"); ax.set_title("Materializer effect by independent video and selector"); ax.grid(axis="y", alpha=.25)
    fig.tight_layout(); fig.savefig(plot_dir / "delta_f1_by_video_selector.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    mat = [abs(r["Delta_F1"]) for r in effects]
    sel = [r["abs_selector_difference"] for r in selector_effects if r["selector_a"] != "__spread_min__"]
    ax.boxplot([mat, sel], labels=["|K3 - K0|", "|selector A - B| at K3"], showmeans=True)
    ax.set_ylim(0, 1.02); ax.set_ylabel("absolute Event F1 difference"); ax.set_title("Materializer effect versus selector pair effect")
    ax.grid(axis="y", alpha=.25); fig.tight_layout(); fig.savefig(plot_dir / "materializer_vs_selector_effect.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    values = []
    labels = []
    for materializer in ("K0", "K3"):
        vals = [r["cross_negative_overmerge"] for r in metrics if r["materializer"] == materializer]
        values.append(vals); labels.append(materializer)
    ax.boxplot(values, labels=labels, showmeans=True); ax.set_ylabel("selected negative units inside multi-anchor prediction")
    ax.set_title("Mechanism diagnostic: selected-negative barrier crossings"); ax.grid(axis="y", alpha=.25)
    fig.tight_layout(); fig.savefig(plot_dir / "cross_negative_overmerge.png", dpi=180); plt.close(fig)


def decision_summary(effects: list[dict[str, Any]], metrics: list[dict[str, Any]], selector_rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [r for r in effects if r["valid_controlled_pair"]]
    delta = [r["Delta_F1"] for r in valid]
    # Strictly greater intentionally uses a tiny tolerance to avoid numerical noise.
    better = sum(x > 1e-12 for x in delta)
    equal = sum(abs(x) <= 1e-12 for x in delta)
    worse = sum(x < -1e-12 for x in delta)
    by_selector = {}
    by_video = {}
    for selector in [x["name"] for x in SELECTORS]:
        values = [r["Delta_F1"] for r in valid if r["selector"] == selector]
        by_selector[selector] = {"n": len(values), "median_delta_f1": float(np.median(values)), "mean_delta_f1": float(np.mean(values)), "better_fraction": sum(x > 1e-12 for x in values) / len(values)}
    for video in VIDEOS:
        values = [r["Delta_F1"] for r in valid if r["video_id"] == video]
        by_video[video] = {"n": len(values), "median_delta_f1": float(np.median(values)), "mean_delta_f1": float(np.mean(values)), "better_fraction": sum(x > 1e-12 for x in values) / len(values)}
    mean_ci = bootstrap_ci(delta, statistic="mean")
    median_ci = bootstrap_ci(delta, statistic="median")
    selector_pair = [r["abs_selector_difference"] for r in selector_rows if r["selector_a"] != "__spread_min__"]
    selector_spread = [r["abs_selector_difference"] for r in selector_rows if r["selector_a"] == "__spread_min__"]
    median_abs_mat = float(np.median(np.abs(delta)))
    median_abs_sel = float(np.median(selector_pair))
    ratio = median_abs_mat / median_abs_sel if median_abs_sel > 0 else float("inf")
    overmerge = {
        materializer: float(np.mean([r["cross_negative_overmerge"] for r in metrics if r["materializer"] == materializer]))
        for materializer in ("K0", "K3")
    }
    # This was predeclared in the protocol; it does not choose a post-hoc threshold.
    consistent_selectors = sum(v["median_delta_f1"] > 0 and v["better_fraction"] >= 0.5 for v in by_selector.values())
    direction = better / len(delta)
    material = float(np.median(delta)) >= 0.02
    multi_video = all(v["median_delta_f1"] > 0 for v in by_video.values())
    if direction >= .75 and material and consistent_selectors == 3 and multi_video and overmerge["K3"] < overmerge["K0"]:
        decision = "ACCEPT"
        rationale = "Predeclared direction, magnitude, selector robustness, three-video and anti-overmerge diagnostic criteria all pass; claim remains model-relative and circularity-qualified."
    elif float(np.median(delta)) <= .005 and (direction < .5 or sum(v["median_delta_f1"] <= 0 for v in by_video.values()) >= 2):
        decision = "REJECT"
        rationale = "The controlled multi-video replay does not show a material, consistent K3 advantage under the frozen model-relative contract."
    else:
        decision = "REVISE"
        rationale = "There is a non-uniform or insufficiently robust effect; report the observed regime boundary rather than promote a universal materialization mainline."
    return {
        "valid_controlled_pairs": len(valid), "mean_delta_f1": float(np.mean(delta)), "median_delta_f1": float(np.median(delta)),
        "mean_delta_f1_bootstrap_95_ci": list(mean_ci), "median_delta_f1_bootstrap_95_ci": list(median_ci),
        "k3_better": better, "equal": equal, "worse": worse, "k3_better_fraction": better / len(delta),
        "per_selector": by_selector, "per_video": by_video, "median_abs_materializer_gain": median_abs_mat,
        "median_abs_selector_difference": median_abs_sel, "median_selector_spread": float(np.median(selector_spread)),
        "effect_ratio_materializer_over_selector": ratio,
        "materializer_vs_selector_effect": ("MATERIALIZER_EFFECT_GREATER" if median_abs_mat > median_abs_sel else "MATERIALIZER_EFFECT_APPROX_OR_SMALLER"),
        "mean_cross_negative_overmerge": overmerge, "decision": decision, "rationale": rationale,
    }


def reports(protocol: dict[str, Any], metrics: list[dict[str, Any]], effects: list[dict[str, Any]], selector_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    # Failure taxonomy covers both direction cases; examples are selected mechanically.
    rows = []
    for kind, subset in (("largest_k3_improvements", sorted(effects, key=lambda x: (-x["Delta_F1"], x["video_id"], x["selector"], x["budget"]))[:5]),
                         ("largest_k3_regressions", sorted(effects, key=lambda x: (x["Delta_F1"], x["video_id"], x["selector"], x["budget"]))[:5])):
        for effect in subset:
            pair = [m for m in metrics if all(m[k] == effect[k] for k in ("video_id", "query_id", "selector", "budget", "seed"))]
            k0, k3 = next(m for m in pair if m["materializer"] == "K0"), next(m for m in pair if m["materializer"] == "K3")
            if effect["Delta_F1"] > 0:
                mechanism = "K3 separated sparse positive anchors and/or avoided selected-negative barrier crossings."
            elif effect["Delta_F1"] < 0:
                mechanism = "K3 fragmentation or duration/barrier constraints reduced overlap matches relative to K0's broad span."
            else:
                mechanism = "No primary-metric change under the same trace."
            rows.append({"case_group": kind, "video_id": effect["video_id"], "selector": effect["selector"], "budget": effect["budget"],
                         "Delta_F1": effect["Delta_F1"], "F1_K0": effect["F1_K0"], "F1_K3": effect["F1_K3"],
                         "cross_negative_overmerge_K0": k0["cross_negative_overmerge"], "cross_negative_overmerge_K3": k3["cross_negative_overmerge"],
                         "fragmentation_K0": k0["positive_fragmentation"], "fragmentation_K3": k3["positive_fragmentation"], "mechanism_interpretation": mechanism,
                         "trace_hash": k0["trace_hash"]})
    write_csv_once(OUT / "failure_taxonomy.csv", rows, list(rows[0]) if rows else ["case_group"])
    effect_md = "\n".join(
        f"- {v}: median ΔF1 `{compact(x['median_delta_f1'])}`, mean `{compact(x['mean_delta_f1'])}`, K3-better `{x['better_fraction']:.1%}` ({x['n']} cells)."
        for v, x in summary["per_video"].items())
    selector_md = "\n".join(
        f"- {s}: median ΔF1 `{compact(x['median_delta_f1'])}`, K3-better `{x['better_fraction']:.1%}` ({x['n']} cells)."
        for s, x in summary["per_selector"].items())
    report = f"""# P0 V3 Materializer Validation V2

## Executive decision

`MATERIALIZATION_MAINLINE_DECISION = {summary['decision']}`

{summary['rationale']}

This is a **cached semantic-oracle replay under QUERY_BUDGET**, not a physical wall-clock or hard-deadline experiment.  It evaluates recovery of a frozen **model-relative** reference relation.  The reference events were constructed by full-grid current-V3 K3, so all event-level conclusions carry the qualified reference-construction interaction stated in the V10 circularity audit.

## Frozen experimental contract

- Protocol: `{protocol['protocol_hash']}`.
- Videos: DALI, HANGZHOU, WUHAN (three independent source videos).
- Candidate/proxy source: prospective frozen protocol `{protocol['input_artifacts']['scan_proxy_protocol']['sha256']}`.
- Reference: V10 1475/1475 release `{protocol['input_artifacts']['v10_reference_manifest']['sha256']}`.
- Selectors: {', '.join(x['name'] for x in SELECTORS)}; all deterministic, no seeds beyond `0`.
- Budgets: {list(BUDGETS)} semantic/oracle invocation calls per video/query.
- Primary matcher: strict positive temporal overlap; one-to-one maximum cardinality, then tIoU. Sensitivity uses tIoU > 0.30.
- Controlled invariant: K0/K3 consume byte-identical recorded query order and outcomes in every valid pair.

## Controlled matrix

Valid controlled pairs: `{summary['valid_controlled_pairs']}` of `{len(effects)}`.  K3 better/equal/worse: `{summary['k3_better']} / {summary['equal']} / {summary['worse']}` (`{summary['k3_better_fraction']:.1%}` strictly better).

Mean ΔF1: `{compact(summary['mean_delta_f1'])}` (bootstrap 95% CI `{compact(summary['mean_delta_f1_bootstrap_95_ci'][0])}` to `{compact(summary['mean_delta_f1_bootstrap_95_ci'][1])}`).  Median ΔF1: `{compact(summary['median_delta_f1'])}` (bootstrap 95% CI `{compact(summary['median_delta_f1_bootstrap_95_ci'][0])}` to `{compact(summary['median_delta_f1_bootstrap_95_ci'][1])}`).

### Per independent video

{effect_md}

### Selector robustness

{selector_md}

## Materializer versus selector effect

- Median `|K3-K0|`: `{compact(summary['median_abs_materializer_gain'])}`.
- Median pairwise `|selector A-selector B|` at fixed K3: `{compact(summary['median_abs_selector_difference'])}`.
- Descriptive ratio: `{compact(summary['effect_ratio_materializer_over_selector'])}`.
- Result: `{summary['materializer_vs_selector_effect']}`.

## Mechanism diagnostics

Mean selected-negative units inside a multi-anchor prediction: K0 `{summary['mean_cross_negative_overmerge']['K0']:.3f}`, K3 `{summary['mean_cross_negative_overmerge']['K3']:.3f}`.  This diagnostic is trace-local rather than human-ground-truth causal evidence; detailed largest gains/regressions are in `failure_taxonomy.csv`.

## Allowed claim

Only the conditional mechanism claim supported by the recorded statistics: under sparse cached semantic verification, this experiment compares reconstruction of the frozen full-grid **model-relative K3-defined event relation**.  It does not establish human semantic correctness, universal event-boundary superiority, or hard-deadline superiority.
"""
    write_text_once(OUT / "FINAL_RESEARCH_REPORT.md", report)
    decision = f"""# Materialization Mainline Decision

Decision: `{summary['decision']}`

Evidence level: controlled cached replay; model-relative and circularity-qualified.

Independent videos: `3`

Comparable selectors: `3`

Controlled pairs: `{summary['valid_controlled_pairs']}`

Median Delta F1: `{compact(summary['median_delta_f1'])}`

Fraction K3 > K0: `{summary['k3_better_fraction']:.1%}`

Main failure mode reduced: selected-negative barrier crossings, K0 `{summary['mean_cross_negative_overmerge']['K0']:.3f}` vs K3 `{summary['mean_cross_negative_overmerge']['K3']:.3f}` mean per cell.

Main unresolved risk: the evaluation event relation itself is current-V3-K3 constructed from full-grid model-relative labels; this supports a conditional reconstruction study, not independent human event-boundary truth.

Recommended next experiment: a pre-frozen boundary-insensitive or small frozen human sanity evaluation, selected independently of these P0 results, to test whether the observed effect survives the K3-defined reference interaction.
"""
    write_text_once(OUT / "MAINLINE_DECISION.md", decision)


def run() -> None:
    protocol = load_protocol()
    labels, candidates, references = load_data()
    config, _, _ = frozen_k3_config()
    metrics: list[dict[str, Any]] = []
    controlled_pairs: list[dict[str, Any]] = []
    trace_checks: list[dict[str, Any]] = []
    for video in VIDEOS:
        for spec in SELECTORS:
            selector = spec["name"]
            for budget in BUDGETS:
                selected = select_trace(selector, candidates[video], budget)
                trace = trace_payload(selector, selected, labels)
                trace_hash = canonical_hash(trace)
                queried = [labels[uid] for uid in trace["queried_unit_ids"]]
                common = {
                    "video_id": video, "query_id": QUERY_ID, "budget": budget, "seed": 0, "selector": selector,
                    "trace_hash": trace_hash, "queried_units_hash": canonical_hash(trace["queried_unit_ids"]),
                    "query_order_hash": canonical_hash(trace["query_order"]), "oracle_outcomes_hash": canonical_hash(trace["oracle_outcomes"]),
                    "oracle_calls": trace["oracle_call_count"], "query_order": json.dumps(trace["query_order"], separators=(",", ":")),
                    "queried_unit_ids": json.dumps(trace["queried_unit_ids"], separators=(",", ":")),
                    "oracle_outcomes": json.dumps(trace["oracle_outcomes"], separators=(",", ":")),
                }
                produced = {"K0": k0_materialize(video, queried), "K3": k3_materialize(queried, config)}
                for materializer, predicted in produced.items():
                    primary = metric_row(predicted, references[video], MatchConfig(**{k: PRIMARY_MATCH[k] for k in ("minimum_tiou", "boundary_tolerance_sec")}))
                    sens = metric_row(predicted, references[video], MatchConfig(**{k: SENSITIVITY_MATCH[k] for k in ("minimum_tiou", "boundary_tolerance_sec")}))
                    diag = diagnostics(predicted, references[video], queried)
                    row = {**common, "materializer": materializer, **primary, "sensitivity_F1_tiou_0_30": sens["F1"],
                           "sensitivity_TP_tiou_0_30": sens["TP"], **diag}
                    metrics.append(row)
                    controlled_pairs.append({**common, "materializer": materializer, "TP": primary["TP"], "FP": primary["FP"], "FN": primary["FN"],
                                             "precision": primary["precision"], "recall": primary["recall"], "F1": primary["F1"],
                                             "event_count": primary["event_count"], "valid_controlled_pair": True})
                trace_checks.append({"video_id": video, "query_id": QUERY_ID, "selector": selector, "budget": budget, "seed": 0,
                                     "trace_hash_K0": trace_hash, "trace_hash_K3": trace_hash, "queried_units_hash_K0": common["queried_units_hash"],
                                     "queried_units_hash_K3": common["queried_units_hash"], "query_order_hash_K0": common["query_order_hash"],
                                     "query_order_hash_K3": common["query_order_hash"], "oracle_outcomes_hash_K0": common["oracle_outcomes_hash"],
                                     "oracle_outcomes_hash_K3": common["oracle_outcomes_hash"], "oracle_calls_K0": budget, "oracle_calls_K3": budget,
                                     "status": "VALID_CONTROLLED_PAIR"})
    effects = paired_effects(metrics)
    if not all(row["valid_controlled_pair"] for row in effects):
        raise RuntimeError("trace identity failure: invalid cells must not enter analysis")
    selector_rows = selector_effect_rows(metrics)
    fields = list(controlled_pairs[0]); write_csv_once(OUT / "controlled_pairs.csv", controlled_pairs, fields)
    write_csv_once(OUT / "event_metrics.csv", metrics, list(metrics[0]))
    write_csv_once(OUT / "trace_identity_checks.csv", trace_checks, list(trace_checks[0]))
    write_csv_once(OUT / "materializer_effects.csv", effects, list(effects[0]))
    write_csv_once(OUT / "selector_effects.csv", selector_rows, list(selector_rows[0]))
    per_video = []
    for video in VIDEOS:
        subset = [r for r in effects if r["video_id"] == video]
        per_video.append({"video_id": video, "valid_pairs": len(subset), "median_Delta_F1": float(np.median([r["Delta_F1"] for r in subset])),
                          "mean_Delta_F1": float(np.mean([r["Delta_F1"] for r in subset])), "K3_better_fraction": sum(r["Delta_F1"] > 1e-12 for r in subset) / len(subset)})
    write_csv_once(OUT / "per_video_summary.csv", per_video, list(per_video[0]))
    summary = decision_summary(effects, metrics, selector_rows)
    write_json_once(OUT / "pooled_summary.json", summary)
    write_csv_once(OUT / "pooled_summary.csv", [{k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in summary.items()}], list(summary))
    reports(protocol, metrics, effects, selector_rows, summary)
    make_plots(metrics, effects, selector_rows)
    print(json.dumps({"status": "COMPLETE", "protocol_hash": protocol["protocol_hash"], **{k: summary[k] for k in ("valid_controlled_pairs", "median_delta_f1", "k3_better_fraction", "decision")}}, sort_keys=True))


def self_test() -> None:
    cfg = K3UnitEventConfig()
    def label(uid: str, start: float, outcome: str) -> ModelRelativeUnitLabel:
        return ModelRelativeUnitLabel(uid, QUERY_ID, "TEST", start, start + 10, outcome)  # type: ignore[arg-type]
    pos_a, neg, unknown, pos_b = label("a", 0, "relevant"), label("n", 10, "not_relevant"), label("u", 10, "unknown"), label("b", 20, "relevant")
    assert len(k0_materialize("TEST", [pos_a, neg, pos_b])) == 1
    assert len(k3_materialize([pos_a, neg, pos_b], cfg)) == 2, "verified negative must be a K3 barrier"
    assert len(k3_materialize([pos_a, unknown, pos_b], cfg)) == 1, "one unknown full bridge must remain legal"
    e0 = k0_materialize("TEST", [pos_a, neg, pos_b])
    e3 = k3_materialize([pos_a, neg, pos_b], cfg)
    ref = [EventRecord("r", QUERY_ID, "TEST", 0, 10, 1., "VERIFIED_EVENT", (), (), "r", None)]
    a = metric_row(e0, ref, MatchConfig()); b = metric_row(e0, ref, MatchConfig())
    assert a == b, "matcher must be deterministic"
    trace = {"queried_unit_ids": ["a", "n", "b"], "query_order": ["a", "n", "b"], "oracle_outcomes": ["relevant", "not_relevant", "relevant"], "oracle_call_count": 3}
    assert canonical_hash(trace) == canonical_hash(dict(trace)), "trace hash must be stable"
    print("P0_V2_SELF_TEST_PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("self-test", "freeze", "run"))
    args = parser.parse_args()
    if args.action == "self-test": self_test()
    elif args.action == "freeze": freeze()
    else: run()


if __name__ == "__main__":
    main()
