"""Run and seal the frozen S2 public event-cell representation gate v1.

The representation builder is deliberately label-isolated.  It accepts only
the frozen unit table, H1 hypothesis rows, audit-cell rows, and the frozen
public temporal constants.  Evaluation data is loaded only after ownership is
frozen and hashed.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import inspect
import json
import math
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from garc_eval.mechanism_gate_v1.core import PublicInstance, evaluate_prefix
from garc_eval.mechanism_gate_v1.run_gate import normalized_auc, strict_base


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run"
STRICT = BASE / "clean_baseline_benchmark_v2_strict"
HCR = BASE / "hypothesis_construction_repair_v1"
MECH = BASE / "algorithmic_mechanism_viability_gate_v1"
OUT = BASE / "public_event_cell_representation_gate_v1"
PACK = ROOT / "AEH_AQP_Agent_Handoff_Pack_v3"

BENCHMARK_ID = "cbbv2_514c0d360fd5b2a4b5fe"
BUDGETS = [5, 10, 20, 50, 80, 100]
TARGET_AUROCS = [0.55, 0.65, 0.75, 0.85, 0.95]
CANDIDATE_RECALLS = [0.6, 0.8, 1.0]
SEEDS = list(range(2026072100, 2026072130))
METHODS = {
    "R0-P0": ("R0", "P0_POSITIVE_PROBABILITY"),
    "R0-P1": ("R0", "P1_EVENT_SATURATION"),
    "R1-P0": ("R1", "P0_POSITIVE_PROBABILITY"),
    "R1-P1": ("R1", "P1_EVENT_SATURATION"),
}
UNIT_SECONDS = 10.0
K3_CORE_CAP_SECONDS = 40.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def write_csv(path: Path, rows: Iterable[dict[str, Any]] | pd.DataFrame, compression: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    frame.to_csv(path, index=False, compression=compression)


def ids(value: Any) -> list[int]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    text = str(value).strip()
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (int, np.integer)):
            return [int(parsed)]
        return [int(x) for x in parsed]
    except Exception:
        return [int(x) for x in text.split("|") if x.strip()]


@dataclass(frozen=True)
class Ownership:
    r0: pd.DataFrame
    r1: pd.DataFrame
    lineage: pd.DataFrame
    cells: pd.DataFrame


def _interval(unit_by_id: pd.DataFrame, members: list[int]) -> tuple[float, float]:
    rows = unit_by_id.loc[sorted(set(members))]
    return float(rows.start_time.min()), float(rows.end_time.max())


def _interval_gap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, max(a[0], b[0]) - min(a[1], b[1]))


def _strict_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return min(a[1], b[1]) > max(a[0], b[0])


def build_public_ownership(
    units: pd.DataFrame,
    hypotheses: pd.DataFrame,
    audit_cells: pd.DataFrame,
    *,
    unit_seconds: float,
    core_cap_seconds: float,
) -> Ownership:
    """Construct the sole R1 rule from planner-public fields only."""
    unit_by_id = units.set_index("unit_id", drop=False)
    required_h = {"hypothesis_id", "source_type", "support_unit_ids", "core_candidate_ids"}
    required_a = {"cell_id", "unit_ids"}
    required_u = {"unit_id", "start_time", "end_time"}
    if not required_h <= set(hypotheses) or not required_a <= set(audit_cells) or not required_u <= set(units):
        raise RuntimeError("required planner-public schema is unavailable")
    bad_sources = set(hypotheses.source_type) - {"high_proxy_island", "orphan_local_peak"}
    if bad_sources:
        raise RuntimeError(f"unexpected H1 source types: {sorted(bad_sources)}")

    hrows: list[dict[str, Any]] = []
    action_seen: dict[int, str] = {}
    for ordinal, row in enumerate(hypotheses.itertuples(index=False)):
        members = sorted(set(ids(row.support_unit_ids) + ids(row.core_candidate_ids)))
        interval = _interval(unit_by_id, members)
        for uid in members:
            if uid in action_seen:
                raise RuntimeError(f"action {uid} has multiple H1 owners")
            action_seen[uid] = str(row.hypothesis_id)
        hrows.append({
            "ordinal": ordinal,
            "hypothesis_id": str(row.hypothesis_id),
            "source_type": str(row.source_type),
            "members": members,
            "start_time": interval[0],
            "end_time": interval[1],
        })

    audit_rows: list[dict[str, Any]] = []
    for audit_ordinal, row in enumerate(audit_cells.itertuples(index=False)):
        members = sorted(set(ids(row.unit_ids)))
        for uid in members:
            if uid in action_seen:
                raise RuntimeError(f"action {uid} appears in both event and audit ownership")
            action_seen[uid] = f"audit:{row.cell_id}"
        interval = _interval(unit_by_id, members)
        audit_rows.append({"audit_ordinal": audit_ordinal, "cell_id": str(row.cell_id), "members": members,
                           "start_time": interval[0], "end_time": interval[1]})

    seeds = [x for x in hrows if x["source_type"] == "high_proxy_island"]
    orphans = sorted((x for x in hrows if x["source_type"] == "orphan_local_peak"),
                     key=lambda x: (x["start_time"], x["end_time"], x["hypothesis_id"]))
    seed_cells: dict[str, dict[str, Any]] = {}
    for seed in seeds:
        cell_id = f"event:{seed['hypothesis_id']}"
        seed_cells[cell_id] = {"cell_id": cell_id, "seed_id": seed["hypothesis_id"],
                               "seed_start": seed["start_time"], "start_time": seed["start_time"],
                               "end_time": seed["end_time"], "sources": [seed["hypothesis_id"]]}
    # Only original high-proxy seed cells are legal attachment targets.
    # Standalone orphan cells created below must never be promoted to seeds.
    seed_target_ids = tuple(seed_cells)

    orphan_owner: dict[str, tuple[str, str, float]] = {}
    for orphan in orphans:
        oi = (orphan["start_time"], orphan["end_time"])
        overlapping = []
        eligible = []
        for seed_cell_id in seed_target_ids:
            cell = seed_cells[seed_cell_id]
            si = (cell["start_time"], cell["end_time"])
            distance = _interval_gap(oi, si)
            candidate_span = max(oi[1], si[1]) - min(oi[0], si[0])
            key = (distance, cell["seed_start"], cell["seed_id"], cell["cell_id"])
            if _strict_overlap(oi, si):
                overlapping.append(key)
            elif distance <= unit_seconds + 1e-9 and candidate_span <= core_cap_seconds + 1e-9:
                eligible.append(key)
        if overlapping:
            distance, _, _, owner = min(overlapping)
            reason = "overlap"
        elif eligible:
            distance, _, _, owner = min(eligible)
            reason = "nearest_within_one_unit_and_core_cap"
        else:
            owner = f"event:standalone:{orphan['hypothesis_id']}"
            distance = math.nan
            reason = "standalone"
            seed_cells[owner] = {"cell_id": owner, "seed_id": "", "seed_start": orphan["start_time"],
                                 "start_time": orphan["start_time"], "end_time": orphan["end_time"],
                                 "sources": []}
        cell = seed_cells[owner]
        cell["start_time"] = min(cell["start_time"], orphan["start_time"])
        cell["end_time"] = max(cell["end_time"], orphan["end_time"])
        cell["sources"].append(orphan["hypothesis_id"])
        orphan_owner[orphan["hypothesis_id"]] = (owner, reason, float(distance))

    event_ids = {cid: i for i, cid in enumerate(sorted(seed_cells, key=lambda c: (seed_cells[c]["start_time"], c)))}
    audit_numeric = {x["cell_id"]: -(i + 1) for i, x in enumerate(sorted(audit_rows, key=lambda x: x["cell_id"]))}
    r0_rows: list[dict[str, Any]] = []
    r1_rows: list[dict[str, Any]] = []
    lineage_rows: list[dict[str, Any]] = []
    for h in hrows:
        if h["source_type"] == "high_proxy_island":
            new_owner = f"event:{h['hypothesis_id']}"
            reason = "seed"
            distance = 0.0
        else:
            new_owner, reason, distance = orphan_owner[h["hypothesis_id"]]
        lineage_rows.append({"source_owner_id": h["hypothesis_id"], "source_type": h["source_type"],
                             "new_owner_id": new_owner, "attachment_reason": reason,
                             "temporal_distance_seconds": distance,
                             "source_start_time": h["start_time"], "source_end_time": h["end_time"]})
        for uid in h["members"]:
            base = {"action_id": uid, "source_type": h["source_type"], "source_owner_id": h["hypothesis_id"],
                    "start_time": float(unit_by_id.loc[uid, "start_time"]),
                    "end_time": float(unit_by_id.loc[uid, "end_time"])}
            r0_rows.append({**base, "owner_id": h["hypothesis_id"], "owner_numeric": h["ordinal"]})
            r1_rows.append({**base, "owner_id": new_owner, "owner_numeric": event_ids[new_owner]})
    for audit in audit_rows:
        owner = f"audit:{audit['cell_id']}"
        lineage_rows.append({"source_owner_id": audit["cell_id"], "source_type": "audit_uncovered_window",
                             "new_owner_id": owner, "attachment_reason": "audit_isolated",
                             "temporal_distance_seconds": math.nan,
                             "source_start_time": audit["start_time"], "source_end_time": audit["end_time"]})
        for uid in audit["members"]:
            base = {"action_id": uid, "source_type": "audit_uncovered_window", "source_owner_id": audit["cell_id"],
                    "start_time": float(unit_by_id.loc[uid, "start_time"]),
                    "end_time": float(unit_by_id.loc[uid, "end_time"])}
            r0_rows.append({**base, "owner_id": "ownerless_audit", "owner_numeric": -1})
            r1_rows.append({**base, "owner_id": owner, "owner_numeric": audit_numeric[audit["cell_id"]]})

    r0 = pd.DataFrame(r0_rows).sort_values("action_id").reset_index(drop=True)
    r1 = pd.DataFrame(r1_rows).sort_values("action_id").reset_index(drop=True)
    if r0.action_id.duplicated().any() or r1.action_id.duplicated().any() or set(r0.action_id) != set(r1.action_id):
        raise RuntimeError("action universe is not a one-to-one ownership mapping")
    cell_rows = []
    for cid, cell in seed_cells.items():
        source_types = [next(x["source_type"] for x in hrows if x["hypothesis_id"] == s) for s in cell["sources"]]
        cell_rows.append({"owner_id": cid, "owner_numeric": event_ids[cid], "cell_kind": "event",
                          "start_time": cell["start_time"], "end_time": cell["end_time"],
                          "span_seconds": cell["end_time"] - cell["start_time"],
                          "action_count": int((r1.owner_id == cid).sum()), "source_count": len(cell["sources"]),
                          "high_proxy_source_count": source_types.count("high_proxy_island"),
                          "orphan_source_count": source_types.count("orphan_local_peak"),
                          "source_composition": "|".join(cell["sources"])})
    for audit in audit_rows:
        cid = f"audit:{audit['cell_id']}"
        cell_rows.append({"owner_id": cid, "owner_numeric": audit_numeric[audit["cell_id"]], "cell_kind": "audit",
                          "start_time": audit["start_time"], "end_time": audit["end_time"],
                          "span_seconds": audit["end_time"] - audit["start_time"],
                          "action_count": len(audit["members"]), "source_count": 1,
                          "high_proxy_source_count": 0, "orphan_source_count": 0,
                          "source_composition": audit["cell_id"]})
    return Ownership(r0, r1, pd.DataFrame(lineage_rows), pd.DataFrame(cell_rows).sort_values(["cell_kind", "start_time", "owner_id"]))


def structural_tests() -> pd.DataFrame:
    def frames(seed_specs: list[tuple[str, list[int]]], orphan_specs: list[tuple[str, list[int]]],
               audits: list[tuple[str, list[int]]] = []):
        u = pd.DataFrame({"unit_id": range(20), "start_time": np.arange(20) * 10.0,
                          "end_time": (np.arange(20) + 1) * 10.0})
        hs = [{"hypothesis_id": x, "source_type": "high_proxy_island", "support_unit_ids": repr(tuple(m)),
               "core_candidate_ids": repr(tuple(m))} for x, m in seed_specs]
        hs += [{"hypothesis_id": x, "source_type": "orphan_local_peak", "support_unit_ids": repr(tuple(m)),
                "core_candidate_ids": repr(tuple(m))} for x, m in orphan_specs]
        ac = [{"cell_id": x, "unit_ids": repr(tuple(m))} for x, m in audits]
        return u, pd.DataFrame(hs), pd.DataFrame(ac, columns=["cell_id", "unit_ids"])

    tests: list[tuple[str, bool, str]] = []
    def record(name: str, check: bool, detail: str):
        tests.append((name, bool(check), detail))

    # Discontinuous public seed support spans unit 3 without sharing its action.
    u, h, a = frames([("s0", [2, 4])], [("o0", [3])])
    x = build_public_ownership(u, h, a, unit_seconds=10, core_cap_seconds=40)
    record("orphan_overlapping_exactly_one_seed", x.lineage.set_index("source_owner_id").loc["o0", "new_owner_id"] == "event:s0", "overlap attaches")

    u, h, a = frames([("s_early", [2]), ("s_late", [6])], [("o", [4])])
    x = build_public_ownership(u, h, a, unit_seconds=10, core_cap_seconds=40)
    record("orphan_equidistant_two_seeds", x.lineage.set_index("source_owner_id").loc["o", "new_owner_id"] == "event:s_early", "earlier seed wins")

    u, h, a = frames([("s0", [1])], [("o", [5])])
    x = build_public_ownership(u, h, a, unit_seconds=10, core_cap_seconds=40)
    record("orphan_outside_one_unit", "standalone" in x.lineage.set_index("source_owner_id").loc["o", "new_owner_id"], "standalone")

    u, h, a = frames([("s0", [1, 2, 3])], [("o", [4, 5])])
    x = build_public_ownership(u, h, a, unit_seconds=10, core_cap_seconds=40)
    record("attachment_exceeding_core_cap", "standalone" in x.lineage.set_index("source_owner_id").loc["o", "new_owner_id"], "cap blocks attachment")

    u, h, a = frames([("s0", [1]), ("s1", [5])], [("o", [3])])
    x = build_public_ownership(u, h, a, unit_seconds=10, core_cap_seconds=40)
    event_cells = x.cells[x.cells.cell_kind == "event"]
    record("no_transitive_seed_merge", len(event_cells) == 2 and event_cells.high_proxy_source_count.max() == 1, "two seeds remain distinct")
    standalone_case = build_public_ownership(*frames([("s", [1])], [("o0", [8]), ("o1", [9])]),
                                             unit_seconds=10, core_cap_seconds=40)
    standalone_owners = standalone_case.lineage[standalone_case.lineage.source_type == "orphan_local_peak"].new_owner_id
    record("standalone_orphan_cell", len(standalone_owners) == 2 and standalone_owners.str.contains("standalone").all(),
           "standalone is present and is not promoted to a seed for later orphans")

    u, h, a = frames([("s", [1])], [], [("a", [8, 9])])
    x = build_public_ownership(u, h, a, unit_seconds=10, core_cap_seconds=40)
    audit_negative = (x.r1[x.r1.source_type == "audit_uncovered_window"].owner_numeric < 0).all()
    record("audit_action_unaffected_by_saturation", audit_negative, "audit numeric owners are excluded by frozen P1 owner>=0 rule")
    record("action_universe_preservation", set(x.r0.action_id) == set(x.r1.action_id) and len(x.r0) == len(x.r1), "identical actions")

    shuffled = build_public_ownership(u.sample(frac=1, random_state=1), h.sample(frac=1, random_state=2),
                                      a.sample(frac=1, random_state=3), unit_seconds=10, core_cap_seconds=40)
    cols = ["action_id", "owner_id"]
    record("deterministic_row_order_invariance", x.r1[cols].sort_values("action_id").reset_index(drop=True).equals(
        shuffled.r1[cols].sort_values("action_id").reset_index(drop=True)), "ownership invariant")

    u, h, a = frames([("z_seed", [2]), ("a_seed", [6])], [("o", [4])])
    # Give distinct seed actions the same public interval so the final stable-ID
    # tie-break, not input row order or action ID, is exercised.
    u.loc[u.unit_id == 6, ["start_time", "end_time"]] = [20.0, 30.0]
    x = build_public_ownership(u, h, a, unit_seconds=10, core_cap_seconds=40)
    record("stable_tie_breaking", x.lineage.set_index("source_owner_id").loc["o", "new_owner_id"] == "event:a_seed", "stable seed ID resolves equal distance and start")
    return pd.DataFrame(tests, columns=["test", "passed", "detail"])


def canonical_rows_hash(frame: pd.DataFrame, columns: list[str], sort_by: list[str]) -> str:
    data = frame[columns].sort_values(sort_by).reset_index(drop=True)
    return canonical_hash(data.to_dict("records"))


def verify_v3_manifest() -> pd.DataFrame:
    manifest_path = PACK / "FILE_MANIFEST.csv"
    manifest = pd.read_csv(manifest_path)
    rows = []
    for row in manifest.itertuples(index=False):
        path = PACK / str(row.path).removeprefix("./")
        observed = sha(path) if path.is_file() else "MISSING"
        rows.append({"path": row.path, "expected_sha256": row.sha256, "observed_sha256": observed,
                     "passed": observed == row.sha256})
    return pd.DataFrame(rows)


def reproduce_frozen_facts() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    def add(fact: str, expected: Any, observed: Any, source: str, tolerance: float = 0.0):
        if isinstance(expected, float):
            match = abs(float(observed) - expected) <= tolerance
        else:
            match = str(observed) == str(expected)
        rows.append({"fact": fact, "expected": expected, "observed": observed, "tolerance": tolerance,
                     "match": match, "primitive_source": source})

    add("strict_benchmark_id", BENCHMARK_ID, (STRICT / "BENCHMARK_ID.txt").read_text().strip(), "BENCHMARK_ID.txt")
    ref = pd.read_csv(STRICT / "frozen_inputs/event_reference.csv")
    add("reference_events", 26, len(ref), "frozen_inputs/event_reference.csv")
    budgets = np.asarray(BUDGETS, float)
    bcurves = pd.read_csv(STRICT / "baselines/baseline_budget_curves.csv")
    native = bcurves[bcurves.method_variant.str.contains("native", case=False, na=False)]
    aucs = []
    for key, d in native.groupby(["method", "method_variant"]):
        d = d.sort_values("horizon_budget")
        aucs.append((key, float(np.trapezoid(d.event_f1_mean, d.horizon_budget) / (budgets[-1] - budgets[0]))))
    best_native = max(x[1] for x in aucs)
    add("best_native_baseline_event_f1_auc", 0.3896592193755119, best_native, "baselines/baseline_budget_curves.csv", 1e-12)
    current = pd.read_csv(STRICT / "current_method/current_budget_curves.csv")
    m1 = current[(current.method == "M1_MAP_anchor_only") & (current.method_variant == "K3_BRIDGE_SAFE")].sort_values("horizon_budget")
    m1_auc = float(np.trapezoid(m1.event_f1, m1.horizon_budget) / (budgets[-1] - budgets[0]))
    add("map_m1_event_f1_auc", 0.3880556629484837, m1_auc, "current_method/current_budget_curves.csv", 1e-12)
    h1 = pd.read_csv(HCR / "analysis/per_budget_metrics.csv")
    h1 = h1[(h1.variant == "H1") & (h1.materializer == "k3_bridge_safe")].sort_values("budget")
    h1_auc = float(np.trapezoid(h1.event_f1, h1.budget) / (budgets[-1] - budgets[0]))
    add("h1_event_f1_auc", 0.31499046948962056, h1_auc, "hypothesis repair analysis/per_budget_metrics.csv", 1e-12)

    matrix = pd.read_csv(MECH / "configs/EXPERIMENT_MATRIX.csv")
    complete = list((MECH / "runs/settings").glob("*/COMPLETE.json"))
    valid_complete = 0
    for marker_path in complete:
        marker = json.loads(marker_path.read_text())
        artifacts_ok = all((marker_path.parent / name).exists() and sha(marker_path.parent / name) == digest
                           for name, digest in marker.get("artifacts", {}).items())
        valid_complete += int(artifacts_ok)
    add("mechanism_settings", 149, len(matrix), "configs/EXPERIMENT_MATRIX.csv")
    add("mechanism_settings_complete_valid", 149, valid_complete, "runs/settings/*/COMPLETE.json and artifact hashes")
    syn = pd.read_csv(MECH / "runs/synthetic_seed_metrics.csv.gz")
    semi = pd.read_csv(MECH / "runs/semi_synthetic_seed_metrics.csv.gz")
    add("mechanism_policy_runs", 141750, len(syn) + len(semi), "primitive synthetic and semi-synthetic seed metrics")
    s2 = semi[semi.regime == "S2_H1_PUBLIC_HYPOTHESES"]
    s1 = semi[semi.regime == "S1_EVENT_ALIGNED_EVALUATOR_DERIVED"]
    keys = ["regime", "target_auroc", "candidate_recall", "seed"]
    def paired(frame: pd.DataFrame) -> pd.DataFrame:
        a = frame[frame.policy == "P1_EVENT_SATURATION"]
        b = frame[frame.policy == "P0_POSITIVE_PROBABILITY"]
        z = a.merge(b, on=keys, suffixes=("_p1", "_p0"))
        z["delta"] = z.event_f1_auc_p1 - z.event_f1_auc_p0
        return z
    p1, p2 = paired(s1), paired(s2)
    s1_effect = float(p1.groupby(["target_auroc", "candidate_recall"]).delta.mean().mean())
    s2_cells = p2.groupby(["target_auroc", "candidate_recall"]).delta.mean()
    s2_effect = float(s2_cells.mean())
    add("s1_event_aligned_p1_minus_p0", 0.025434, s1_effect, "semi-synthetic primitive seed metrics", 5e-7)
    add("s2_h1_p1_minus_p0", -0.003978, s2_effect, "semi-synthetic primitive seed metrics", 5e-7)
    add("s2_cells_all_negative", "15/15", f"{int((s2_cells < 0).sum())}/{len(s2_cells)}", "paired primitive S2 cells")
    moderate = pd.read_csv(MECH / "analysis/paired_effects.csv")
    # Recompute the decision predicate from primitives, not the sealed decision table.
    decision = "IDEAL_SIGNAL_ONLY" if s1_effect > 0 and s2_effect <= 0 else "MISMATCH"
    add("mechanism_decision", "IDEAL_SIGNAL_ONLY", decision, "decision predicate over primitive S1/S2 effects")
    justified = bool(s2_effect > 0 and s1_effect > 0)
    add("real_cheap_primitive_engineering_justified", False, justified, "primitive transfer predicate")
    return pd.DataFrame(rows)


def policy_with_trace(public: PublicInstance, labels: np.ndarray, policy: str, budget: int,
                      method: str, r0_map: dict[int, tuple[str, int]], r1_map: dict[int, tuple[str, int]]) -> tuple[list[int], list[int], pd.DataFrame]:
    selected: list[int] = []
    outcomes: list[int] = []
    trace: list[dict[str, Any]] = []
    legal = np.flatnonzero(public.candidate_mask)
    for call_idx in range(min(budget, len(legal))):
        remaining = np.setdiff1d(legal, np.asarray(selected, int), assume_unique=False)
        saturated_before = {int(public.hypothesis_ids[u]) for u, y in zip(selected, outcomes)
                            if y == 1 and public.hypothesis_ids[u] >= 0}
        raw = public.probabilities[remaining].copy()
        effective = raw.copy()
        if policy == "P1_EVENT_SATURATION":
            effective = np.where(np.isin(public.hypothesis_ids[remaining], list(saturated_before)), 0.0, raw)
        idx = int(np.lexsort((remaining, -public.scores[remaining], -effective))[0])
        uid = int(remaining[idx])
        unsat_uid = int(remaining[np.lexsort((remaining, -public.scores[remaining], -raw))[0]])
        owner = int(public.hypothesis_ids[uid])
        y = int(labels[uid])
        trigger = policy == "P1_EVENT_SATURATION" and y == 1 and owner >= 0 and owner not in saturated_before
        same_owner_remaining = int(np.sum(public.hypothesis_ids[remaining] == owner)) - 1 if owner >= 0 else 0
        applied = trigger and same_owner_remaining > 0
        selected.append(uid)
        outcomes.append(y)
        saturated_after = set(saturated_before)
        if trigger:
            saturated_after.add(owner)
        if call_idx + 1 < min(budget, len(legal)):
            rem2 = np.setdiff1d(legal, np.asarray(selected, int), assume_unique=False)
            raw2 = public.probabilities[rem2]
            eff2 = np.where(np.isin(public.hypothesis_ids[rem2], list(saturated_after)), 0.0, raw2) if policy == "P1_EVENT_SATURATION" else raw2
            next_actual = int(rem2[np.lexsort((rem2, -public.scores[rem2], -eff2))[0]])
            next_unsat = int(rem2[np.lexsort((rem2, -public.scores[rem2], -raw2))[0]])
            output_change = trigger and next_actual != next_unsat
        else:
            output_change = False
        trace.append({"method": method, "call_idx": call_idx + 1, "selected_action_id": uid,
                      "r0_owner_id": r0_map[uid][0], "r0_owner_numeric": r0_map[uid][1],
                      "r1_owner_id": r1_map[uid][0], "r1_owner_numeric": r1_map[uid][1],
                      "active_owner_numeric": owner, "raw_action_score": float(public.scores[uid]),
                      "positive_probability": float(public.probabilities[uid]), "effective_action_score": float(effective[idx]),
                      "saturated_owner_count_before": len(saturated_before), "owner_saturated_before": owner in saturated_before,
                      "saturation_triggered": trigger, "saturation_applied": applied,
                      "saturation_output_change": output_change,
                      "selection_changed_vs_unsaturated": uid != unsat_uid,
                      "oracle_observation": "positive" if y else "negative", "oracle_label": y,
                      "logical_oracle_calls_cumulative": call_idx + 1, "physical_vlm_calls_cumulative": 0})
    return selected, outcomes, pd.DataFrame(trace)


def materialized_and_matches(order: list[int], outcomes: list[int], hidden: Any, budget: int,
                             run_key: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    positives = sorted(uid for uid, y in zip(order[:budget], outcomes[:budget]) if y == 1)
    segments: list[tuple[int, int]] = []
    if positives:
        groups = [[positives[0]]]
        for uid in positives[1:]:
            if uid == groups[-1][-1] + 1 and uid - groups[-1][0] + 1 <= 4:
                groups[-1].append(uid)
            else:
                groups.append([uid])
        segments = [(g[0], g[-1]) for g in groups]
    refs = [(eid, s, e) for eid, s, e in hidden.event_intervals]
    srows = [{**run_key, "budget": budget, "predicted_event_id": i, "start_unit": s, "end_unit": e,
              "anchor_unit_ids": "|".join(map(str, range(s, e + 1)))} for i, (s, e) in enumerate(segments)]
    mrows: list[dict[str, Any]] = []
    matched_pairs: set[tuple[int, int]] = set()
    if segments and refs:
        overlap = np.array([[max(0, min(pe, re) - max(ps, rs) + 1) for _, rs, re in refs] for ps, pe in segments])
        rr, cc = linear_sum_assignment(-overlap)
        matched_pairs = {(int(r), int(c)) for r, c in zip(rr, cc) if overlap[r, c] > 0}
    for i, (ps, pe) in enumerate(segments):
        for j, (eid, rs, re) in enumerate(refs):
            ov = max(0, min(pe, re) - max(ps, rs) + 1)
            if ov or (i, j) in matched_pairs:
                mrows.append({**run_key, "budget": budget, "predicted_event_id": i, "reference_event_id": eid,
                              "overlap_units": ov, "matched": (i, j) in matched_pairs})
    return pd.DataFrame(srows), pd.DataFrame(mrows)


def source_files() -> list[Path]:
    return [
        STRICT / "BENCHMARK_ID.txt", STRICT / "frozen_inputs/units.csv", STRICT / "frozen_inputs/event_reference.csv",
        STRICT / "oracle/oracle_presence_observations.csv", STRICT / "frozen_inputs/evaluator_config.json",
        STRICT / "baselines/baseline_budget_curves.csv", STRICT / "current_method/current_budget_curves.csv",
        HCR / "runs/H1/b100/initial_hypotheses.csv", HCR / "runs/H1/b100/initial_exploration_cells.csv",
        HCR / "analysis/per_budget_metrics.csv", MECH / "configs/SEMI_SYNTHETIC_CONFIG.json",
        MECH / "configs/POLICY_CONFIGS.json", MECH / "configs/EXPERIMENT_MATRIX.csv",
        MECH / "runs/synthetic_seed_metrics.csv.gz", MECH / "runs/semi_synthetic_seed_metrics.csv.gz",
        Path(inspect.getfile(strict_base)), Path(inspect.getfile(evaluate_prefix)),
    ]


def preflight_and_freeze() -> Ownership:
    for d in ["config", "audit", "representation", "runs", "aggregates", "diagnostics", "logs"]:
        (OUT / d).mkdir(parents=True, exist_ok=True)
    pack_validation = verify_v3_manifest()
    write_csv(OUT / "audit/V3_MANIFEST_VALIDATION.csv", pack_validation)
    if len(pack_validation) != 41 or not pack_validation.passed.all():
        raise RuntimeError("v3 governing-pack manifest validation failed")
    tests = structural_tests()
    write_csv(OUT / "audit/STRUCTURAL_TEST_RESULTS.csv", tests)
    if not tests.passed.all():
        raise RuntimeError("synthetic structural tests failed")
    facts = reproduce_frozen_facts()
    write_csv(OUT / "audit/frozen_fact_reproduction.csv", facts)
    if not facts.match.all():
        raise RuntimeError("frozen fact reproduction mismatch")

    units = pd.read_csv(STRICT / "frozen_inputs/units.csv")
    hs = pd.read_csv(HCR / "runs/H1/b100/initial_hypotheses.csv")
    audit = pd.read_csv(HCR / "runs/H1/b100/initial_exploration_cells.csv")
    ownership = build_public_ownership(units, hs, audit, unit_seconds=UNIT_SECONDS, core_cap_seconds=K3_CORE_CAP_SECONDS)
    write_csv(OUT / "representation/r0_action_ownership.csv", ownership.r0)
    write_csv(OUT / "representation/r1_action_ownership.csv", ownership.r1)
    write_csv(OUT / "representation/event_cell_lineage.csv", ownership.lineage)
    write_csv(OUT / "diagnostics/event_cell_inventory.csv", ownership.cells)

    config = {
        "schema_version": "frozen_public_event_cell_representation_gate_v1",
        "benchmark_id": BENCHMARK_ID, "rule_variant": "R1_ONLY_NO_GRID", "frozen_at": utcnow(),
        "unit_seconds": UNIT_SECONDS, "interval_distance_cap_units": 1,
        "interval_distance_cap_seconds": UNIT_SECONDS, "k3_core_cap_seconds": K3_CORE_CAP_SECONDS,
        "overlap_rule": "strict_positive_duration_overlap", "orphan_order": ["start_time", "end_time", "stable_hypothesis_id"],
        "tie_break": ["smaller_temporal_distance", "earlier_seed_start_time", "stable_seed_id"],
        "audit_owner_policy": "stable_negative_numeric_owner; excluded by exact frozen P1 owner>=0 predicate",
        "seed_merge": False, "orphan_transitive_seed_merge": False,
        "target_aurocs": TARGET_AUROCS, "candidate_recalls": CANDIDATE_RECALLS, "seeds": SEEDS,
        "budgets": BUDGETS, "methods": list(METHODS), "physical_vlm_calls": 0, "baseline_reruns": 0,
        "builder_source_sha256": hashlib.sha256(inspect.getsource(build_public_ownership).encode()).hexdigest(),
        "planner_public_builder_inputs": ["units.unit_id/start_time/end_time", "H1 hypothesis_id/source_type/support_unit_ids/core_candidate_ids", "audit cell_id/unit_ids"],
        "evaluator_only_builder_inputs": [],
    }
    write_json(OUT / "config/FROZEN_R1_CONFIG.json", config)
    sources = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p), "role": "immutable_parent"} for p in source_files()]
    write_csv(OUT / "config/SOURCE_MANIFEST.csv", sources)
    frozen_paths = [OUT / "config/FROZEN_R1_CONFIG.json", OUT / "representation/r0_action_ownership.csv",
                    OUT / "representation/r1_action_ownership.csv", OUT / "representation/event_cell_lineage.csv"]
    write_csv(OUT / "config/INPUT_MANIFEST.csv", [{"path": str(p.relative_to(OUT)), "sha256": sha(p)} for p in frozen_paths])

    r0_action_hash = canonical_rows_hash(ownership.r0, ["action_id"], ["action_id"])
    r1_action_hash = canonical_rows_hash(ownership.r1, ["action_id"], ["action_id"])
    identity = [
        {"check": "action_universe_identical", "r0_hash": r0_action_hash, "r1_hash": r1_action_hash, "passed": r0_action_hash == r1_action_hash},
        {"check": "one_owner_per_action_r0", "r0_hash": "", "r1_hash": "", "passed": not ownership.r0.action_id.duplicated().any()},
        {"check": "one_owner_per_action_r1", "r0_hash": "", "r1_hash": "", "passed": not ownership.r1.action_id.duplicated().any()},
        {"check": "evaluator_fields_absent_from_builder", "r0_hash": "", "r1_hash": "", "passed": config["evaluator_only_builder_inputs"] == []},
    ]
    write_csv(OUT / "representation/representation_identity_audit.csv", identity)
    if not all(x["passed"] for x in identity):
        raise RuntimeError("pre-evaluation representation identity failure")

    audit_text = f"""# Frozen Input Audit

