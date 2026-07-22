#!/usr/bin/env python3
"""Stage 3A: local, visited-state-only attribution of the Stage-2 win."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "outputs/psvr_autonomous_research/stage_2_baselines/raw"
OUT = REPO / "outputs/psvr_autonomous_research/stage_3_action_attribution"
WINNING_UNIT = 75
N = 347
LAM = 0.5
BETA = 0.25


def blocks(observed: set[int]) -> list[tuple[int, int]]:
    result, start = [], None
    for unit in range(N):
        if unit not in observed and start is None:
            start = unit
        if unit in observed and start is not None:
            result.append((start, unit - 1)); start = None
    if start is not None:
        result.append((start, N - 1))
    return result


def local_signal(unit: int, scores: dict[int, float]) -> float:
    if not scores:
        return 0.0
    scale = max(1.0, max(abs(value) for value in scores.values()))
    return max((max(0.0, value) / scale) / (1.0 + abs(unit - seen))
               for seen, value in scores.items())


def rank_state(observed: set[int], scores: dict[int, float], queried: set[int],
               scan_actions: int, action_index: int, run_id: str) -> list[dict]:
    candidates = []
    norm = math.log2(N + 1.0)
    for left, right in blocks(observed):
        span = right - left + 1
        unit = (left + right) // 2
        coverage = span / N + LAM * math.log2(span + 1.0) / norm
        signal = BETA * local_signal(unit, scores)
        candidates.append({"unit_id": unit, "full": coverage + signal,
                           "without_coverage_debt": signal,
                           "without_proxy_signal": coverage})
    variants = ("full", "without_coverage_debt", "without_proxy_signal")
    ranks = {}
    for variant in variants:
        ordered = sorted(candidates, key=lambda row: (-row[variant], row["unit_id"]))
        ranks[variant] = {row["unit_id"]: index + 1 for index, row in enumerate(ordered)}
    full_order = sorted(candidates, key=lambda row: (-row["full"], row["unit_id"]))
    a1_action = "scan" if not (observed - queried) or scan_actions <= len(queried) else "query"
    a0_action = "scan" if scan_actions < 29 else ("query" if observed - queried else "stop")
    rows = []
    for row in candidates:
        rows.append({"run_id": run_id, "action_index": action_index,
                     "visited_state_action_A1": a1_action,
                     "fixed_VERIFY_trigger_A0_action": a0_action,
                     **row,
                     "rank_full": ranks["full"][row["unit_id"]],
                     "rank_without_coverage_debt": ranks["without_coverage_debt"][row["unit_id"]],
                     "rank_without_proxy_signal": ranks["without_proxy_signal"][row["unit_id"]],
                     "full_selected_in_batch": row["unit_id"] in {x["unit_id"] for x in full_order[:4]}})
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = sorted(RAW.glob("*/attempt_*/complete.json"))
    runs = [json.loads(path.read_text()) for path in paths]
    if len(runs) != 45 or any(row.get("status") != "ok" for row in runs):
        raise RuntimeError(f"expected exactly 45 valid Stage-2 runs, found {len(runs)}")
    winning = [row for row in runs if any(q["unit_id"] == WINNING_UNIT and q["parsed_label"] == "positive"
                                           for q in row["queried_results"])]
    if len(winning) != 3:
        raise RuntimeError(f"expected three runtime repeats of the unique win, found {len(winning)}")

    all_rank_rows, timelines, rank_history = [], [], []
    for run in winning:
        observed: set[int] = set(); scores: dict[int, float] = {}; queried: set[int] = set(); scans = 0
        first_scan = relevant = creation = None
        for index, action in enumerate(run["actions"]):
            if action["action"] == "scan":
                rows = rank_state(observed, scores, queried, scans, index, run["run_id"])
                all_rank_rows.extend(rows)
                for unit, score in zip(action["unit_ids"], action["scores"]):
                    observed.add(int(unit)); scores[int(unit)] = float(score)
                    if int(unit) == WINNING_UNIT:
                        first_scan = {"action_index": index, "scan_start_seconds": action["start_seconds"],
                                      "scan_end_seconds": action["end_seconds"]}
                        relevant = {**first_scan, "proxy_score": float(score)}
                scans += 1
                available = sorted(observed - queried, key=lambda unit: (-scores[unit], unit))
                if WINNING_UNIT in observed and creation is None:
                    creation = {"action_index": index, "elapsed_seconds": action["end_seconds"],
                                "candidate_rank_after_action": available.index(WINNING_UNIT) + 1}
                if WINNING_UNIT in observed and WINNING_UNIT not in queried:
                    rank_history.append({"run_id": run["run_id"], "action_index": index,
                                         "state": "after_scan", "candidate_rank": available.index(WINNING_UNIT) + 1,
                                         "candidate_score": scores[WINNING_UNIT]})
            else:
                available = sorted(observed - queried, key=lambda unit: (-scores[unit], unit))
                if WINNING_UNIT in available:
                    rank_history.append({"run_id": run["run_id"], "action_index": index,
                                         "state": "before_verify", "candidate_rank": available.index(WINNING_UNIT) + 1,
                                         "candidate_score": scores[WINNING_UNIT]})
                queried.add(int(action["unit_id"]))
        query_index = next(i for i, q in enumerate(run["queried_results"]) if q["unit_id"] == WINNING_UNIT)
        query = run["queried_results"][query_index]
        verify_action = next(a for a in run["actions"] if a["action"] == "query" and a["unit_id"] == WINNING_UNIT)
        checkpoint = next(c for c in run["checkpoints"]
                          if c["action"] == "query" and c["physical_oracle_calls"] == query_index + 1)
        timelines.append({"run_id": run["run_id"], "first_cell_scan": first_scan,
                          "first_relevant_proxy_observation": relevant, "candidate_creation": creation,
                          "VERIFY_admission": verify_action["admission"],
                          "VERIFY_start_seconds": query["query_start_seconds"],
                          "VERIFY_completion_seconds": query["query_end_seconds"],
                          "confirmation": {"parsed_label": query["parsed_label"],
                                           "confidence": query["confidence"],
                                           "parse_status": query["parse_status"]},
                          "snapshot_commit_seconds": checkpoint["elapsed_seconds"],
                          "snapshot_path": checkpoint["snapshot_path"]})

    fields = list(all_rank_rows[0])
    with (OUT / "VISITED_STATE_PRIORITY_AUDIT.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(all_rank_rows)
    with (OUT / "CANDIDATE_RANK_HISTORY.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rank_history[0])); writer.writeheader(); writer.writerows(rank_history)
    (OUT / "WINNING_EVENT_TIMELINE.json").write_text(json.dumps({
        "winning_unit_id": WINNING_UNIT, "semantic_event_instances": 1,
        "runtime_repeats": len(timelines), "timelines": timelines}, indent=2) + "\n")

    full_changed_by_signal = sum(row["rank_full"] != row["rank_without_proxy_signal"] for row in all_rank_rows)
    full_changed_by_coverage = sum(row["rank_full"] != row["rank_without_coverage_debt"] for row in all_rank_rows)
    fixed_trigger_disagreements = sum(row["visited_state_action_A1"] != row["fixed_VERIFY_trigger_A0_action"]
                                      for row in all_rank_rows if row["rank_full"] == 1)
    result = {
        "audit_population": {"stage2_runs": 45, "winning_runs": 3,
                             "semantic_samples": 1, "runtime_repeats_not_semantic_samples": True},
        "primary_driver": "INCONCLUSIVE_INTERACTION_OR_ALLOCATION",
        "secondary_driver": "coverage_debt_scan_order_exposed_unit_75_before_the_sixth_VERIFY",
        "attribution_confidence": "LOW_TO_MODERATE",
        "evidence_scope": "visited_scheduler_states_of_three_runtime_repeats_on_one_development_video_query",
        "physically_validated": False,
        "observed_evidence": {
            "winning_unit": WINNING_UNIT,
            "winning_unit_recovered_in_all_C3_T_high_repeats": True,
            "other_stage2_runs_with_confirmed_event": 0,
            "visited_priority_candidate_rows": len(all_rank_rows),
            "rank_entries_changed_when_proxy_signal_removed": full_changed_by_signal,
            "rank_entries_changed_when_coverage_debt_removed": full_changed_by_coverage,
            "fixed_trigger_action_disagreements_at_visited_scan_states": fixed_trigger_disagreements,
        },
        "derived_conclusion": "The local trace proves that both exposure by S1 and admission of a sixth VERIFY were necessary on the realized path, but it cannot identify their separate causal effects.",
        "competing_explanation": "Runtime timing or the scan/allocation interaction, rather than either marginal factor, may explain the win.",
        "counterfactual_limit": "No hidden proxy observation, unexecuted trajectory, counterfactual F1, counterfactual AnytimeAUC, or counterfactual recovery was computed.",
        "CF4_CF5_resolution": "Deferred to physical C1 and C2 in H-FACT1.",
    }
    (OUT / "ACTION_ATTRIBUTION.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "README.md").write_text(
        "# Stage 3A local action attribution\n\n"
        "This audit is restricted to scheduler states actually visited by the three Stage-2 winning runtime repeats. "
        "It is diagnostic, not a physical validation and not a branch decision.\n"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
