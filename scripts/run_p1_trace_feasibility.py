#!/usr/bin/env python3
"""P1-A outcome-blind trace diversity / equal-yield feasibility audit.

This is deliberately not an event-recovery experiment: trace construction reads
only the released candidate positions and Proxy-A scores.  Frozen cached unit
outcomes are joined *after* traces exist solely to determine whether an
independent-reference experiment can form matched equal-yield comparisons.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1"
SCAN = ROOT / "outputs/v3_scan_proxy_preregistration_v1"
V10 = ROOT / "outputs/v10_multiseal_reference_v1"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
BUDGETS = (5, 10, 20, 50, 80, 100)
SEEDS = tuple(range(8))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def stable_unit(seed: int, candidate_id: str) -> float:
    raw = hashlib.sha256(f"P1_TRACE_SEED_V1|{seed}|{candidate_id}".encode()).digest()
    return int.from_bytes(raw[:8], "big") / 2**64


def temporal_coverage(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    def visit(lo: int, hi: int) -> None:
        if lo >= hi:
            return
        mid = (lo + hi) // 2
        out.append(rows[mid])
        visit(lo, mid); visit(mid + 1, hi)
    visit(0, len(rows))
    return out


def uniform(rows: list[dict], budget: int) -> list[dict]:
    if budget == 1:
        return [rows[0]]
    ix = [round(i * (len(rows) - 1) / (budget - 1)) for i in range(budget)]
    return [rows[i] for i in ix]


def mmr(rows: list[dict], budget: int, weight: float) -> list[dict]:
    """Frozen relevance + temporal novelty ranking; no outcomes or reference."""
    scores = np.asarray([float(r["proxy_score"]) for r in rows])
    lo, hi = float(scores.min()), float(scores.max())
    norm = (scores - lo) / (hi - lo) if hi > lo else np.zeros_like(scores)
    n = len(rows)
    chosen: list[int] = []
    remaining = set(range(n))
    while remaining and len(chosen) < budget:
        def val(i: int) -> tuple[float, int, str]:
            novelty = 1.0 if not chosen else min(abs(i - j) / max(n - 1, 1) for j in chosen)
            return ((1.0 - weight) * float(norm[i]) + weight * novelty, -int(rows[i]["candidate_order"]), str(rows[i]["candidate_id"]))
        best = max(remaining, key=val)
        chosen.append(best); remaining.remove(best)
    return [rows[i] for i in chosen]


def score_trace(selected: list[dict], labels: dict[str, str], n: int) -> dict:
    pos = sorted(int(x["candidate_order"]) for x in selected)
    positives = [x for x in selected if labels[x["unit_id"]] == "relevant"]
    ppos = sorted(int(x["candidate_order"]) for x in positives)
    regions = 0 if not pos else 1 + sum(b - a > 1 for a, b in zip(pos, pos[1:]))
    holes = ([pos[0], n - 1 - pos[-1]] + [b - a - 1 for a, b in zip(pos, pos[1:])]) if pos else [n]
    coverage = ((pos[-1] - pos[0] + 1) / n) if pos else 0.0
    pdisp = float(np.std(ppos) / max(n - 1, 1)) if ppos else 0.0
    return {
        "verified_positive_count": len(positives),
        "positive_yield": len(positives) / len(selected),
        "number_of_temporal_regions_touched": regions,
        "coverage_fraction": coverage,
        "largest_unqueried_gap_units": max(holes),
        "temporal_dispersion": float(np.std(pos) / max(n - 1, 1)) if pos else 0.0,
        "positive_temporal_dispersion_ORACLE_OBSERVED_AFTER_VERIFY": pdisp,
    }


def main() -> None:
    out = OUT / "TRACE_POPULATION_AUDIT.csv"
    if out.exists():
        raise RuntimeError(f"immutable audit already exists: {out}")
    unit = pd.read_parquet(V10 / "FINAL_UNIT_REFERENCE.parquet")
    labels = dict(zip(unit.unit_id.astype(str), unit.authoritative_label.astype(str)))
    traces: list[dict] = []
    for video in VIDEOS:
        c = pd.read_parquet(SCAN / "frozen_tables" / video / "candidate_table.parquet")
        p = pd.read_parquet(SCAN / "frozen_tables" / video / "proxy_table.parquet")
        rows = c.merge(p, on=["video_id", "candidate_id"], validate="one_to_one").sort_values("candidate_order").to_dict("records")
        for r in rows:
            r["unit_id"] = str(r["source_unit_ids"][0])
        for budget in BUDGETS:
            generators: list[tuple[str, int, list[dict]]] = [
                ("UniformTemporal", 0, uniform(rows, budget)),
                ("StaticProxyRank", 0, sorted(rows, key=lambda x: (-float(x["proxy_score"]), int(x["candidate_order"])))[:budget]),
                ("CoverageFirst", 0, temporal_coverage(rows)[:budget]),
                ("MMR_w025", 0, mmr(rows, budget, .25)),
                ("MMR_w050", 0, mmr(rows, budget, .50)),
                ("MMR_w075", 0, mmr(rows, budget, .75)),
            ]
            for seed in SEEDS:
                generators.append(("SeededTemporalHash", seed, sorted(rows, key=lambda x: (stable_unit(seed, str(x["candidate_id"])), int(x["candidate_order"])))[:budget]))
            for generator, seed, selected in generators:
                ids = [str(x["unit_id"]) for x in selected]
                digest = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
                traces.append({"video_id": video, "query_id": "Q_DRIVER_RESPONSE_V1", "proxy_family": "PROXY_A_YOLOV8N_OBJECT_MOTION", "budget": budget, "generator": generator, "seed": seed, "trace_hash": digest, "selected_unit_ids_json": json.dumps(ids, separators=(",", ":")), **score_trace(selected, labels, len(rows))})
    raw = pd.DataFrame(traces).drop_duplicates("trace_hash").sort_values(["video_id", "budget", "generator", "seed"]).reset_index(drop=True)
    raw.to_csv(out, index=False)

    # Exact-yield strata meet the primary rule.  Pair count is deliberately
    # collapsed to one high-vs-low geometry contrast per stratum, avoiding a
    # combinatorial pseudo-replication claim.
    rows: list[dict] = []
    for key, group in raw.groupby(["video_id", "query_id", "proxy_family", "budget", "verified_positive_count"], sort=True):
        if len(group) < 2:
            continue
        geom = "number_of_temporal_regions_touched"
        spread = float(group[geom].max() - group[geom].min())
        if spread <= 0:
            continue
        hi = group.sort_values([geom, "trace_hash"], ascending=[False, True]).iloc[0]
        lo = group.sort_values([geom, "trace_hash"], ascending=[True, True]).iloc[0]
        rows.append({"video_id": key[0], "query_id": key[1], "proxy_family": key[2], "budget": key[3], "verified_positive_count": key[4], "traces_in_stratum": len(group), "primary_geometry": geom, "geometry_min": float(group[geom].min()), "geometry_max": float(group[geom].max()), "geometry_range": spread, "coverage_range": float(group.coverage_fraction.max()-group.coverage_fraction.min()), "effective_independent_comparison_count": 1, "high_geometry_trace_hash": hi.trace_hash, "low_geometry_trace_hash": lo.trace_hash})
    matched = pd.DataFrame(rows)
    matched.to_csv(OUT / "TRACE_EQUAL_YIELD_MATCHES.csv", index=False)
    by_video = matched.groupby("video_id").size().to_dict() if len(matched) else {}
    sufficient = len(matched) >= 12 and len(by_video) == 3 and all(by_video.get(v, 0) >= 3 for v in VIDEOS)
    summary = {
        "status": "PASS_SINGLE_QUERY_TRACE_FEASIBILITY" if sufficient else "P1_DESIGN_INSUFFICIENT",
        "trace_population": len(raw), "exact_equal_yield_matched_strata": len(matched),
        "video_query_clusters_represented": len(by_video), "matched_strata_by_video": by_video,
        "effective_independent_comparison_count": int(matched.effective_independent_comparison_count.sum()) if len(matched) else 0,
        "median_primary_geometry_range": float(matched.geometry_range.median()) if len(matched) else None,
        "rule": "PASS requires >=12 exact-yield geometry-varying strata, all 3 available video-query clusters represented, and >=3 strata/video; this certifies only trace feasibility, never P1 scientific success.",
        "outcome_blind_generation": True,
        "caveat": "Only one released semantic query and Proxy A are available. Passing this audit does not satisfy P1's six video-query clusters or two-natural-proxy requirements."
    }
    (OUT / "TRACE_FEASIBILITY_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (OUT / "P1_TRACE_FEASIBILITY.md").write_text("# P1-A Trace-diversity feasibility audit\n\n" + "\n".join(f"- **{k}**: `{v}`" for k, v in summary.items()) + "\n\nTrace generators were fixed before cached outcomes were joined: UniformTemporal, StaticProxyRank, CoverageFirst, three fixed MMR weights, and eight seeded temporal hashes. Outcomes never choose or rank a trace. Exact verified-positive count is the primary matched-yield stratum; no near-yield relaxation is used here.\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