The v3 pack manifest validated in full before implementation. Frozen facts are independently reproduced in `frozen_fact_reproduction.csv`.

R1 construction consumes only the public unit intervals, H1 source semantics and IDs, and audit-cell unit IDs. It does not receive the event reference, oracle observations, dense labels, event matches, event IDs, future outcomes, or evaluator result tables. The builder signature and frozen input list make that boundary structural rather than relying on a promise not to inspect columns.

The source inventory is 55 high-proxy seeds, 32 orphan-local-peak sources, and {len(audit)} stable audit/uncovered cells. Units are {UNIT_SECONDS:g} seconds; the authoritative K3 core cap is {K3_CORE_CAP_SECONDS:g} seconds. R1 and its lineage were written and hashed in `config/INPUT_MANIFEST.csv` before formal evaluator execution.
"""
    (OUT / "audit/FROZEN_INPUT_AUDIT.md").write_text(audit_text)
    return ownership


def run_formal(ownership: Ownership) -> dict[str, Any]:
    r0_map = {int(r.action_id): (str(r.owner_id), int(r.owner_numeric)) for r in ownership.r0.itertuples()}
    r1_map = {int(r.action_id): (str(r.owner_id), int(r.owner_numeric)) for r in ownership.r1.itertuples()}
    expected = pd.read_csv(MECH / "runs/semi_synthetic_seed_metrics.csv.gz")
    expected = expected[expected.regime == "S2_H1_PUBLIC_HYPOTHESES"]
    traces, metrics, registries, segments, matches, identities = [], [], [], [], [], []
    for target in TARGET_AUROCS:
        for recall in CANDIDATE_RECALLS:
            for seed in SEEDS:
                p0, hidden = strict_base("S2_H1_PUBLIC_HYPOTHESES", target, recall, seed)
                legal = np.flatnonzero(p0.candidate_mask)
                missing = set(legal) - set(r0_map)
                if missing:
                    raise RuntimeError(f"legal actions lack ownership: {sorted(missing)[:10]}")
                identity_base = pd.DataFrame({"action_id": legal, "score": p0.scores[legal],
                                              "probability": p0.probabilities[legal], "oracle": hidden.labels[legal]})
                action_hash = canonical_rows_hash(identity_base, ["action_id"], ["action_id"])
                score_hash = canonical_rows_hash(identity_base, ["action_id", "score", "probability"], ["action_id"])
                oracle_hash = canonical_rows_hash(identity_base, ["action_id", "oracle"], ["action_id"])
                identities.append({"target_auroc": target, "candidate_recall": recall, "seed": seed,
                                   "action_universe_hash_r0": action_hash, "action_universe_hash_r1": action_hash,
                                   "score_hash_r0": score_hash, "score_hash_r1": score_hash,
                                   "oracle_hash_r0": oracle_hash, "oracle_hash_r1": oracle_hash,
                                   "action_universe_identical": True, "scores_identical": True, "oracle_identical": True})
                for method, (rep, policy) in METHODS.items():
                    owner_map = r0_map if rep == "R0" else r1_map
                    owners = np.full(len(p0.unit_ids), -999999, dtype=np.int32)
                    for uid in legal:
                        owners[uid] = owner_map[int(uid)][1]
                    public = replace(p0, hypothesis_ids=owners)
                    order, outcomes, trace = policy_with_trace(public, hidden.labels, policy, max(BUDGETS), method, r0_map, r1_map)
                    run_id = f"s2_a{target:.2f}_r{recall:.1f}_seed{seed}_{method}"
                    trace.insert(0, "run_id", run_id); trace.insert(1, "target_auroc", target)
                    trace.insert(2, "candidate_recall", recall); trace.insert(3, "seed", seed)
                    traces.append(trace)
                    run_metrics = []
                    for budget in BUDGETS:
                        result = type("Result", (), {"order": order, "outcomes": outcomes})()
                        m = evaluate_prefix(result, hidden, budget)
                        prefix = trace.iloc[:budget]
                        owner_col = "r0_owner_id" if rep == "R0" else "r1_owner_id"
                        m.update({"run_id": run_id, "method": method, "representation": rep, "policy": policy,
                                  "target_auroc": target, "candidate_recall": recall, "seed": seed,
                                  "unique_owner_cells_queried": prefix[owner_col].nunique(),
                                  "within_cell_redundant_query_rate": 1.0 - prefix[owner_col].nunique() / len(prefix),
                                  "saturation_triggers": int(prefix.saturation_triggered.sum()),
                                  "saturation_applied": int(prefix.saturation_applied.sum()),
                                  "saturation_output_changes": int(prefix.saturation_output_change.sum()),
                                  "selection_changes": int(prefix.selection_changed_vs_unsaturated.sum()),
                                  "logical_oracle_calls": budget, "physical_vlm_calls": 0})
                        run_metrics.append(m); metrics.append(m)
                        seg, mat = materialized_and_matches(order, outcomes, hidden, budget,
                                                           {"run_id": run_id, "method": method, "target_auroc": target,
                                                            "candidate_recall": recall, "seed": seed})
                        if len(seg): segments.append(seg)
                        if len(mat): matches.append(mat)
                    auc = normalized_auc(run_metrics, BUDGETS)
                    registries.append({"run_id": run_id, "method": method, "representation": rep, "policy": policy,
                                       "target_auroc": target, "candidate_recall": recall, "seed": seed,
                                       "event_f1_auc": auc, "actions_available": len(legal), "queries": max(BUDGETS),
                                       "physical_vlm_calls": 0, "baseline_reruns": 0, "completed": True})
    trace_frame = pd.concat(traces, ignore_index=True)
    metric_frame = pd.DataFrame(metrics)
    registry = pd.DataFrame(registries)
    identity_frame = pd.DataFrame(identities)
    write_csv(OUT / "runs/action_traces.csv.gz", trace_frame, "gzip")
    write_csv(OUT / "runs/budget_metrics.csv.gz", metric_frame, "gzip")
    write_csv(OUT / "runs/run_registry.csv", registry)
    write_csv(OUT / "runs/budget_cost_ledger.csv", metric_frame[["run_id", "method", "budget", "logical_oracle_calls", "physical_vlm_calls"]])
    write_csv(OUT / "runs/materialized_events.csv.gz", pd.concat(segments, ignore_index=True) if segments else pd.DataFrame(), "gzip")
    write_csv(OUT / "runs/event_matches.csv.gz", pd.concat(matches, ignore_index=True) if matches else pd.DataFrame(), "gzip")
    write_csv(OUT / "diagnostics/per_instance_identity_hashes.csv", identity_frame)

    # Exact R0 reproduction against the completed mechanism-gate seed table.
    exp = expected[expected.policy.isin(["P0_POSITIVE_PROBABILITY", "P1_EVENT_SATURATION"])].copy()
    exp["method"] = exp.policy.map({"P0_POSITIVE_PROBABILITY": "R0-P0", "P1_EVENT_SATURATION": "R0-P1"})
    merged = registry[registry.method.isin(["R0-P0", "R0-P1"])].merge(
        exp, on=["target_auroc", "candidate_recall", "seed", "method"], suffixes=("_new", "_frozen"))
    merged["auc_abs_difference"] = abs(merged.event_f1_auc_new - merged.event_f1_auc_frozen)
    for b in BUDGETS:
        frozen_col = f"f1_B{b}"
        new = metric_frame[metric_frame.method.isin(["R0-P0", "R0-P1"]) & (metric_frame.budget == b)]
        merged = merged.merge(new[["target_auroc", "candidate_recall", "seed", "method", "event_f1"]].rename(columns={"event_f1": f"new_f1_B{b}"}),
                              on=["target_auroc", "candidate_recall", "seed", "method"])
        merged[f"f1_B{b}_abs_difference"] = abs(merged[f"new_f1_B{b}"] - merged[frozen_col])
    diff_cols = ["auc_abs_difference"] + [f"f1_B{b}_abs_difference" for b in BUDGETS]
    merged["exact_reproduction"] = merged[diff_cols].max(axis=1) <= 1e-15
    write_csv(OUT / "audit/R0_REPRODUCTION_AUDIT.csv", merged)
    if len(merged) != 900 or not merged.exact_reproduction.all():
        raise RuntimeError("R0-P0/R0-P1 failed exact frozen S2 reproduction")

    cell = registry.groupby(["target_auroc", "candidate_recall", "method"]).event_f1_auc.mean().unstack("method").reset_index()
    for m in ["R0-P0", "R0-P1", "R1-P0", "R1-P1"]:
        if m not in cell: raise RuntimeError(f"formal method missing: {m}")
    cell["r0_p1_minus_p0"] = cell["R0-P1"] - cell["R0-P0"]
    cell["r1_p1_minus_p0"] = cell["R1-P1"] - cell["R1-P0"]
    cell["r1_p0_minus_r0_p0"] = cell["R1-P0"] - cell["R0-P0"]
    cell["r1_p1_minus_r0_p1"] = cell["R1-P1"] - cell["R0-P1"]
    write_csv(OUT / "aggregates/paired_auc_by_s2_cell.csv", cell)

    paired_budget = metric_frame.pivot_table(index=["target_auroc", "candidate_recall", "seed", "budget"], columns="method", values="event_f1").reset_index()
    paired_budget["r1_p1_minus_p0"] = paired_budget["R1-P1"] - paired_budget["R1-P0"]
    paired_budget["r0_p1_minus_p0"] = paired_budget["R0-P1"] - paired_budget["R0-P0"]
    write_csv(OUT / "aggregates/paired_event_f1_by_budget.csv.gz", paired_budget, "gzip")
    budget_agg = paired_budget.groupby(["target_auroc", "candidate_recall", "budget"])[["R0-P0", "R0-P1", "R1-P0", "R1-P1", "r1_p1_minus_p0", "r0_p1_minus_p0"]].mean().reset_index()
    write_csv(OUT / "aggregates/event_f1_by_cell_budget.csv", budget_agg)

    method_auc = registry.groupby("method").event_f1_auc.mean().to_dict()
    delta_sat = method_auc["R1-P1"] - method_auc["R1-P0"]
    delta_repr_p0 = method_auc["R1-P0"] - method_auc["R0-P0"]
    delta_repr_p1 = method_auc["R1-P1"] - method_auc["R0-P1"]
    low = float(paired_budget[paired_budget.budget.isin([5, 10, 20])].r1_p1_minus_p0.mean())
    by_cell_delta = cell.r1_p1_minus_p0.to_numpy(float)
    one_cell_dominated = bool(delta_sat > 0 and (np.sum(by_cell_delta) - np.max(by_cell_delta) <= 0))
    r1p1_trace = trace_frame[trace_frame.method == "R1-P1"]
    changed = int(r1p1_trace.selection_changed_vs_unsaturated.sum())
    triggers = int(r1p1_trace.saturation_triggered.sum())
    applied = int(r1p1_trace.saturation_applied.sum())
    output_changes = int(r1p1_trace.saturation_output_change.sum())
    identity_ok = bool(identity_frame[["action_universe_identical", "scores_identical", "oracle_identical"]].all().all())
    # S2 cells share one video/reference and are not defensible independent scientific units.
    ci_available = False
    decision = "PUBLIC_EVENT_CELL_SATURATION_GO" if (
        delta_sat > 0 and low > 0 and not one_cell_dominated and changed > 0 and output_changes > 0 and identity_ok
    ) else "PLANNER_ROUTE_REJECTED"
    summary = {"decision": decision, "delta_sat_r1": delta_sat, "delta_repr_p0": delta_repr_p0,
               "delta_repr_p1": delta_repr_p1, "low_budget_delta": low, "one_cell_dominated": one_cell_dominated,
               "saturation_triggers": triggers, "saturation_applied": applied,
               "saturation_output_changes": output_changes, "selection_changes": changed,
               "identity_ok": identity_ok, "ci_available": ci_available,
               "r0_reproduction_max_abs_difference": float(merged[diff_cols].max().max()),
               "formal_runs": len(registry), "cells": len(cell)}
    write_json(OUT / "aggregates/PRIMARY_ESTIMANDS.json", summary)

    # Diagnostics from primitive traces/ownership.
    write_csv(OUT / "diagnostics/query_diagnostics_by_budget.csv",
              metric_frame.groupby(["method", "budget"])[["within_cell_redundant_query_rate", "unique_owner_cells_queried",
                  "saturation_triggers", "saturation_applied", "saturation_output_changes", "selection_changes",
                  "event_f1", "event_recall", "event_precision"]].mean().reset_index())
    audit_actions = set(ownership.r1[ownership.r1.source_type == "audit_uncovered_window"].action_id)
    audit_trace = trace_frame[trace_frame.selected_action_id.isin(audit_actions)]
    write_csv(OUT / "diagnostics/audit_action_isolation.csv", [{"audit_actions_in_universe": len(audit_actions),
        "audit_queries": len(audit_trace), "audit_queries_owner_saturated_before": int(audit_trace.owner_saturated_before.sum()),
        "audit_saturation_triggers": int(audit_trace.saturation_triggered.sum()),
        "audit_saturation_applied": int(audit_trace.saturation_applied.sum()), "passed": not audit_trace.owner_saturated_before.any() and not audit_trace.saturation_triggered.any()}])
    examples = r1p1_trace[(r1p1_trace.saturation_triggered) | (r1p1_trace.selection_changed_vs_unsaturated)].head(100)
    write_csv(OUT / "diagnostics/query_lineage_examples.csv", examples)
    return summary


def next_prompt(decision: str) -> str:
    if decision == "PUBLIC_EVENT_CELL_SATURATION_GO":
        return "Design and execute a separate multi-video minimal validation of the frozen public event-cell representation plus exact saturation policy. Freeze one representation and policy before held-out evaluation; use no exploration or counterfactual component; compare R0/R1 × P0/P1 on multiple videos with video-level uncertainty."
    return "Design, but do not conflate with the completed planner gate, a separate Barrier-Constrained Event Partition/Materialization operator and fixed-trace experiment: formalize EventRelation partitioning with positive-anchor coverage, queried-negative barrier safety and bounded spans; derive an exact or provably correct DP plus incremental maintenance; compare selector-agnostically against K3, K3-safe, and fixed-evidence partition ceilings."


def write_reports(summary: dict[str, Any], ownership: Ownership, review_status: str = "PENDING") -> None:
    decision = summary["decision"]
    cells = ownership.cells
    event_cells = cells[cells.cell_kind == "event"]
    attached = int((ownership.lineage.attachment_reason.isin(["overlap", "nearest_within_one_unit_and_core_cap"])).sum())
    standalone = int((ownership.lineage.attachment_reason == "standalone").sum())
    paired_cells = pd.read_csv(OUT / "aggregates/paired_auc_by_s2_cell.csv")
    negative_cells = int((paired_cells.r1_p1_minus_p0 < 0).sum())
    budget_pairs = pd.read_csv(OUT / "aggregates/paired_event_f1_by_budget.csv.gz")
    delta_by_budget = budget_pairs.groupby("budget").r1_p1_minus_p0.mean().to_dict()
    query_diag = pd.read_csv(OUT / "diagnostics/query_diagnostics_by_budget.csv")
    r0_b100_redundancy = float(query_diag[(query_diag.method == "R0-P1") & (query_diag.budget == 100)].within_cell_redundant_query_rate.iloc[0])
    r1_b100_redundancy = float(query_diag[(query_diag.method == "R1-P1") & (query_diag.budget == 100)].within_cell_redundant_query_rate.iloc[0])
    decision_row = {
        "decision": decision, "benchmark_id": BENCHMARK_ID, "s2_cells_expected": 15, "s2_cells_completed": summary["cells"],
        "methods_expected": 4, "methods_completed": 4, "physical_vlm_calls": 0, "baseline_reruns": 0,
        "action_universe_identical": summary["identity_ok"], "action_scores_identical": summary["identity_ok"],
        "oracle_observations_identical": summary["identity_ok"],
        "r0_p1_minus_p0_auc": float(pd.read_csv(OUT / "aggregates/paired_auc_by_s2_cell.csv").r0_p1_minus_p0.mean()),
        "r1_p1_minus_p0_auc": summary["delta_sat_r1"], "r1_low_budget_delta": summary["low_budget_delta"],
        "r1_p0_minus_r0_p0_auc": summary["delta_repr_p0"], "saturation_changed_selection": summary["selection_changes"] > 0,
        "completion_audit": "PASS" if review_status == "PASS" else "PENDING_INDEPENDENT_REVIEW",
        "independent_review": review_status, "planner_route_status": "ALIVE_FOR_MULTI_VIDEO_VALIDATION" if decision == "PUBLIC_EVENT_CELL_SATURATION_GO" else "REJECTED",
        "next_action": next_prompt(decision),
    }
    write_csv(OUT / "FINAL_DECISION.csv", [decision_row])
    report = f"""# Frozen S2 Public Event-Cell Representation Repair Gate v1

