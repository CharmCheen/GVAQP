#!/usr/bin/env python3
"""Fail-closed audit for the Phase-0 contract-blocked terminal state."""

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "DARE_AQP_Experiment_v1").is_dir())
OUT = ROOT / "DARE_AQP_Experiment_v1/outputs/gate_c0_physical_interval_operator_v1"

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

def rows(path):
    with path.open(newline="", encoding="utf-8") as f: return list(csv.DictReader(f))

checks = []
def check(name, passed, evidence): checks.append({"check": name, "status": "PASS" if passed else "FAIL", "evidence": str(evidence)})

for manifest_name in ["C0_SOURCE_MANIFEST.csv", "C0_INPUT_MANIFEST.csv"]:
    manifest = rows(OUT / "config" / manifest_name)
    ok = all((ROOT / r["path"]).is_file() and sha256(ROOT / r["path"]) == r["sha256"] for r in manifest)
    check(manifest_name + " hashes", ok, len(manifest))

config = json.loads((ROOT / "DARE_AQP_Experiment_v1/config/gate_c0.json").read_text())
missing = ["minimum_any_sensitivity", "maximum_any_false_negatives", "minimum_count_exact_accuracy",
           "maximum_count_undercount_rate", "abstention_gate_semantics"]
check("accuracy thresholds absent from frozen config", not any(key in config for key in missing), missing)
contract = " ".join((ROOT / "DARE_AQP_Experiment_v1/docs/INTERVAL_ORACLE_CONTRACT.md").read_text().split())
check("existing contract is exact ceiling only", "assumes exact operators" in contract and "Actual VLM costs are unknown" in contract, "explicit validity boundary")

calls = rows(OUT / "oracle/VLM_CALL_LEDGER.csv")
check("new physical call count", len(calls) == 0, len(calls))
decision = rows(OUT / "FINAL_DECISION.csv")
check("single blocked decision", len(decision) == 1 and decision[0]["decision"] == "INTERVAL_OPERATOR_CONTRACT_BLOCKED", decision[0]["decision"])
check("decision call accounting", decision[0]["physical_vlm_calls"] == "0" and decision[0]["call_budget"] == "160", "0/160")

gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.free", "--format=csv,noheader"], capture_output=True, text=True)
check("GPU availability not used as blocker", gpu.returncode == 0 and "A100" in gpu.stdout, gpu.stdout.strip())
model = ROOT / "models/vlm/qwen3_vl/Qwen3-VL-32B-Instruct"
check("strict model availability not used as blocker", model.is_dir() and len(list(model.glob("model-*.safetensors"))) == 14, model)
check("no interval inference session", "interval_oracle_gate_v1:" not in subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True).stdout, "no session")
manifest_path = OUT / "FILE_MANIFEST.csv"
if manifest_path.is_file():
    manifest_rows = rows(manifest_path)
    manifest_ok = all((ROOT / r["path"]).is_file() and sha256(ROOT / r["path"]) == r["sha256"] for r in manifest_rows)
else:
    manifest_rows, manifest_ok = [], False
check("all sealed file hashes", manifest_ok, len(manifest_rows))

verdict = "PASS" if all(x["status"] == "PASS" for x in checks) else "FAIL"
review = {"verdict": verdict, "review_scope": "contract-blocked terminal package",
          "checks": checks,
          "conclusion": "Stopping before call 1 is the only decision-compliant action; no physical-operator claim is validated."}
(OUT / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json").write_text(json.dumps(review, indent=2) + "\n")
if verdict != "PASS": raise SystemExit(1)
subprocess.run([sys.executable, str(ROOT / "garc_eval/interval_oracle_gate_v1/seal_blocked.py")], check=True)
print(verdict)
