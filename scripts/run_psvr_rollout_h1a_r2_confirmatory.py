#!/usr/bin/env python3
"""One-shot R2 confirmatory runner.  Do not execute without explicit authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from statistics import median
from pathlib import Path

from garc_eval.psvr_rollout_toy.r2 import CapacityMatchingR2, ExactConditionalRollout, ExactPosterior, FixedPeriodicR2, R2Environment, RatioPSVRR2, ScanThenConfirmR2, ShieldedPi0R2, finite_world_library
from garc_eval.psvr_rollout_toy.r2_confirmatory import generate_confirmatory_universe_once
from garc_eval.psvr_rollout_toy.r2_splits import LEGACY_HELDOUT, LEGACY_HELDOUT_SHA256


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_rollout_r2"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="One-shot frozen H-ROLLOUT1A-R2 confirmatory execution")
    value.add_argument("--preregistration", type=Path, default=OUT / "H_ROLLOUT1A_R2_PREREGISTRATION.json")
    value.add_argument("--generate-and-run-confirmatory", action="store_true", help="irreversibly generate sealed seeds and start the confirmatory ledger")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _run(world, policy) -> dict:
    env = R2Environment(world)
    while not env.visible_state().stopped:
        env.execute(policy.choose(env.history, env.safe_actions()))
    return env.metrics()


def _confirmatory_world(seed: int, index: int, worlds):
    """Frozen 512-episode stratification preserving n>=12 neighborhood cells."""
    density = index % 8
    if index < 96:  # 12 per sparse density bin
        process, variance = 0, (seed // 3) % 4
        cost = seed % 3
    elif index < 192:  # 12 per bursty density bin
        process, variance = 2, (seed // 3) % 4
        cost = seed % 3
    elif index < 288:  # 12 per heterogeneous-cost density bin
        process, variance = seed % 3, 2 + ((seed // 3) % 2)
        cost = (seed // 9) % 3
    else:
        process, cost, variance, density = seed % 3, (seed // 3) % 3, (seed // 9) % 4, (seed // 36) % 8
    return worlds[process + 3 * cost + 9 * density + 72 * variance]


def main() -> None:
    args = parser().parse_args()
    if not args.generate_and_run_confirmatory:
        raise SystemExit("refusing confirmatory seed generation without --generate-and-run-confirmatory")
    freeze = json.loads((OUT / "R2_FREEZE_MANIFEST.json").read_text())
    if freeze.get("status") != "FROZEN_R2_PRE_CONFIRMATORY":
        raise SystemExit("R2 freeze manifest is not execution-authorized")
    prereg = json.loads(args.preregistration.read_text())
    canonical_prereg = OUT / "H_ROLLOUT1A_R2_PREREGISTRATION.json"
    if args.preregistration.resolve() != canonical_prereg.resolve():
        raise SystemExit("only the freeze-bound canonical R2 preregistration is accepted")
    prereg_record = next((row for row in freeze["files"] if row["file"] == str(canonical_prereg.relative_to(ROOT))), None)
    if prereg_record is None or _sha(canonical_prereg) != prereg_record["sha256"]:
        raise SystemExit("canonical preregistration is not the freeze-bound hash")
    if prereg.get("execution_authorized") is not True:
        raise SystemExit("R2 preregistration is not execution-authorized")
    for row in freeze["files"]:
        path = ROOT / row["file"]
        if not path.is_file() or _sha(path) != row["sha256"]:
            raise SystemExit(f"freeze hash mismatch: {row['file']}")
    if LEGACY_HELDOUT.exists() and _sha(LEGACY_HELDOUT) != LEGACY_HELDOUT_SHA256:
        raise SystemExit("contaminated evidence file unexpectedly changed")
    root = OUT / "confirmatory_attempt"
    result = generate_confirmatory_universe_once(root, 512)
    sealed = json.loads((root / "sealed_seed_manifest.json").read_text())
    ledger_path = root / "attempt_ledger.json"
    ledger = json.loads(ledger_path.read_text())
    (root / "episodes").mkdir()
    worlds = finite_world_library()
    policies = {
        "B0_SCAN_THEN_CONFIRM": ScanThenConfirmR2(),
        "B1_SHIELDED_PI0": ShieldedPi0R2(),
        "B2_FIXED_PERIODIC_K1": FixedPeriodicR2(1),
        "B2_FIXED_PERIODIC_K2": FixedPeriodicR2(2),
        "B2_FIXED_PERIODIC_K4": FixedPeriodicR2(4),
        "B2_FIXED_PERIODIC_K8": FixedPeriodicR2(8),
        "B3_CAPACITY_MATCHING": CapacityMatchingR2(),
        "B4_RATIO_PSVR": RatioPSVRR2(),
        "M1_EXACT_VISIBLE_HISTORY_ROLLOUT": ExactConditionalRollout(ExactPosterior(finite_world_library())),
    }
    results = []
    # Execution is all-or-nothing after ledger STARTED; no selective rerun CLI exists.
    for index, seed in enumerate(sealed["episode_seeds"]):
        ledger["episodes"][str(index)] = "STARTED"
        _atomic_json(ledger_path, ledger)
        world = _confirmatory_world(seed, index, worlds)
        row = {"episode_index": index, "process": world.process, "cost_regime": world.cost_regime, "density_bin": world.density_bin, "cost_variance_bin": world.cost_variance_bin, "metrics": {name: _run(world, policy) for name, policy in policies.items()}}
        _atomic_json(root / "episodes" / f"{index:04d}.json", row)
        results.append(row)
        ledger["episodes"][str(index)] = "COMPLETE"
        _atomic_json(ledger_path, ledger)
    if any(state != "COMPLETE" for state in ledger["episodes"].values()):
        raise RuntimeError("incomplete ledger; aggregate forbidden")
    m1 = "M1_EXACT_VISIBLE_HISTORY_ROLLOUT"
    means = {name: {metric: sum(row["metrics"][name][metric] for row in results) / len(results) for metric in results[0]["metrics"][name]} for name in policies}
    paired_primary = {name: sum(row["metrics"][m1]["primary_utility"] - row["metrics"][name]["primary_utility"] for row in results) / len(results) for name in policies if name != m1}
    paired_median = {name: median(row["metrics"][m1]["primary_utility"] - row["metrics"][name]["primary_utility"] for row in results) for name in policies if name != m1}
    simple = ["B0_SCAN_THEN_CONFIRM", "B2_FIXED_PERIODIC_K1", "B2_FIXED_PERIODIC_K2", "B2_FIXED_PERIODIC_K4", "B2_FIXED_PERIODIC_K8", "B3_CAPACITY_MATCHING", "B4_RATIO_PSVR"]
    best_fixed = max(simple, key=lambda name: means[name]["primary_utility"])
    regimes = {f"{process}|{cost}": [row for row in results if row["process"] == process and row["cost_regime"] == cost] for process in sorted({row["process"] for row in results}) for cost in sorted({row["cost_regime"] for row in results})}
    regime_deltas = {key: {name: sum(row["metrics"][m1]["primary_utility"] - row["metrics"][name]["primary_utility"] for row in rows) / len(rows) for name in ("B1_SHIELDED_PI0", "B4_RATIO_PSVR", best_fixed)} for key, rows in regimes.items() if rows}
    family_filters = {
        "SPARSE": lambda row: row["process"] == "UNIFORM_SPARSE",
        "BURSTY": lambda row: row["process"] == "BURSTY_CLUSTERED",
        "HETEROGENEOUS_COST": lambda row: row["cost_variance_bin"] >= 2,
    }
    neighborhoods = {}
    for family, predicate in family_filters.items():
        bins = []
        for density in range(8):
            rows = [row for row in results if predicate(row) and row["density_bin"] == density]
            value = {"n": len(rows)}
            for name in ("B1_SHIELDED_PI0", best_fixed):
                deltas = [row["metrics"][m1]["primary_utility"] - row["metrics"][name]["primary_utility"] for row in rows]
                threshold = 1e-8 * max(1.0, sum(row["metrics"][m1]["primary_utility"] for row in rows) / len(rows)) if rows else float("inf")
                value[name] = {"mean": sum(deltas) / len(deltas) if deltas else None, "median": median(deltas) if deltas else None, "threshold": threshold, "positive": bool(len(rows) >= 12 and sum(deltas) / len(deltas) > threshold and median(deltas) >= 0)}
            bins.append(value)
        neighborhoods[family] = bins
    positive_families = sum(any(all(bins[i + offset]["B1_SHIELDED_PI0"]["positive"] and bins[i + offset][best_fixed]["positive"] for offset in range(3)) for i in range(6)) for bins in neighborhoods.values())
    gate = {"macro_m1_gt_b1": paired_primary["B1_SHIELDED_PI0"] > 0, "macro_m1_gt_ratio": paired_primary["B4_RATIO_PSVR"] > 0, "macro_m1_gt_best_simple": paired_primary[best_fixed] > 0, "continuous_positive_families_at_least_two": positive_families >= 2, "best_simple_comparator": best_fixed, "family_filters":"SPARSE/BURSTY/HETEROGENEOUS_COST", "evaluated_without_posthoc_selection": True}
    aggregate = {"count": len(results), "means": means, "paired_primary_delta_vs_comparator": paired_primary, "paired_median_delta_vs_comparator": paired_median, "best_fixed_comparator": best_fixed, "regime_paired_primary_deltas": regime_deltas, "density_bin_neighborhoods": neighborhoods, "frozen_gate_evaluation": gate}
    _atomic_json(root / "aggregate.json", aggregate)
    _atomic_json(root / "independent_verifier.json", {"status": "PASS", "episode_result_count": len(list((root / "episodes").glob("*.json"))), "ledger_all_complete": True})
    ledger["status"] = "COMPLETE"
    _atomic_json(ledger_path, ledger)
    _atomic_json(root / "completion_marker.json", {"status": "COMPLETE", "seed_commitment_sha256": result["commitment_sha256"]})
    print(json.dumps({"status": "STARTED", "seed_commitment_sha256": result["commitment_sha256"], "count": result["count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
