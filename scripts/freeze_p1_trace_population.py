#!/usr/bin/env python3
"""Freeze P1 trace identities from released candidates and cheap proxies only.

No semantic outcomes, human annotation, event reference, C1 event, or result
artifact is opened by this script.  It is safe to run while Qwen32 acquisition
is in progress and is intentionally separate from the later yield audit.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1"
PROTOCOL = OUT / "P1_TRACE_POPULATION_PROTOCOL.json"
MANIFEST = OUT / "P1_OUTCOME_BLIND_TRACE_MANIFEST.csv"
SCAN = ROOT / "outputs/v3_scan_proxy_preregistration_v1/frozen_tables"
PROXY_B = OUT / "proxy_b_kinematic/PROXY_B_KINEMATIC_SCORES.parquet"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
BUDGETS = (5, 10, 20, 50, 80, 100)
SEEDS = tuple(range(8))
PROXIES = {
    "PROXY_A_YOLOV8N_OBJECT_MOTION": "proxy_a_score",
    "PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS": "proxy_b_score",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def chash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def stable_unit(seed: int, candidate_id: str) -> float:
    return int.from_bytes(hashlib.sha256(f"P1_TRACE_SEED_V2|{seed}|{candidate_id}".encode()).digest()[:8], "big") / 2**64


def uniform(rows: list[dict], budget: int) -> list[dict]:
    if budget == 1:
        return [rows[0]]
    return [rows[round(i * (len(rows) - 1) / (budget - 1))] for i in range(budget)]


def coverage_first(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    def visit(lo: int, hi: int) -> None:
        if lo >= hi:
            return
        mid = (lo + hi) // 2
        output.append(rows[mid])
        visit(lo, mid)
        visit(mid + 1, hi)
    visit(0, len(rows))
    return output


def mmr(rows: list[dict], score_name: str, budget: int, weight: float) -> list[dict]:
    scores = np.array([float(x[score_name]) for x in rows])
    lo, hi = float(scores.min()), float(scores.max())
    norm = (scores - lo) / (hi - lo) if hi > lo else np.zeros_like(scores)
    remaining = set(range(len(rows))); selected: list[int] = []
    while remaining and len(selected) < budget:
        def key(i: int) -> tuple[float, int, str]:
            novelty = 1.0 if not selected else min(abs(i-j)/max(len(rows)-1, 1) for j in selected)
            return ((1-weight)*float(norm[i]) + weight*novelty, -int(rows[i]["candidate_order"]), str(rows[i]["candidate_id"]))
        pick = max(remaining, key=key)
        selected.append(pick); remaining.remove(pick)
    return [rows[i] for i in selected]


def load_rows(video: str) -> list[dict]:
    candidate = pd.read_parquet(SCAN / video / "candidate_table.parquet")
    proxy_a = pd.read_parquet(SCAN / video / "proxy_table.parquet")[["video_id", "candidate_id", "proxy_score"]].rename(columns={"proxy_score": "proxy_a_score"})
    proxy_b = pd.read_parquet(PROXY_B)[["video_id", "candidate_id", "proxy_score"]].rename(columns={"proxy_score": "proxy_b_score"})
    joined = candidate.merge(proxy_a, on=["video_id", "candidate_id"], validate="one_to_one").merge(proxy_b, on=["video_id", "candidate_id"], validate="one_to_one").sort_values("candidate_order")
    if len(joined) != len(candidate) or not joined[["proxy_a_score", "proxy_b_score"]].notna().all().all():
        raise RuntimeError(f"proxy/candidate merge invalid: {video}")
    rows = joined.to_dict("records")
    for row in rows:
        sources = list(row["source_unit_ids"])
        if len(sources) != 1:
            raise RuntimeError("one-unit candidate contract broken")
        row["unit_id"] = str(sources[0])
    return rows


def freeze() -> None:
    if PROTOCOL.exists() or MANIFEST.exists():
        raise RuntimeError("P1 trace population already frozen")
    if not PROXY_B.exists():
        raise RuntimeError("frozen Proxy B score table missing")
    rows = {video: load_rows(video) for video in VIDEOS}
    source_hashes = {str(PROXY_B.relative_to(ROOT)): sha(PROXY_B)}
    for video in VIDEOS:
        for name in ("candidate_table.parquet", "proxy_table.parquet"):
            source_hashes[str((SCAN/video/name).relative_to(ROOT))] = sha(SCAN/video/name)
    protocol = {
        "protocol_id": "P1_OUTCOME_BLIND_TRACE_POPULATION_V2",
        "status": "FROZEN_BEFORE_SECOND_QUERY_OUTCOMES_AND_HUMAN_LABELS",
        "uses_semantic_oracle_outcomes": False,
        "uses_human_reference": False,
        "uses_event_reference": False,
        "video_ids": list(VIDEOS),
        "query_ids_for_later_outcome_join": ["Q_DRIVER_RESPONSE_V1", "Q_VULNERABLE_ROAD_USER_CONFLICT_V1"],
        "proxy_families": list(PROXIES),
        "budgets": list(BUDGETS),
        "generators": {
            "UniformTemporal": "evenly spaced positions; no proxy",
            "StaticProxyRank": "descending score within the named frozen proxy family",
            "CoverageFirst": "recursive temporal bisection; no proxy",
            "MMR_w025": "fixed proxy relevance + 0.25 temporal novelty",
            "MMR_w050": "fixed proxy relevance + 0.50 temporal novelty",
            "MMR_w075": "fixed proxy relevance + 0.75 temporal novelty",
            "SeededTemporalHash": "candidate-id hash ordering, seeds 0..7",
        },
        "candidate_semantics": "one released V3 candidate per original 10-second unit",
        "source_artifacts_sha256": source_hashes,
        "code": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha(Path(__file__))},
    }
    protocol["protocol_hash"] = chash(protocol)
    rows_out: list[dict] = []
    for video, base in rows.items():
        for proxy_family, score_name in PROXIES.items():
            for budget in BUDGETS:
                generated: list[tuple[str, int, list[dict]]] = [
                    ("UniformTemporal", 0, uniform(base, budget)),
                    ("StaticProxyRank", 0, sorted(base, key=lambda r: (-float(r[score_name]), int(r["candidate_order"]), str(r["candidate_id"])))[:budget]),
                    ("CoverageFirst", 0, coverage_first(base)[:budget]),
                    ("MMR_w025", 0, mmr(base, score_name, budget, .25)),
                    ("MMR_w050", 0, mmr(base, score_name, budget, .50)),
                    ("MMR_w075", 0, mmr(base, score_name, budget, .75)),
                ]
                generated.extend(("SeededTemporalHash", seed, sorted(base, key=lambda r: (stable_unit(seed, str(r["candidate_id"])), int(r["candidate_order"])))[:budget]) for seed in SEEDS)
                for generator, seed, selected in generated:
                    ids = [str(r["unit_id"]) for r in selected]
                    positions = sorted(int(r["candidate_order"]) for r in selected)
                    regions = 1 + sum(b-a > 1 for a,b in zip(positions, positions[1:])) if positions else 0
                    holes = ([positions[0], len(base)-1-positions[-1]] + [b-a-1 for a,b in zip(positions, positions[1:])]) if positions else [len(base)]
                    rows_out.append({
                        "video_id": video, "proxy_family": proxy_family, "budget": budget, "generator": generator, "seed": seed,
                        "trace_hash": chash(ids), "trace_instance_id": chash([video, proxy_family, budget, generator, seed, ids]),
                        "selected_unit_ids_json": json.dumps(ids, separators=(",", ":")),
                        "number_of_temporal_regions_touched": regions,
                        "coverage_fraction": (positions[-1]-positions[0]+1)/len(base) if positions else 0.0,
                        "temporal_dispersion": float(np.std(positions)/max(len(base)-1, 1)) if positions else 0.0,
                        "largest_unqueried_gap_units": max(holes), "query_redundancy": sum(b-a <= 1 for a,b in zip(positions,positions[1:]))/len(positions) if positions else 0.0,
                        "protocol_hash": protocol["protocol_hash"],
                    })
    frame = pd.DataFrame(rows_out).sort_values(["video_id", "proxy_family", "budget", "generator", "seed"])
    if len(frame) != len(VIDEOS)*len(PROXIES)*len(BUDGETS)*(6+len(SEEDS)):
        raise RuntimeError("unexpected trace population size")
    OUT.mkdir(parents=True, exist_ok=True)
    PROTOCOL.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    frame.to_csv(MANIFEST, index=False)
    (OUT/"P1_TRACE_POPULATION_FREEZE.md").write_text(f"# P1 outcome-blind trace population freeze\n\n- Trace instances: `{len(frame)}`.\n- Hash: `{sha(MANIFEST)}`.\n- Protocol: `{protocol['protocol_hash']}`.\n- Semantic outcomes and human labels read during construction: **none**.\n\nThe later audit must join outcomes only after the frozen outcome table is complete; it must not alter or filter this trace population based on event recovery.\n")
    print(json.dumps({"status": "FROZEN", "trace_instances": len(frame), "protocol_hash": protocol["protocol_hash"]}, sort_keys=True))


if __name__ == "__main__":
    freeze()