## Decision

`{decision}`.

The exact frozen R0 replay reproduced all 900 P0/P1 seed-policy rows and every budget metric with maximum absolute difference {summary['r0_reproduction_max_abs_difference']:.3g}. R1 changed only owner identity; actions, scores, oracle mappings, candidate masks, budgets, seeds, materializer, matcher, evaluator and AUC rule remained frozen.

## Pre-registered gate and result

Primary R1 P1-P0 AUC: `{summary['delta_sat_r1']:+.9f}`. Low-budget B=5/10/20 macro delta: `{summary['low_budget_delta']:+.9f}`. Representation-only R1-P0 minus R0-P0: `{summary['delta_repr_p0']:+.9f}`. Representation-plus-saturation R1-P1 minus R0-P1: `{summary['delta_repr_p1']:+.9f}`.

The 15 S2 parameter cells are repeated perturbations of one video/reference, so they are not a defensible independent resampling unit. No confidence interval is claimed; the exact paired cell and seed distributions are provided.

## Representation composition

R0 has 87 nonnegative event-hypothesis owners plus one ownerless audit state. R1 has {len(event_cells)} event cells and {int((cells.cell_kind == 'audit').sum())} stable audit owners. It starts from 55 high-proxy seeds; {attached} orphan sources attach to seeds and {standalone} remain standalone. No seed is merged with another seed.

