#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from garc_eval.scan_confirm_controller.config import load_config
from garc_eval.scan_confirm_controller.fixed_ratio import FixedPolicyController
from garc_eval.scan_confirm_controller.myopic_controller import MyopicVPSController
from garc_eval.scan_confirm_controller.offline_oracle import multi_step_trace_oracle, one_step_action_oracle
from garc_eval.scan_confirm_controller.runner import TraceReplayEnvironment, run_benchmark

OUT = ROOT / "outputs/scan_confirm_decision_v1"


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f: json.dump(value, f, indent=2, sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f: frame.to_csv(f, index=False); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def controller_for(name: str, seed: int, config: dict):
    if name.startswith("R8") or name.startswith("A"):
        kwargs = dict(alpha_s=1, beta_s=1, alpha_c=1, beta_c=1, margin=.001, tie_break="SCAN", minimum_bucket_samples=3)
        if name == "A1_NO_COST_NORMALIZATION": kwargs["cost_normalization"] = False
        if name == "A2_NO_SHRINKAGE": kwargs["shrinkage"] = False
        if name in {"A3_GLOBAL_SCAN", "A5_NO_COVERAGE_BUCKETS"}: kwargs["use_scan_buckets"] = False
        if name in {"A4_GLOBAL_CONFIRM", "A6_NO_SCORE_BUCKETS"}: kwargs["use_confirm_buckets"] = False
        if name == "A7_MARGIN_ZERO": kwargs["margin"] = 0
        if name == "A8_CONFIRM_TIE": kwargs["tie_break"] = "CONFIRM"
        if name == "A9_NO_REMAINING_BUDGET_VALUE": kwargs["use_remaining_budget_value"] = False
        return MyopicVPSController(**kwargs)
    return FixedPolicyController(name, seed)


def run_matrix(names: list[str], destination: Path, config: dict) -> pd.DataFrame:
    summaries = []
    for name in names:
        seeds = config["seeds"] if name == "R7_RANDOM" else [0]
        for task in config["development_groups"]:
            for budget in config["budgets_sec"]:
                for seed in seeds:
                    kwargs = {"constant_median_cost": name == "A10_CONSTANT_MEDIAN_COST"}
                    summary, ledger = run_benchmark(controller_for(name, seed, config), task, budget, name, seed, **kwargs)
                    summaries.append(summary)
                    atomic_json(destination / "traces" / f"{name}__{task}__B{int(budget)}__S{seed}.json", ledger)
    frame = pd.DataFrame(summaries); atomic_csv(destination / "run_metrics.csv", frame); return frame


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--phase", choices=["baselines", "myopic", "oracle", "ablations", "all"], default="all")
    args = parser.parse_args(); config = load_config(ROOT / "configs/scan_confirm_myopic_vps.yaml")
    freeze = json.loads((OUT / "contracts/freeze_manifest.json").read_text())
    contract_hash = hashlib.sha256((ROOT / "docs/SCAN_CONFIRM_DECISION_BENCHMARK_CONTRACT_V1.md").read_bytes()).hexdigest()
    if freeze["contract_hash"] != contract_hash: raise SystemExit("contract changed after freeze")
    if args.phase in {"baselines", "all"}:
        run_matrix(["R0_SCAN_FIRST", "R1_CONFIRM_FIRST", "R2_RATIO_75_25", "R3_RATIO_50_50", "R4_RATIO_25_75", "R5_PERIODIC", "R6_FRONTIER_RULE", "R7_RANDOM"], OUT / "fixed_ratio_baselines", config)
    if args.phase in {"myopic", "all"}:
        run_matrix(["R8_MYOPIC_VPS"], OUT / "myopic_vps", config)
    if args.phase in {"ablations", "all"}:
        run_matrix(["A0_FULL", "A1_NO_COST_NORMALIZATION", "A2_NO_SHRINKAGE", "A3_GLOBAL_SCAN", "A4_GLOBAL_CONFIRM", "A5_NO_COVERAGE_BUCKETS", "A6_NO_SCORE_BUCKETS", "A7_MARGIN_ZERO", "A8_CONFIRM_TIE", "A9_NO_REMAINING_BUDGET_VALUE", "A10_CONSTANT_MEDIAN_COST"], OUT / "ablations", config)
    if args.phase in {"oracle", "all"}:
        summaries=[]; meta=[]
        for task in config["development_groups"]:
            for budget in config["budgets_sec"]:
                one, ledger = one_step_action_oracle(TraceReplayEnvironment(task, budget)); summaries.append(one)
                atomic_json(OUT / "offline_oracle/traces" / f"ONE_STEP__{task}__B{int(budget)}.json", ledger)
                multi, mledger, info = multi_step_trace_oracle(TraceReplayEnvironment(task, budget), min(16, int(config["offline_beam_width"])))
                summaries.append(multi); meta.append({"task_id": task, "budget_sec": budget, **info})
                atomic_json(OUT / "offline_oracle/traces" / f"MULTI_STEP__{task}__B{int(budget)}.json", mledger)
        atomic_csv(OUT / "offline_oracle/run_metrics.csv", pd.DataFrame(summaries)); atomic_json(OUT / "offline_oracle/search_metadata.json", meta)


if __name__ == "__main__": main()
