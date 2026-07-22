#!/usr/bin/env python3
"""Fail-closed, independent recomputation audit of sealed Gate A artifacts."""

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent
OUT = PACKAGE / "outputs/gate_a_final"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def main():
    config = json.loads((PACKAGE / "config/gate_a_frozen.json").read_text())
    checks = []
    def check(name, passed, evidence):
        checks.append({"check": name, "passed": bool(passed), "evidence": str(evidence)})

    model_manifest = pd.read_csv(OUT / "model_file_manifest.csv")
    expected_models = {config["methods"][x]["model_id"]: config["methods"][x]["revision"] for x in ["image_text", "video_text"]}
    check("exact_model_repositories", set(model_manifest.source_repository) == set(expected_models), sorted(model_manifest.source_repository.unique()))
    check("exact_model_revisions", all(row.resolved_revision == expected_models[row.source_repository] == row.requested_revision for row in model_manifest.itertuples()), "requested=resolved=configured")
    model_hashes_ok = all(Path(row.cache_path).stat().st_size == row.size_bytes and sha256(Path(row.cache_path)) == row.sha256 for row in model_manifest.itertuples())
    check("all_model_file_sizes_and_hashes", len(model_manifest) == 16 and model_hashes_ok, f"files={len(model_manifest)}")

    complete = json.loads((OUT / "INFERENCE_COMPLETE.json").read_text())
    scores = pd.read_csv(OUT / "raw_scores.csv")
    expected_signals = set(config["methods"])
    grouped = scores.groupby("signal_id")
    coverage = all(len(g) == 347 and g.unit_id.nunique() == 347 and set(g.unit_id) == set(range(347)) for _, g in grouped)
    check("four_signals_347_exact_units", set(grouped.groups) == expected_signals and coverage, grouped.size().to_dict())
    metadata_ok = all(set(zip(g.model_id, g.model_revision, g.prompt_id)) == {(config["methods"][s]["model_id"], config["methods"][s]["revision"], config["methods"][s]["prompt_id"])} for s, g in grouped)
    check("frozen_score_metadata", metadata_ok, "all signal metadata equals frozen config")
    check("raw_score_seal", complete["scores_sha256"] == sha256(OUT / "raw_scores.csv"), complete["scores_sha256"])

    ranks = pd.read_csv(OUT / "sealed_ranking_manifest.csv")
    with (OUT / "raw_scores.csv").open(newline="", encoding="utf-8") as handle:
        exact_score_rows = list(csv.DictReader(handle))
    ranking_ok = True
    for row in ranks.itertuples():
        path = Path(row.path); sealed = pd.read_csv(path).sort_values("rank")
        part = [x for x in exact_score_rows if x["signal_id"] == row.signal_id]
        recomputed = [int(x["unit_id"]) for x in sorted(part, key=lambda x: (-float(x["score"]), int(x["unit_id"])))]
        ranking_ok &= sha256(path) == row.sha256 and len(sealed) == 347 and sealed.unit_id.astype(int).tolist() == recomputed
    check("ranking_hash_and_recomputation", len(ranks) == 4 and ranking_ok, f"rankings={len(ranks)}")

    runner = (PACKAGE / "scripts/run_gate_a_inference.py").read_text()
    forbidden = ["event_reference.csv", "oracle_observations.csv", 'config["inputs"]["events"]', "gate_b_link.csv"]
    check("static_inference_leakage_boundary", not any(token in runner for token in forbidden), "no evaluator/oracle path token in runner")
    inference_config = json.loads((OUT / "inference_configuration.json").read_text())
    check("input_and_sampling_identity", inference_config["video_sha256"] == "bad229001034002404fc82a44962b6daa2a5743457a53767db39772d705df610" and inference_config["sampling"] == {m: config["methods"][m]["sampling"] for m in ["image_text", "video_text"]}, inference_config["sampling"])

    runtime = pd.read_csv(OUT / "runtime_ledger.csv")
    required_runtime = {"model_load_seconds", "cold_total_inference_seconds", "warm_index_query_seconds", "data_loading_seconds", "preprocessing_cpu_seconds", "model_forward_seconds", "gpu_seconds", "peak_gpu_memory_mb", "failed_units", "retried_units", "frames_processed", "batch_size", "dtype", "attention_implementation"}
    runtime_ok = required_runtime.issubset(runtime.columns) and set(runtime.signal_id) == {"image_text", "video_text"} and dict(zip(runtime.signal_id, runtime.frames_processed)) == {"image_text": 347, "video_text": 2776} and runtime.failed_units.sum() == 0 and runtime.retried_units.sum() == 0
    check("complete_runtime_accounting", runtime_ok, f"columns={len(runtime.columns)}, rows={len(runtime)}")

    evaluation = OUT / "evaluation"
    gate = pd.read_csv(evaluation / "gate_b_link.csv")
    gate_ok = set(gate.signal_id) == expected_signals and len(gate) == 4 * len(config["top_k"])
    check("frozen_gate_b_integration", gate_ok, f"rows={len(gate)}")
    decision = json.loads((OUT / "FINAL_DECISION.json").read_text())
    no_go = not (gate.gate == "GO").any()
    check("decision_matches_registered_threshold", (decision["gate_a_decision"] == "UNIT_ORACLE_DARE_ACCELERATION_NO_GO") == no_go, f"any_public_GO={not no_go}")
    check("physical_exact_oracle_calls_zero", complete["physical_exact_oracle_vlm_calls"] == 0 and decision["physical_exact_oracle_vlm_calls"] == 0, "0")
    required_eval = ["ranking_metrics.csv", "gate_b_link.csv", "per_budget_event_metrics.csv", "event_f1_auc.csv", "unique_event_first_discovery.csv", "arc_map_overlap_divergence.csv", "ranking_diagnostics.csv", "public_to_oracle_gap.csv", "query_cost_normalized_results.csv", "per_unit_runtime.csv"]
    check("required_evaluation_artifacts", all((evaluation / x).is_file() for x in required_eval), required_eval)

    verdict = "PASS" if all(row["passed"] for row in checks) else "FAIL"
    payload = {"review_type": "independent_fail_closed_recomputation", "verdict": verdict, "checks": checks}
    (OUT / "INDEPENDENT_ADVERSARIAL_REVIEW.json").write_text(json.dumps(payload, indent=2) + "\n")
    lines = ["# Independent adversarial review — Gate A", "", f"**Verdict: `{verdict}`.**", "", "| Check | Result | Evidence |", "|---|---:|---|"]
    lines += [f"| {x['check']} | {'PASS' if x['passed'] else 'FAIL'} | {x['evidence'].replace('|','/')} |" for x in checks]
    (OUT / "INDEPENDENT_ADVERSARIAL_REVIEW.md").write_text("\n".join(lines) + "\n")
    if verdict != "PASS": raise SystemExit(1)
    manifest_rows = []
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "FILE_MANIFEST.csv"):
        manifest_rows.append({"path": str(path.relative_to(REPO)), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    pd.DataFrame(manifest_rows).to_csv(OUT / "FILE_MANIFEST.csv", index=False)
    print(OUT / "INDEPENDENT_ADVERSARIAL_REVIEW.md")


if __name__ == "__main__": main()
