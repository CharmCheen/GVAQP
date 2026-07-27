#!/usr/bin/env python3
"""Development-only coverage-baseline replay with frozen evaluator metrics."""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from partial_scan_pilot_common import atomic_csv, atomic_json, atomic_text, transition  # noqa: E402

BENCH = ROOT / "benchmarks/partial_scan_pilot_v1"
IMM, DERIVED = BENCH / "immutable", BENCH / "derived"
OUT = ROOT / "outputs/partial_scan_method_development_v1/coverage_baselines"
BUDGET_SEC, SEEDS = 60.0, range(8)
METHODS = ("SEQUENTIAL", "RANDOM_WITHOUT_REPLACEMENT", "UNIFORM_PREFIX", "ANYTIME_LARGEST_GAP", "DISTANCE_COVERAGE_GREEDY", "OBSERVATION_COVERAGE_GREEDY")


def unit_event_map(mapping: pd.DataFrame) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in mapping.itertuples(index=False):
        for unit in json.loads(row.source_unit_ids):
            result.setdefault(unit, set()).add(row.reference_event_id)
    return result


def choose(method: str, units: pd.DataFrame, scanned: list[str], rng: random.Random, observation: dict[str, float]) -> str:
    remaining = units[~units.unit_id.isin(scanned)]
    if method == "SEQUENTIAL": return str(remaining.iloc[0].unit_id)
    if method == "RANDOM_WITHOUT_REPLACEMENT": return str(remaining.iloc[rng.randrange(len(remaining))].unit_id)
    indices = dict(zip(units.unit_id, units.unit_index))
    if method == "UNIFORM_PREFIX":
        for level in range(math.ceil(math.log2(max(2, len(units)))) + 1):
            stride = max(1, len(units) // (2 ** level))
            for index in range(0, len(units), stride):
                candidate = str(units.iloc[index].unit_id)
                if candidate not in scanned: return candidate
    if method == "ANYTIME_LARGEST_GAP":
        if not scanned: return str(remaining.iloc[len(remaining) // 2].unit_id)
        return str(max(remaining.unit_id, key=lambda u: (min(abs(indices[u] - indices[s]) for s in scanned), -indices[u])))
    # Distance coverage uses temporal dispersion. Observation coverage breaks ties by
    # precomputed unit-local observable candidate/trigger mass, never reference events.
    if not scanned:
        return str(max(remaining.unit_id, key=lambda u: (observation.get(u, 0.0), -indices[u]))) if method == "OBSERVATION_COVERAGE_GREEDY" else str(remaining.iloc[len(remaining)//2].unit_id)
    return str(max(remaining.unit_id, key=lambda u: (min(abs(indices[u] - indices[s]) for s in scanned), observation.get(u, 0.0) if method == "OBSERVATION_COVERAGE_GREEDY" else 0.0, -indices[u])))


def estimated_cost(previous: dict | None, selected: dict, model: dict) -> float:
    tr = transition(previous, selected)
    key = f"{tr['transition_class']}|{tr['same_or_cross_gop']}|CONTROLLED_WARM"
    return float(model["strata"].get(key, {}).get("q90_action_cost_sec", model["fallback_q90_sec"]))


def run_one(method: str, seed: int, video: str, units: pd.DataFrame, events: dict[str, set[str]], observation: dict[str, float], model: dict) -> list[dict]:
    scanned: list[str] = []; exposed: set[str] = set(); rows=[]; elapsed=0.; previous=None; rng=random.Random(seed)
    total_events = set().union(*(events.get(str(u), set()) for u in units.unit_id))
    while len(scanned) < len(units):
        unit_id=choose(method, units, scanned, rng, observation); selected=units[units.unit_id.eq(unit_id)].iloc[0].to_dict(); cost=estimated_cost(previous, selected, model)
        if elapsed + cost > BUDGET_SEC: break
        scanned.append(unit_id); elapsed += cost; new=events.get(unit_id, set()) - exposed; exposed |= events.get(unit_id, set())
        indices=np.array([int(units[units.unit_id.eq(x)].iloc[0].unit_index) for x in scanned])
        all_indices=units.unit_index.to_numpy(); nearest=float(np.abs(all_indices[:,None]-indices[None,:]).min(axis=1).mean())
        rows.append({"video_id":video,"method":method,"seed":seed,"action_index":len(scanned),"unit_id":unit_id,"estimated_action_cost_sec":cost,"cumulative_scan_time_sec":elapsed,"new_exposed_event_count":len(new),"exposed_event_count":len(exposed),"event_exposure_fraction":len(exposed)/max(1,len(total_events)),"max_unscanned_gap_units":max(np.diff(sorted(indices)).max(initial=0)-1, int(all_indices.min()), int(all_indices.max()-indices.max())),"integrated_nearest_scan_distance_units":nearest,"observation_mass":observation.get(unit_id,0.)})
        previous=selected
    return rows


def main() -> None:
    timeline=pd.read_csv(IMM / "timeline_units.csv")
    mapping=pd.read_parquet(DERIVED / "candidate_event_map.parquet"); mapping=mapping[mapping.partition_offset_sec.eq(0)]
    events=unit_event_map(mapping)
    feature=pd.read_csv(ROOT / "outputs/partial_scan_method_development_v1/temporal_cost_audit/unit_observation_features.csv")
    observation=(feature.detection_count + feature.track_count + feature.trigger_count).groupby(feature.unit_id).first().to_dict()
    model=json.loads((DERIVED / "cost_calibration/conservative_cost_model.json").read_text())
    rows=[]
    for video, group in timeline.groupby("video_id"):
        group=group.sort_values("unit_index")
        for method in METHODS:
            for seed in SEEDS: rows.extend(run_one(method, seed, video, group, events, observation, model))
    trace=pd.DataFrame(rows); OUT.mkdir(parents=True,exist_ok=True); atomic_csv(OUT / "development_action_trace.csv",trace)
    summary=trace.groupby(["video_id","method","seed"]).agg(actions=("action_index","max"),exposure_scan_time_auc=("event_exposure_fraction",lambda x: float(np.trapezoid(x.to_numpy(), trace.loc[x.index,"cumulative_scan_time_sec"].to_numpy()))),exposure_at_end=("event_exposure_fraction","last"),time_to_first_exposure=("cumulative_scan_time_sec",lambda x: float(x.iloc[np.argmax(trace.loc[x.index,"new_exposed_event_count"].to_numpy()>0)]) if (trace.loc[x.index,"new_exposed_event_count"]>0).any() else np.nan),unused_budget=("cumulative_scan_time_sec",lambda x:BUDGET_SEC-float(x.iloc[-1])),max_gap=("max_unscanned_gap_units","last"),nearest_distance=("integrated_nearest_scan_distance_units","last")).reset_index()
    aggregate=summary.groupby(["video_id","method"]).mean(numeric_only=True).reset_index(); atomic_csv(OUT / "development_baseline_summary.csv",aggregate)
    checkpoints=trace[trace.action_index.isin([1,2,4,8,16])].groupby(["video_id","method","action_index"]).event_exposure_fraction.mean().reset_index(); atomic_csv(OUT / "exposure_checkpoints.csv",checkpoints)
    atomic_json(OUT / "coverage_baseline_manifest.json",{"scope":"DEVELOPMENT_ONLY","methods":list(METHODS),"seeds":len(SEEDS),"budget_sec":BUDGET_SEC,"cost":"FROZEN_CONTROLLED_WARM_Q90_TRANSITION_MODEL","metric":"PSEUDO_REFERENCE_EVENT_EXPOSURE_SCAN_TIME_AUC","formal_ranking":"BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION"})
    atomic_text(OUT / "COVERAGE_BASELINE_REPORT.md", "# Development Coverage Baselines\n\nResults are development-only comparisons against the frozen pseudo-reference; they are not formal benchmark rankings. Costs are frozen controlled-warm transition Q90 estimates.\n")

if __name__ == "__main__": main()
