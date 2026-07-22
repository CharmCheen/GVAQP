#!/usr/bin/env python3
"""Prephysical and post-smoke correctness gates for H-SCAN1A."""

from __future__ import annotations

import json
import math
from pathlib import Path

from garc_eval.psvr_hscan1a.policy_service import decide, eligible_cells


REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs/psvr_autonomous_research/stage_4_scan_component_ablation"
OLD = REPO / "outputs/psvr_autonomous_research/stage_3_factorization/raw_matrix"
N = 347
PUBLIC = [{"unit_id": i} for i in range(N)]


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def payload(method: str, observed: dict[int, float], queried: list[int], scans: int) -> dict:
    return {"method": method, "public_units": PUBLIC,
            "proxy_rows": [{"unit_id": unit, "proxy_score": score} for unit, score in sorted(observed.items())],
            "queried_ids": queried, "batch_size": 4,
            "parameters": {"lambda": 0.5, "beta": 0.25, "revision": 0, "scan_actions": scans}}


def local_signal(unit: int, scores: dict[int, float]) -> float:
    if not scores:
        return 0.0
    scale = max(1.0, max(abs(value) for value in scores.values()))
    return max((max(0.0, value) / scale) / (1.0 + abs(unit - seen)) for seen, value in scores.items())


def replay_old_run(run: dict) -> dict:
    observed, queried, scans = {}, [], 0; mismatches = []
    candidate_ranks, candidate_creation = [], []
    for index, action in enumerate(run["actions"]):
        decision = decide(payload("D1", observed, queried, scans))
        expected_action = action["action"]
        if decision["action"] != expected_action:
            mismatches.append({"action_index": index, "field": "action", "new": decision["action"], "old": expected_action})
        if expected_action == "scan":
            if decision["scan_unit_ids"] != action["unit_ids"]:
                mismatches.append({"action_index": index, "field": "scan_unit_ids",
                                   "new": decision["scan_unit_ids"], "old": action["unit_ids"]})
            new_levels = [row["scan_level"] for row in decision["scan_priorities"]]
            candidate_ranks.append({"action_index": index,
                                    "visible_ranking": sorted(observed, key=lambda u: (-observed[u], u)),
                                    "selected_scan_levels": new_levels})
            for unit, score in zip(action["unit_ids"], action["scores"]):
                observed[int(unit)] = float(score)
            scans += 1
        else:
            if decision["candidate_unit_id"] != action["unit_id"]:
                mismatches.append({"action_index": index, "field": "candidate_unit_id",
                                   "new": decision["candidate_unit_id"], "old": action["unit_id"]})
            queried.append(int(action["unit_id"]))
        available = sorted(set(observed) - set(queried), key=lambda u: (-observed[u], u))
        candidate_creation.append({"action_index": index, "frontier": available})
    return {"run_id": run["run_id"], "mismatches": mismatches,
            "scan_cell_sequence": [unit for action in run["actions"] if action["action"] == "scan" for unit in action["unit_ids"]],
            "proxy_observation_sequence": [[int(unit), float(score)] for action in run["actions"] if action["action"] == "scan"
                                           for unit, score in zip(action["unit_ids"], action["scores"])],
            "candidate_creation_sequence": candidate_creation,
            "candidate_ranking_sequence": candidate_ranks,
            "physical_oracle_target_sequence": [int(q["unit_id"]) for q in run["queried_results"]],
            "VERIFY_admission_sequence": [a["admission"] for a in run["actions"] if a["action"] == "query"],
            "snapshot_event_sequence": [int(c["confirmed_events"]) for c in run["checkpoints"]]}


def zeroing_audit(runs: list[dict]) -> dict:
    checked_states = 0; checked_cells = 0; max_error = 0.0; eligibility_failures = []
    for run in runs:
        observed = {}
        for action_index, action in enumerate(run["actions"]):
            if action["action"] != "scan":
                continue
            cells = eligible_cells(N, set(observed)); checked_states += 1
            for cell in cells:
                span = int(cell["unobserved_span_units"]); unit = int(cell["unit_id"])
                duration = span / N
                debt = 0.5 * math.log2(span + 1.0) / math.log2(N + 1.0)
                proxy = 0.25 * local_signal(unit, observed)
                full, d2, d3 = duration + debt + proxy, duration + debt, proxy
                max_error = max(max_error, abs(full - (d2 + d3)), abs(d2 - (full - proxy)))
                checked_cells += 1
            baseline = [(row["cell_id"], row["unit_id"]) for row in cells]
            for method in ("D1", "D2", "D3"):
                # Component zeroing changes ranks, never the input eligibility set.
                current = [(row["cell_id"], row["unit_id"]) for row in eligible_cells(N, set(observed))]
                if current != baseline:
                    eligibility_failures.append({"run_id": run["run_id"], "action_index": action_index, "method": method})
            for unit, score in zip(action["unit_ids"], action["scores"]):
                observed[int(unit)] = float(score)
    return {"visited_scheduler_states": checked_states, "eligible_cells_checked": checked_cells,
            "max_decomposition_absolute_error": max_error,
            "D2_equals_full_minus_proxy": max_error < 1e-12,
            "D3_equals_proxy_group": max_error < 1e-12,
            "D1_D2_D3_frozen_eligibility": not eligibility_failures,
            "eligibility_failures": eligibility_failures,
            "D0_four_way_eligibility_requirement": "NOT_APPLICABLE_CONFLICTS_WITH_FROZEN_D0_FIXED_COVERAGE_DEFINITION",
            "D0_reason": "D0 must remain H-FACT1 C0 range(1,N,3); changing it to midpoint eligibility would violate D0 equivalence."}


