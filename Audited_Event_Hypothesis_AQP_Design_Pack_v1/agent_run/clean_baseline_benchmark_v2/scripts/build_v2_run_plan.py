#!/usr/bin/env python3
"""Mechanically reconstruct the clean benchmark v2 run plan from frozen v1 registries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve()
PACK = HERE.parent.parent
V1 = PACK.parent / "clean_baseline_benchmark_v1"

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def main() -> None:
    out = PACK / "configs"
    out.mkdir(parents=True, exist_ok=True)
    baseline = pd.read_csv(V1 / "baselines/baseline_run_registry.csv")
    base_cfg = pd.read_csv(V1 / "baselines/baseline_configs.csv")
    current = pd.read_csv(V1 / "current_method/current_method_runs.csv")
    if len(baseline) != 1464 or len(current) != 12:
        raise RuntimeError(f"Unexpected authoritative v1 run counts: {len(baseline)}/{len(current)}")
    if baseline.run_id.duplicated().any() or current.run_id.duplicated().any():
        raise RuntimeError("Duplicate v1 run IDs")
    cfg_lookup = base_cfg.set_index("run_id")
    rows = []
    for source, frame, category in [("v1_baseline_registry", baseline, "baseline"), ("v1_current_registry", current, "current_method")]:
        for r in frame.to_dict("records"):
            if category == "baseline":
                config_hash = str(cfg_lookup.loc[r["run_id"], "config_hash"])
            else:
                cfg = json.loads((V1 / str(r["run_path"]) / "config.json").read_text(encoding="utf-8"))
                config_hash = canonical_hash(cfg)
            rows.append({
                "run_id": r["run_id"], "run_category": category, "method": r["method"],
                "track": r["track"], "configuration": r["method_variant"],
                "configuration_hash": config_hash, "seed": int(r["seed"]),
                "budget": int(r["horizon_budget"]), "materializer": r["materializer"],
                "expected_logical_calls": int(r["logical_oracle_calls"]),
                "clean_initial_state": True, "source_plan": source,
            })
    expected = pd.DataFrame(rows).sort_values("run_id").reset_index(drop=True)
    if len(expected) != 1476 or expected.run_id.duplicated().any():
        raise RuntimeError("Expected matrix reconstruction failed")
    expected.to_csv(out / "EXPECTED_RUN_MATRIX.csv", index=False)
    current_cfg = []
    for r in current.to_dict("records"):
        cfg = json.loads((V1 / str(r["run_path"]) / "config.json").read_text())
        current_cfg.append({"method": r["method"], "method_variant": r["method_variant"],
                            "config_json": json.dumps(cfg, sort_keys=True, separators=(",", ":")),
                            "config_hash": canonical_hash(cfg)})
    configs = pd.concat([base_cfg[["method", "method_variant", "config_json", "config_hash"]], pd.DataFrame(current_cfg)], ignore_index=True)
    configs = configs.drop_duplicates("config_hash").sort_values(["method", "method_variant", "config_hash"])
    configs.to_csv(out / "BASELINE_CONFIG_MANIFEST.csv", index=False)
    pd.read_csv(V1 / "frozen_inputs/random_seeds.csv").to_csv(out / "SEED_MANIFEST.csv", index=False)
    budgets = pd.read_csv(V1 / "frozen_inputs/budget_schedule.csv")
    budget_obj = {"budgets": budgets.budget.astype(int).tolist(), "unit_count": 347,
                  "cost_model": {"presence_query_logical_cost": 1, "duplicate_queries": "REJECT",
                                 "oracle_build_physical_calls_excluded_from_method_budget": True},
                  "source_benchmark_id": json.loads((V1 / "BENCHMARK_MANIFEST.json").read_text())["benchmark_id"]}
    (out / "FROZEN_BUDGETS.json").write_text(json.dumps(budget_obj, indent=2, sort_keys=True) + "\n")
    names = {"EXPECTED_RUN_MATRIX.csv", "BASELINE_CONFIG_MANIFEST.csv", "SEED_MANIFEST.csv", "FROZEN_BUDGETS.json"}
    hashes = {p.name: sha256(p) for p in sorted(out.iterdir()) if p.name in names}
    (out / "RUN_PLAN_HASHES.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"baseline_runs": 1464, "current_method_runs": 12, "hashes": hashes}, sort_keys=True))

if __name__ == "__main__":
    main()
