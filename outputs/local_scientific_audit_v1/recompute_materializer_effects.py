#!/usr/bin/env python3
"""Stdlib-only deterministic recomputation of P0 K3-vs-K0 and mechanism medians.

Uses only csv/json (no numpy/pandas) to independently verify:
  - K3 vs K0 controlled-pair median Delta_F1 (materializer_effects.csv)
  - gap-only / duration-cap / negative-barrier / complex-K3 marginals
    (mechanism_effects.csv), including an independent F1_to - F1_from check.
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P0 = ROOT / "outputs/p0_materializer_validation_v3"
MECH = ROOT / "outputs/p0_materializer_mechanism_ablation_v1"


def median(values):
    vals = sorted(float(v) for v in values)
    n = len(vals)
    if n == 0:
        return float("nan")
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def mean(values):
    vals = list(values)
    return sum(vals) / len(vals) if vals else float("nan")


def load_csv(path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def stats(deltas, tol=1e-12):
    n = len(deltas)
    pos = sum(1 for d in deltas if d > tol)
    eq = sum(1 for d in deltas if abs(d) <= tol)
    neg = sum(1 for d in deltas if d < -tol)
    return {
        "cells": n,
        "median": median(deltas),
        "mean": mean(deltas),
        "positive": pos,
        "equal": eq,
        "negative": neg,
    }


def main():
    out = {}

    # ---- 1. K3 vs K0 controlled effect (materializer_effects.csv) ----
    eff = load_csv(P0 / "materializer_effects.csv")
    deltas = [float(r["Delta_F1"]) for r in eff if r["valid_controlled_pair"] == "True"]
    out["k3_vs_k0"] = stats(deltas)

    # ---- 2. Mechanism marginals (mechanism_effects.csv) ----
    mech = load_csv(MECH / "mechanism_effects.csv")
    out["mechanisms"] = {}
    for mechanism in (
        "gap constraint",
        "duration cap",
        "queried-negative barrier",
        "current-V3 unknown/parse/exact semantics",
    ):
        rows = [r for r in mech if r["mechanism"] == mechanism]
        deltas = [float(r["Delta_F1"]) for r in rows]
        # Independent verification using F1_to - F1_from rather than stored Delta_F1.
        rederived = [float(r["F1_to"]) - float(r["F1_from"]) for r in rows]
        mismatch = [i for i, (a, b) in enumerate(zip(deltas, rederived)) if abs(a - b) > 1e-9]
        out["mechanisms"][mechanism] = {
            **stats(deltas),
            "independent_F1to_minus_F1from_median": median(rederived),
            "delta_mismatch_rows": mismatch[:5],
            "delta_mismatch_count": len(mismatch),
        }

    # ---- 3. Cross-check with stored pooled summary ----
    pooled = json.loads((P0 / "pooled_summary.json").read_text(encoding="utf-8"))
    out["pooled_summary_reported"] = {
        "median_delta_f1": pooled.get("median_delta_f1"),
        "mean_delta_f1": pooled.get("mean_delta_f1"),
        "k3_better": pooled.get("k3_better"),
        "equal": pooled.get("equal"),
        "worse": pooled.get("worse"),
        "valid_controlled_pairs": pooled.get("valid_controlled_pairs"),
        "decision": pooled.get("decision"),
    }

    # ---- 4. Mechanism summary CSV cross-check ----
    summ = load_csv(MECH / "mechanism_summary.csv")
    out["mechanism_summary_csv"] = {
        r["mechanism"]: {
            "median_Delta_F1": float(r["median_Delta_F1"]),
            "mean_Delta_F1": float(r["mean_Delta_F1"]),
            "cells": int(r["cells"]),
        }
        for r in summ
    }

    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