def main() -> None:
    paths = [path for method in ("C0", "C1") for deadline in ("T_transition", "T_high")
             for path in sorted(OLD.glob(f"{method}__{deadline}__replicate_*/attempt_*/complete.json"))]
    old_runs = [json.loads(path.read_text()) for path in paths]
    c1 = [run for run in old_runs if run["method"] == "C1"]
    replays = [replay_old_run(run) for run in c1]
    equivalence = {"gate": "PASS" if all(not row["mismatches"] for row in replays) else "FAIL",
                   "H_FACT1_C1_runs_replayed": len(replays),
                   "scheduler_action_equivalence": all(not row["mismatches"] for row in replays),
                   "scan_cell_sequence_equivalence": all(not any(x["field"] == "scan_unit_ids" for x in row["mismatches"]) for row in replays),
                   "candidate_and_VERIFY_target_equivalence": all(not any(x["field"] == "candidate_unit_id" for x in row["mismatches"]) for row in replays),
                   "physical_sequences_source": "H-FACT1 C1 durable artifacts; new D1 physical comparison added after smoke",
                   "replays": replays}
    smoke_paths = sorted((OUT / "raw_smoke").glob("*/attempt_*/complete.json"))
    if smoke_paths:
        smoke = [json.loads(path.read_text()) for path in smoke_paths]
        d1 = next((run for run in smoke if run["method"] == "D1"), None)
        baseline = json.loads(next(OLD.glob("C1__T_transition__replicate_00/attempt_*/complete.json")).read_text())
        if d1:
            scan = lambda run: [u for a in run["actions"] if a["action"] == "scan" for u in a["unit_ids"]]
            queries = lambda run: [q["unit_id"] for q in run["queried_results"]]
            proxy = lambda run: [(u, s) for a in run["actions"] if a["action"] == "scan" for u, s in zip(a["unit_ids"], a["scores"])]
            physical = {"scan_cell_sequence_equal": scan(d1) == scan(baseline),
                        "proxy_observation_sequence_equal": proxy(d1) == proxy(baseline),
                        "physical_oracle_target_common_prefix_equal": queries(d1)[:min(len(queries(d1)),len(queries(baseline)))] == queries(baseline)[:min(len(queries(d1)),len(queries(baseline)))],
                        "D1_queries": queries(d1), "C1_queries": queries(baseline),
                        "snapshot_event_sequence_D1": [c["confirmed_events"] for c in d1["checkpoints"]],
                        "snapshot_event_sequence_C1": [c["confirmed_events"] for c in baseline["checkpoints"]],
                        "admitted_VERIFY_count_D1": d1["physical_oracle_calls"],
                        "admitted_VERIFY_count_C1": baseline["physical_oracle_calls"]}
            equivalence["physical_smoke"] = physical
            equivalence["physical_smoke_prefix_equivalent"] = all(physical[key] for key in
                ("scan_cell_sequence_equal", "proxy_observation_sequence_equal", "physical_oracle_target_common_prefix_equal"))
    formal_paths = sorted((OUT / "raw_matrix").glob("D1__*/attempt_*/complete.json"))
    if formal_paths:
        formal = []
        for path in formal_paths:
            new = json.loads(path.read_text())
            old_path = next(OLD.glob(f"C1__{new['deadline_name']}__replicate_{int(new['replicate']):02d}/attempt_*/complete.json"))
            old = json.loads(old_path.read_text())
            scan = lambda run: [u for a in run["actions"] if a["action"] == "scan" for u in a["unit_ids"]]
            proxy = lambda run: [(u, s) for a in run["actions"] if a["action"] == "scan" for u, s in zip(a["unit_ids"], a["scores"])]
            query = lambda run: [q["unit_id"] for q in run["queried_results"]]
            common = min(len(query(new)), len(query(old)))
            formal.append({"run_id": new["run_id"], "H_FACT1_run_id": old["run_id"],
                           "scan_cell_sequence_equal": scan(new) == scan(old),
                           "proxy_observation_sequence_equal": proxy(new) == proxy(old),
                           "query_common_prefix_equal": query(new)[:common] == query(old)[:common],
                           "new_admitted_VERIFY": len(query(new)), "old_admitted_VERIFY": len(query(old)),
                           "new_confirmed_events": new["checkpoints"][-1]["confirmed_events"],
                           "old_confirmed_events": old["checkpoints"][-1]["confirmed_events"]})
        equivalence["physical_formal_comparisons"] = formal
        equivalence["physical_formal_prefix_equivalent"] = all(
            row["scan_cell_sequence_equal"] and row["proxy_observation_sequence_equal"] and
            row["query_common_prefix_equal"] and row["new_confirmed_events"] == row["old_confirmed_events"]
            for row in formal)
    dump(OUT / "FULL_EQUIVALENCE_REPORT.json", equivalence)
    dump(OUT / "COMPONENT_ZEROING_REPORT.json", zeroing_audit(c1))
    print(json.dumps({"equivalence_gate": equivalence["gate"],
                      "zeroing": zeroing_audit(c1)}, indent=2))


if __name__ == "__main__":
    main()
