#!/usr/bin/env python3
"""Seal label-blind PSTR selections from a proxy-only unit table."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import pandas as pd


FORBIDDEN_COLUMNS = {
    "label",
    "oracle_label",
    "is_positive",
    "event_id",
    "reference_event_id",
    "boundary_start",
    "boundary_end",
}


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pstr(scores: list[float], budget: int) -> list[int]:
    n_units = len(scores)
    n_cells = min(n_units, budget + int(math.floor(budget / 4)))
    winners = []
    for cell in range(n_cells):
        lo = n_units * cell // n_cells
        hi = n_units * (cell + 1) // n_cells
        winners.append(max(range(lo, hi), key=lambda unit_id: (scores[unit_id], -unit_id)))
    return sorted(winners, key=lambda unit_id: (-scores[unit_id], unit_id))[:budget]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy-input", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--unit-id-column", default="unit_id")
    parser.add_argument("--proxy-column", default="proxy_score")
    parser.add_argument("--budgets", default="5,10,20,50,80,100")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("Refusing to write without --execute")

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("candidate", {}).get("method_id") != "pstr_5_to_4":
        raise RuntimeError("protocol does not freeze PSTR-5:4")
    with args.proxy_input.open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    forbidden = sorted(set(header) & FORBIDDEN_COLUMNS)
    if forbidden:
        raise RuntimeError(f"proxy-only input contains forbidden columns: {forbidden}")
    required = {args.unit_id_column, args.proxy_column}
    if not required.issubset(header):
        raise RuntimeError(f"proxy-only input lacks required columns: {sorted(required - set(header))}")
    frame = pd.read_csv(
        args.proxy_input, usecols=[args.unit_id_column, args.proxy_column]
    ).sort_values(args.unit_id_column)
    unit_ids = frame[args.unit_id_column].astype(int).tolist()
    if unit_ids != list(range(len(frame))):
        raise RuntimeError("unit IDs must be the contiguous temporal order 0..n-1")
    scores = frame[args.proxy_column].astype(float).tolist()
    if not all(math.isfinite(value) for value in scores):
        raise RuntimeError("proxy scores contain non-finite values; missing-value fill is forbidden")
    budgets = [int(value) for value in args.budgets.split(",")]
    if budgets != sorted(set(budgets)) or any(value <= 0 or value > len(frame) for value in budgets):
        raise RuntimeError("budgets must be unique, increasing, positive, and no larger than n")

    rows = []
    for budget in budgets:
        for rank, unit_id in enumerate(pstr(scores, budget), 1):
            rows.append(
                {
                    "method": "pstr_5_to_4",
                    "budget": budget,
                    "selection_rank": rank,
                    "unit_id": unit_id,
                    "proxy_score": scores[unit_id],
                }
            )
    args.output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output / "sealed_selections.csv", index=False)
    script_path = Path(__file__).resolve()
    ledger = {
        "status": "SEALED_LABEL_BLIND",
        "method": "pstr_5_to_4",
        "population": len(frame),
        "budgets": budgets,
        "proxy_input": str(args.proxy_input.resolve()),
        "proxy_input_sha256": sha256(args.proxy_input),
        "protocol": str(args.protocol.resolve()),
        "protocol_sha256": sha256(args.protocol),
        "selector_script_sha256": sha256(script_path),
        "forbidden_label_or_reference_inputs_opened": [],
        "physical_exact_oracle_vlm_calls": 0,
    }
    (args.output / "SEAL.json").write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(ledger, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
