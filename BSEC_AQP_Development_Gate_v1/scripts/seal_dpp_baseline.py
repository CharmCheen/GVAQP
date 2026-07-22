#!/usr/bin/env python3
"""Seal a label-blind quality-weighted greedy DPP baseline ranking."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ALLOWED_KEYS = {"unit_id", "clip_score", "embedding"}


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rank_percentile(scores: np.ndarray) -> np.ndarray:
    ids = np.arange(len(scores))
    order = np.lexsort((ids, -scores))
    out = np.empty(len(scores), dtype=float)
    out[order] = np.linspace(1.0, 0.0, len(scores), endpoint=True)
    return out


def greedy_dpp_ranking(scores: np.ndarray, embeddings: np.ndarray) -> list[int]:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    if np.any(norms <= 0):
        raise RuntimeError("DPP embeddings contain a zero-norm row")
    features = embeddings / norms
    quality = np.exp(2.0 * rank_percentile(scores))
    kernel = (quality[:, None] * (features @ features.T)) * quality[None, :]
    kernel.flat[:: len(kernel) + 1] += 1e-9
    n = len(scores)
    factors = np.zeros((n, n), dtype=float)
    residual = np.diag(kernel).copy()
    selected = []
    used = np.zeros(n, dtype=bool)
    for step in range(n):
        candidates = np.flatnonzero(~used)
        best = int(candidates[np.argmax(residual[candidates])])
        selected.append(best)
        used[best] = True
        if step == n - 1:
            break
        denom = float(np.sqrt(max(residual[best], 1e-15)))
        correction = factors[:step, best] @ factors[:step, :]
        update = (kernel[best, :] - correction) / denom
        factors[step, :] = update
        residual = np.maximum(0.0, residual - update * update)
        residual[used] = -np.inf
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True, help="NPZ with unit_id, clip_score, embedding only")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budgets", default="5,10,20,50,80,100")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("Refusing to write without --execute")
    archive = np.load(args.features, allow_pickle=False)
    keys = set(archive.files)
    if keys != ALLOWED_KEYS:
        raise RuntimeError(f"feature archive keys must be exactly {sorted(ALLOWED_KEYS)}; got {sorted(keys)}")
    unit_ids = archive["unit_id"].astype(int)
    scores = archive["clip_score"].astype(float)
    embeddings = archive["embedding"].astype(float)
    n = len(unit_ids)
    if unit_ids.tolist() != list(range(n)) or scores.shape != (n,) or embeddings.shape[0] != n:
        raise RuntimeError("DPP feature shapes or temporal unit order are invalid")
    if not np.all(np.isfinite(scores)) or not np.all(np.isfinite(embeddings)):
        raise RuntimeError("DPP features contain non-finite values")
    budgets = [int(value) for value in args.budgets.split(",")]
    if budgets != sorted(set(budgets)) or any(value <= 0 or value > n for value in budgets):
        raise RuntimeError("invalid budgets")
    ranking = greedy_dpp_ranking(scores, embeddings)
    rows = []
    for budget in budgets:
        for rank, unit_id in enumerate(ranking[:budget], 1):
            rows.append(
                {
                    "method": "quality_weighted_greedy_dpp",
                    "budget": budget,
                    "selection_rank": rank,
                    "unit_id": unit_id,
                    "clip_score": scores[unit_id],
                }
            )
    args.output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output / "sealed_selections.csv", index=False)
    ledger = {
        "status": "SEALED_LABEL_BLIND",
        "method": "quality_weighted_greedy_dpp",
        "kernel": "diag(exp(2*clip_rank_percentile)) @ normalized_embedding_gram @ diag(exp(2*clip_rank_percentile)) + 1e-9*I",
        "population": n,
        "budgets": budgets,
        "features_sha256": sha256(args.features),
        "selector_script_sha256": sha256(Path(__file__).resolve()),
        "forbidden_label_or_reference_inputs_opened": [],
        "physical_exact_oracle_vlm_calls": 0,
    }
    (args.output / "SEAL.json").write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(ledger, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