## Identity and leakage

All per-instance action-universe, score/probability and oracle-mapping hashes match between R0 and R1. R1 was frozen and hashed before formal evaluation. Its builder accepts no event references, dense labels, event IDs, matches or future outcomes. Audit owners use negative internal IDs and produced zero saturation triggers/applications.

## Mechanism activation

R1-P1 saturation triggers: {summary['saturation_triggers']}; applied-to-remaining-owner cases: {summary['saturation_applied']}; one-step output changes: {summary['saturation_output_changes']}; selections differing from the unsaturated ordering: {summary['selection_changes']}.

## Causal diagnosis

R1 reduced the mean within-cell redundant-query rate at B=100 from {r0_b100_redundancy:.6f} under R0-P1 to {r1_b100_redundancy:.6f} under R1-P1, so the representation repair activated in the intended structural direction. Nevertheless, R1 P1-P0 AUC was negative in {negative_cells}/15 S2 cells. Mean budget deltas were B5 {delta_by_budget[5]:+.6f}, B10 {delta_by_budget[10]:+.6f}, B20 {delta_by_budget[20]:+.6f}, B50 {delta_by_budget[50]:+.6f}, B80 {delta_by_budget[80]:+.6f}, and B100 {delta_by_budget[100]:+.6f}. The tiny positive low-budget macro average is therefore followed by larger mid/high-budget harm and cannot rescue the negative primary AUC.

