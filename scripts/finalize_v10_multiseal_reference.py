#!/usr/bin/env python3
"""Compatibility validation and complete-only V10-MS reference finalizer."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative"
V9_EXEC = BASE / "full_grid_execution_staged_v9_runtime_recovery"
V9_PACKAGE = BASE / "full_grid_preregistration_staged_v9_runtime_recovery"
OUT = ROOT / "outputs/v10_multiseal_reference_v1"
import sys
sys.path.insert(0, str(ROOT / "src"))
from garc_eval.accelerated_event_query.k3_unit_event_adapter import K3UnitEventAdapter, K3UnitEventConfig
from garc_eval.accelerated_event_query.model_relative_labels import ModelRelativeUnitLabel
from garc_eval.accelerated_event_query.oracle_v3_manifest import canonical_hash, load_json, sha256_file
from garc_eval.accelerated_event_query.oracle_v3_parser import parse_oracle_v3_response

UNIT_SCHEMA = pa.schema([
    ("ordinal", pa.int64()), ("unit_id", pa.string()), ("video_id", pa.string()),
    ("start_time", pa.float64()), ("end_time", pa.float64()), ("unit_kind", pa.string()),
    ("parse_status", pa.string()), ("authoritative_label", pa.string()),
    ("diagnostic_confidence", pa.string()), ("diagnostic_evidence", pa.string()),
    ("origin_seal", pa.string()), ("origin_raw_sha256", pa.string()),
    ("origin_record_payload_sha256", pa.string()),
])
EVENT_SCHEMA = pa.schema([
    ("event_id", pa.string()), ("query_id", pa.string()), ("video_id", pa.string()),
    ("start_time", pa.float64()), ("end_time", pa.float64()), ("evidence_status", pa.string()),
    ("source_unit_ids", pa.list_(pa.string())), ("k3_group", pa.string()),
    ("k3_config_sha256", pa.string()),
])


def write_json_once(path: Path, value: dict[str, Any]) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text: raise RuntimeError(f"immutable mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def write_text_once(path: Path, value: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != value: raise RuntimeError(f"immutable mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(value, encoding="utf-8")


def protocol() -> dict[str, Any]:
    p = load_json(OUT / "MULTI_SEAL_PROTOCOL.json")
    unsigned = {k: v for k, v in p.items() if k != "protocol_hash"}
    if canonical_hash(unsigned) != p["protocol_hash"] or not p.get("PROTOCOL_FROZEN"):
        raise RuntimeError("invalid frozen V10-MS protocol")
    return p


def seal(kind: str) -> dict[str, Any]:
    name = {"shadow": "SEAL_SHADOW", "missing": "SEAL_B"}[kind]
    value = load_json(OUT / "seals" / name / "EXECUTION_SEAL.json")
    unsigned = {k: v for k, v in value.items() if k != "seal_hash"}
    if canonical_hash(unsigned) != value["seal_hash"]: raise RuntimeError("execution seal hash mismatch")
    if value["protocol_hash"] != protocol()["protocol_hash"]: raise RuntimeError("execution seal protocol mismatch")
    return value


def record(path: Path, expected_unit_id: str, seal_value: dict[str, Any]) -> dict[str, Any]:
    item = load_json(path)
    if item.get("status") != "AUTHENTICATED_V10_MS_RAW_OUTPUT": raise RuntimeError("unexpected V10 raw status")
    if item.get("unit_id") != expected_unit_id or item.get("seal_hash") != seal_value["seal_hash"]: raise RuntimeError("V10 raw identity mismatch")
    if item.get("semantic_contract") != protocol()["semantic_contract"]: raise RuntimeError("V10 raw semantic contract mismatch")
    if hashlib.sha256(item.get("raw", "").encode()).hexdigest() != item.get("raw_response_sha256"): raise RuntimeError("V10 raw response hash mismatch")
    parsed = parse_oracle_v3_response(item["raw"])
    if (item.get("parse_status"), item.get("authoritative_label"), item.get("parsed")) != (parsed.parse_status, parsed.effective_label, parsed.parsed): raise RuntimeError("V10 strict parser mismatch")
    unsigned = {k: v for k, v in item.items() if k != "record_payload_sha256"}
    if canonical_hash(unsigned) != item.get("record_payload_sha256"): raise RuntimeError("V10 record payload mismatch")
    return item


def compatibility() -> None:
    p, s = protocol(), seal("shadow")
    units = {x["unit_id"]: x for x in load_json(V9_PACKAGE / "FULL_GRID_UNIT_MANIFEST.json")["units"]}
    rows = []
    raw_equal = parsed_equal = 0
    for unit_id in s["unit_ids"]:
        old = load_json(V9_EXEC / units[unit_id]["raw_output_relative_path"])
        new_path = OUT / "seals" / "SEAL_SHADOW" / "raw" / f"{unit_id}.json"
        new = record(new_path, unit_id, s)
        contract_equal = new["semantic_contract"] == p["semantic_contract"]
        processed_equal = old["processed_input_sha256"] == new["processed_input_sha256"]
        raw_match = old["raw_response_sha256"] == new["raw_response_sha256"]
        parsed_match = (old["parse_status"], old["authoritative_label"], old["parsed"]) == (new["parse_status"], new["authoritative_label"], new["parsed"])
        raw_equal += raw_match; parsed_equal += parsed_match
        rows.append({"video_id": units[unit_id]["video_id"], "unit_id": unit_id, "v9_raw_sha256": old["raw_response_sha256"], "new_raw_sha256": new["raw_response_sha256"], "processed_input_hash_equal": processed_equal, "semantic_contract_equal": contract_equal, "raw_generation_equal": raw_match, "parsed_terminal_equal": parsed_match, "status": "PASS" if raw_match and parsed_match and processed_equal and contract_equal else ("QUALIFIED_PASS" if parsed_match and processed_equal and contract_equal else "FAIL")})
    path = OUT / "CROSS_SEAL_COMPATIBILITY.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        w = csv.DictWriter(handle, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    status = "PASS" if all(x["status"] == "PASS" for x in rows) else ("QUALIFIED_PASS" if all(x["status"] != "FAIL" for x in rows) else "FAIL")
    decision = {"status": status, "protocol_hash": p["protocol_hash"], "shadow_seal_hash": s["seal_hash"], "rows": len(rows), "raw_generation_equal_rows": raw_equal, "parsed_terminal_equal_rows": parsed_equal, "csv_sha256": sha256_file(path)}
    decision["decision_hash"] = canonical_hash(decision)
    write_json_once(OUT / "CROSS_SEAL_COMPATIBILITY_DECISION.json", decision)
    print(json.dumps(decision, sort_keys=True))


def write_parquet_once(path: Path, table: pa.Table) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp"); pq.write_table(table, tmp, compression="zstd", version="2.6")
    if path.exists():
        if sha256_file(path) != sha256_file(tmp): tmp.unlink(); raise RuntimeError(f"immutable parquet mismatch: {path}")
        tmp.unlink(); return
    path.parent.mkdir(parents=True, exist_ok=True); tmp.replace(path)


def finalize() -> None:
    p, b = protocol(), seal("missing")
    comp = load_json(OUT / "CROSS_SEAL_COMPATIBILITY_DECISION.json")
    if comp["status"] not in {"PASS", "QUALIFIED_PASS"}: raise RuntimeError("cross-seal compatibility did not pass")
    units_payload = load_json(V9_PACKAGE / "FULL_GRID_UNIT_MANIFEST.json")
    units = {x["unit_id"]: x for x in units_payload["units"]}
    admissible = []
    with (OUT / "V9_UNIT_ADMISSIBILITY.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["admissibility_status"] == "ADMISSIBLE_V9": admissible.append(row["unit_id"])
    missing = load_json(OUT / "MISSING_UNIT_SET.json")["missing_unit_ids"]
    if set(admissible) & set(missing) or set(admissible) | set(missing) != set(units): raise RuntimeError("multi-seal unit union is incomplete or overlapping")
    result = load_json(OUT / "seals" / "SEAL_B" / "EXECUTION_RESULT.json")
    if result.get("status") != "COMPLETE": raise RuntimeError("Seal B did not complete")
    rows = []
    for unit in sorted(units_payload["units"], key=lambda x: x["ordinal"]):
        uid = unit["unit_id"]
        if uid in admissible:
            item = load_json(V9_EXEC / unit["raw_output_relative_path"]); origin = "SEAL_A_V9"
            # Admission audit already validated exact V9 record provenance.
        else:
            item = record(OUT / "seals" / "SEAL_B" / "raw" / f"{uid}.json", uid, b); origin = b["seal_id"]
        parsed = parse_oracle_v3_response(item["raw"])
        rows.append({"ordinal": unit["ordinal"], "unit_id": uid, "video_id": unit["video_id"], "start_time": unit["start_time"], "end_time": unit["end_time"], "unit_kind": unit["unit_kind"], "parse_status": parsed.parse_status, "authoritative_label": parsed.effective_label, "diagnostic_confidence": (parsed.parsed or {}).get("confidence"), "diagnostic_evidence": (parsed.parsed or {}).get("evidence"), "origin_seal": origin, "origin_raw_sha256": sha256_file(V9_EXEC / unit["raw_output_relative_path"]) if uid in admissible else sha256_file(OUT / "seals" / "SEAL_B" / "raw" / f"{uid}.json"), "origin_record_payload_sha256": item["record_payload_sha256"]})
    unit_path = OUT / "FINAL_UNIT_REFERENCE.parquet"; write_parquet_once(unit_path, pa.Table.from_pylist(rows, schema=UNIT_SCHEMA))
    k3_payload = load_json(ROOT / "outputs/accelerated_event_query_v1/oracle_protocol_v3_model_relative/k3_eventization/K3_UNIT_EVENT_CONFIG_V3.json")
    config = K3UnitEventConfig(**k3_payload["parameters"])
    labels = [ModelRelativeUnitLabel(unit_id=x["unit_id"], query_id="Q_DRIVER_RESPONSE_V1", video_id=x["video_id"], start_time=x["start_time"], end_time=x["end_time"], outcome=x["authoritative_label"], confidence=x["diagnostic_confidence"], evidence=x["diagnostic_evidence"]) for x in rows]
    relation_a = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1", config).materialize(labels)
    relation_b = K3UnitEventAdapter("Q_DRIVER_RESPONSE_V1", config).materialize(labels)
    if relation_a.relation_sha256 != relation_b.relation_sha256: raise RuntimeError("K3 reference rebuild is nondeterministic")
    events = [{"event_id": x.event_id, "query_id": x.query_id, "video_id": x.video_id, "start_time": x.start_time, "end_time": x.end_time, "evidence_status": x.evidence_status, "source_unit_ids": list(x.source_candidate_ids), "k3_group": x.k3_group, "k3_config_sha256": relation_a.k3_config_sha256} for x in relation_a.events]
    event_path = OUT / "K3_MODEL_RELATIVE_EVENT_RELATION.parquet"; write_parquet_once(event_path, pa.Table.from_pylist(events, schema=EVENT_SCHEMA))
    manifest = {"status": "FORMAL_MULTI_SEAL_MODEL_RELATIVE_REFERENCE_RELEASE", "protocol_hash": p["protocol_hash"], "unit_reference_hash": sha256_file(unit_path), "event_relation_hash": relation_a.relation_sha256, "event_relation_parquet_sha256": sha256_file(event_path), "k3_config_hash": relation_a.k3_config_sha256, "expected_units": len(units), "seal_a_units": len(admissible), "seal_b_units": len(missing), "cross_seal_compatibility": comp["status"], "no_duplicate_authoritative_unit": True, "complete": len(rows) == len(units)}
    manifest["manifest_hash"] = canonical_hash(manifest); write_json_once(OUT / "REFERENCE_MANIFEST.json", manifest)
    circularity = """# Reference Circularity Audit\n\nThe unit-level semantic outcomes are VLM model-relative and precede event construction. The published event relation is then constructed with the frozen K3 rule from complete unit outcomes. Method-side sparse K3 uses the same rule family. Therefore event-level K3-vs-K0 F1 against this relation carries a **reference-construction interaction risk**: K3 may align with the evaluator-side grouping definition.\n\nDecision: `QUALIFIED_BUT_VALID` only for a mechanism study conditioned on this model-relative K3 event definition. P0 must report unit-level/sensitivity diagnostics and must not claim independent human event-boundary superiority from this reference alone. The risk is not fatal to testing whether sparse K3 reconstructs the frozen K3-defined relation, but it is fatal to an unconditional claim that K3 is universally superior.\n"""
    write_text_once(OUT / "REFERENCE_CIRCULARITY_AUDIT.md", circularity)
    release = f"# Multi-Seal Release Decision\n\nDecision: `RELEASED`\n\nComplete frozen unit union: `{len(rows)} / {len(units)}`. Cross-seal compatibility: `{comp['status']}`. Unit reference hash: `{sha256_file(unit_path)}`. Relation hash: `{relation_a.relation_sha256}`.\n\nP0 is eligible only under the qualified model-relative circularity limitation in `REFERENCE_CIRCULARITY_AUDIT.md`.\n"
    write_text_once(OUT / "MULTI_SEAL_RELEASE_DECISION.md", release)
    print(json.dumps(manifest, sort_keys=True))


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("action", choices=["compatibility", "finalize"]); args = ap.parse_args()
    if args.action == "compatibility": compatibility()
    else: finalize()


if __name__ == "__main__": main()