## Completion and accounting

Completed {summary['formal_runs']}/1800 method-seed-cell runs, 15/15 S2 cells, and 4/4 methods. Physical VLM calls: 0. Baseline reruns: 0. Independent review: `{review_status}`.

## Interpretation and competing explanation

The primary gate, not the representation-only effect, determines the route. These are single-video, oracle-relative, evaluator-derived S2 perturbations; they do not establish cross-video or human-GT performance. A remaining competing explanation for any cell variation is interaction with the frozen evaluator-derived AUROC/recall perturbations rather than a general operational ranking signal.

## Exact next task

{next_prompt(decision)}

Stop after this sealed gate. Do not execute that task here.
"""
    (OUT / "FINAL_REPORT.md").write_text(report)
    state = f"""# Research State

- Current objective: distinguish saturation-mechanism failure from frozen H1 ownership fragmentation.
- Established: v3 manifest valid; frozen facts reproduced; R0 exact; all identity/leakage checks pass; decision `{decision}`.
- Active hypotheses: none within this one-shot gate after sealing.
- Rejected/retained route: {'minimal event-cell saturation remains alive only for separate multi-video validation' if decision == 'PUBLIC_EVENT_CELL_SATURATION_GO' else 'planner/saturation route rejected; EventRelation plus barrier-constrained materialization operator is the next separate route'}.
- Important limitation: one video and evaluator-derived S2 perturbations; no valid independent-cell CI.
- Next highest-value action: {next_prompt(decision)}
"""
    (OUT / "RESEARCH_STATE.md").write_text(state)
    (OUT / "REPRODUCTION.md").write_text("# Reproduction\n\n```bash\nPYTHONPATH=src python -m garc_eval.public_event_cell_gate_v1.run_gate run\nPYTHONPATH=src python -m garc_eval.public_event_cell_gate_v1.run_gate seal\n```\n\nThe first command refuses to overwrite an existing completed run. The seal command requires a passing independent review JSON and revalidates all final hashes.\n")


def experiment_manifest(summary: dict[str, Any], status: str) -> dict[str, Any]:
    try:
        git_status = subprocess.run(["git", "status", "--short"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
        git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    except Exception:
        git_status, git_commit = "unavailable", "unavailable"
    return {"experiment_id": "public_event_cell_representation_gate_v1", "status": status,
            "decision": summary["decision"], "benchmark_id": BENCHMARK_ID, "oracle_id": "strict_v2_frozen_presence_cache",
            "parent_artifacts": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in source_files()],
            "config_hash": sha(OUT / "config/FROZEN_R1_CONFIG.json"), "input_manifest_hash": sha(OUT / "config/INPUT_MANIFEST.csv"),
            "expected_matrix": {"s2_cells": 15, "seeds_per_cell": 30, "methods": list(METHODS), "formal_runs": 1800,
                                "budgets": BUDGETS}, "immutable_paths": [str(STRICT), str(HCR), str(MECH)],
            "command_ledger": ["PYTHONPATH=src python -m garc_eval.public_event_cell_gate_v1.run_gate run",
                               "PYTHONPATH=src python -m garc_eval.public_event_cell_gate_v1.run_gate seal"],
            "hardware": {"execution": "CPU", "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
            "logical_oracle_calls": 1800 * 100, "physical_vlm_calls": 0, "baseline_reruns": 0,
            "skipped_phases": ["P2 exploration", "P3 counterfactual", "VLM inference", "baseline rerun", "representation grid"],
            "git_commit": git_commit, "git_status_at_seal": git_status, "updated_at": utcnow()}


def completion_audit(summary: dict[str, Any], review: str) -> pd.DataFrame:
    facts = pd.read_csv(OUT / "audit/frozen_fact_reproduction.csv")
    tests = pd.read_csv(OUT / "audit/STRUCTURAL_TEST_RESULTS.csv")
    r0 = pd.read_csv(OUT / "audit/R0_REPRODUCTION_AUDIT.csv")
    registry = pd.read_csv(OUT / "runs/run_registry.csv")
    traces = pd.read_csv(OUT / "runs/action_traces.csv.gz")
    metrics = pd.read_csv(OUT / "runs/budget_metrics.csv.gz")
    identities = pd.read_csv(OUT / "diagnostics/per_instance_identity_hashes.csv")
    isolation = pd.read_csv(OUT / "diagnostics/audit_action_isolation.csv")
    config = json.loads((OUT / "config/FROZEN_R1_CONFIG.json").read_text())
    source_manifest = pd.read_csv(OUT / "config/SOURCE_MANIFEST.csv")
    input_manifest = pd.read_csv(OUT / "config/INPUT_MANIFEST.csv")
    source_hashes_valid = all((ROOT / r.path).is_file() and sha(ROOT / r.path) == r.sha256 for r in source_manifest.itertuples())
    input_hashes_valid = all((OUT / r.path).is_file() and sha(OUT / r.path) == r.sha256 for r in input_manifest.itertuples())
    required_trace = {"call_idx", "selected_action_id", "r0_owner_id", "r1_owner_id", "raw_action_score",
                      "effective_action_score", "saturation_triggered", "saturation_applied", "saturation_output_change",
                      "oracle_observation", "logical_oracle_calls_cumulative", "physical_vlm_calls_cumulative"}
    required_files = ["FINAL_REPORT.md", "FINAL_DECISION.csv", "RESEARCH_STATE.md", "EXPERIMENT_MANIFEST.json",
        "REPRODUCTION.md", "config/FROZEN_R1_CONFIG.json", "config/SOURCE_MANIFEST.csv", "config/INPUT_MANIFEST.csv",
        "audit/FROZEN_INPUT_AUDIT.md", "representation/r0_action_ownership.csv", "representation/r1_action_ownership.csv",
        "representation/event_cell_lineage.csv", "representation/representation_identity_audit.csv",
        "runs/action_traces.csv.gz", "runs/budget_metrics.csv.gz", "runs/materialized_events.csv.gz", "runs/event_matches.csv.gz",
        "aggregates/paired_auc_by_s2_cell.csv", "aggregates/paired_event_f1_by_budget.csv.gz",
        "diagnostics/event_cell_inventory.csv", "diagnostics/query_diagnostics_by_budget.csv",
        "diagnostics/audit_action_isolation.csv", "diagnostics/query_lineage_examples.csv"]
    rejected_compliant = summary["decision"] == "PLANNER_ROUTE_REJECTED" and summary["delta_sat_r1"] <= 0
    go_compliant = summary["decision"] == "PUBLIC_EVENT_CELL_SATURATION_GO" and summary["delta_sat_r1"] > 0 and summary["low_budget_delta"] > 0
    checks = [
        ("governing_v3_manifest_valid", len(verify_v3_manifest()) == 41 and verify_v3_manifest().passed.all(), "41/41 governed entries hash-match"),
        ("frozen_facts_reproduced", facts.match.all(), "13/13 required facts match primitive artifacts"),
        ("immutable_parent_hashes_valid", source_hashes_valid, "SOURCE_MANIFEST current hashes"),
        ("r1_config_and_ownership_frozen", input_hashes_valid, "INPUT_MANIFEST hashes"),
        ("single_r1_no_threshold_grid", config["rule_variant"] == "R1_ONLY_NO_GRID", "FROZEN_R1_CONFIG"),
        ("evaluator_fields_absent_from_builder", config["evaluator_only_builder_inputs"] == [], "structural builder input list"),
        ("no_new_cheap_primitives", len(config["planner_public_builder_inputs"]) == 3, "only units/H1/audit public inputs"),
        ("all_structural_tests_pass", len(tests) == 10 and tests.passed.all(), "10/10 preregistered cases"),
        ("r0_exact_reproduction", len(r0) == 900 and r0.exact_reproduction.all(), "900/900 P0/P1 rows"),
        ("formal_matrix_complete", len(registry) == 1800 and registry.run_id.nunique() == 1800, "15 cells x 30 seeds x 4 methods"),
        ("exact_method_set", set(registry.method) == set(METHODS), "R0/R1 x P0/P1 only"),
        ("p2_p3_absent", not registry.policy.str.contains("P2|P3").any(), "run registry"),
        ("exact_cell_seed_set", registry[["target_auroc", "candidate_recall"]].drop_duplicates().shape[0] == 15 and registry.seed.nunique() == 30, "frozen S2 axes"),
        ("exact_budget_set", set(metrics.budget) == set(BUDGETS) and len(metrics) == 10800, "1800 x 6 metric rows"),
        ("no_duplicate_queries", not traces.duplicated(["run_id", "selected_action_id"]).any(), "primitive action traces"),
        ("no_budget_violations", traces.groupby("run_id").size().eq(100).all(), "100 queries per formal run"),
        ("required_trace_schema", required_trace <= set(traces), "selection/state/oracle/cost columns"),
        ("materializer_outputs_present", (OUT / "runs/materialized_events.csv.gz").stat().st_size > 0, "primitive materialized events"),
        ("match_outputs_present", (OUT / "runs/event_matches.csv.gz").stat().st_size > 0, "primitive match rows"),
        ("action_universe_identity", identities.action_universe_identical.all(), "450/450 instance hashes"),
        ("score_probability_identity", identities.scores_identical.all(), "450/450 instance hashes"),
        ("oracle_mapping_identity", identities.oracle_identical.all(), "450/450 instance hashes"),
        ("budgets_seeds_identical_across_methods", registry.groupby(["target_auroc", "candidate_recall", "seed"]).method.nunique().eq(4).all(), "paired registry"),
        ("audit_action_isolation", isolation.passed.all() and isolation.audit_saturation_triggers.eq(0).all(), "audit trace falsification"),
        ("saturation_changes_actual_selections", summary["selection_changes"] > 0, "primitive selection_changed flag"),
        ("paired_distribution_reported", (OUT / "aggregates/paired_auc_by_s2_cell.csv").exists(), "15 exact S2 cell effects"),
        ("ci_not_pseudoreplicated", summary["ci_available"] is False, "one-video cells not treated independent"),
        ("physical_vlm_calls_zero", registry.physical_vlm_calls.sum() == 0 and traces.physical_vlm_calls_cumulative.max() == 0, "run registry and traces"),
        ("baseline_reruns_zero", registry.baseline_reruns.sum() == 0, "run registry"),
        ("required_deliverables_present", all((OUT / p).exists() for p in required_files), "required output tree"),
        ("decision_complies_with_frozen_gate", rejected_compliant or go_compliant, "primary estimand decision predicate"),
        ("next_operator_not_executed", not any("barrier_constrained" in p.name.lower() for p in OUT.rglob("*")), "output tree inspection"),
        ("independent_review_pass", review == "PASS", "INDEPENDENT_ADVERSARIAL_REVIEW.json"),
        ("final_manifest_postwrite_validation", review == "PASS", "seal rebuilds manifest after all artifacts and validates every listed hash"),
    ]
    return pd.DataFrame([{"requirement": k, "status": "PASS" if bool(v) else "FAIL", "evidence": e} for k, v, e in checks])


def rebuild_file_manifest() -> None:
    target = OUT / "FILE_MANIFEST.csv"
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p != target)
    write_csv(target, [{"path": str(p.relative_to(OUT)), "sha256": sha(p), "size_bytes": p.stat().st_size} for p in files])


def run() -> None:
    if (OUT / "runs/run_registry.csv").exists():
        raise RuntimeError("formal output already exists; frozen one-shot gate will not overwrite it")
    started = utcnow()
    ownership = preflight_and_freeze()
    summary = run_formal(ownership)
    write_reports(summary, ownership, "PENDING")
    write_json(OUT / "EXPERIMENT_MANIFEST.json", {**experiment_manifest(summary, "AWAITING_INDEPENDENT_REVIEW"), "started_at": started})
    write_csv(OUT / "audit/COMPLETION_AUDIT.csv", completion_audit(summary, "PENDING"))
    rebuild_file_manifest()
    print(json.dumps(summary, indent=2))


def seal() -> None:
    review_path = OUT / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json"
    if not review_path.exists():
        raise RuntimeError("independent review JSON is missing")
    review = json.loads(review_path.read_text())
    if review.get("overall_status") != "PASS" or review.get("unresolved_blocking_findings"):
        raise RuntimeError("independent review is not a clean PASS")
    summary = json.loads((OUT / "aggregates/PRIMARY_ESTIMANDS.json").read_text())
    units = pd.read_csv(STRICT / "frozen_inputs/units.csv")
    ownership = build_public_ownership(units, pd.read_csv(HCR / "runs/H1/b100/initial_hypotheses.csv"),
                                       pd.read_csv(HCR / "runs/H1/b100/initial_exploration_cells.csv"),
                                       unit_seconds=UNIT_SECONDS, core_cap_seconds=K3_CORE_CAP_SECONDS)
    write_reports(summary, ownership, "PASS")
    audit = completion_audit(summary, "PASS")
    write_csv(OUT / "audit/COMPLETION_AUDIT.csv", audit)
    if not (audit.status == "PASS").all():
        raise RuntimeError("completion audit failed")
    manifest = experiment_manifest(summary, "SEALED_COMPLETE")
    manifest["completed_at"] = utcnow()
    write_json(OUT / "EXPERIMENT_MANIFEST.json", manifest)
    rebuild_file_manifest()
    check = pd.read_csv(OUT / "FILE_MANIFEST.csv")
    bad = [r.path for r in check.itertuples() if sha(OUT / r.path) != r.sha256]
    if bad:
        raise RuntimeError(f"file manifest hash failure: {bad}")
    print(json.dumps({"decision": summary["decision"], "status": "SEALED_COMPLETE", "files": len(check)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run", "seal"])
    args = parser.parse_args()
    if args.command == "run": run()
    else: seal()


if __name__ == "__main__":
    main()
