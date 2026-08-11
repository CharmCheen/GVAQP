"""Clocked scan/refine loop used by the physical ARC integration.

The loop is dependency-injected so CPU tests can exercise deadline and leakage
semantics.  The executable runner wires these callbacks to the exact frozen
proxy, VERIFY accessor, K3 materializer, and durable commit implementation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .policy import ARCPhysicalPolicy


Clock = Callable[[], int]


@dataclass(frozen=True)
class ARCPhysicalRuntimeResult:
    stop_reason: str
    proxy_pass_complete: bool
    refinement_started: bool
    scan_actions: int
    logical_oracle_calls: int
    selected_unit_ids: tuple[int, ...]
    checkpoints: tuple[dict[str, Any], ...]
    actions: tuple[dict[str, Any], ...]
    proxy_summary: dict[str, Any] | None
    diagnostics: dict[str, Any]
    snapshot_elapsed_seconds: float
    total_elapsed_seconds: float
    deadline_seconds: float
    deadline_met: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.__dict__,
            "selected_unit_ids": list(self.selected_unit_ids),
            "checkpoints": list(self.checkpoints),
            "actions": list(self.actions),
        }


class ARCPhysicalRuntime:
    """Execute ARC within one monotonic, hard-deadline accounting domain."""

    def __init__(
        self,
        *,
        policy: ARCPhysicalPolicy,
        units: Sequence[dict[str, Any]],
        deadline_seconds: float,
        run_start_ns: int,
        scan_upper_seconds: float,
        commit_upper_seconds: float,
        scan_unit: Callable[[dict[str, Any]], dict[str, Any]],
        finalize_proxy_scores: Callable[[list[dict[str, Any]]], Sequence[float]],
        query_oracle: Callable[[int], dict[str, Any]],
        commit_snapshot: Callable[
            [list[dict[str, Any]], str, dict[str, Any] | None], dict[str, Any]
        ],
        admit_verify: Callable[[float], dict[str, Any]],
        final_synchronize: Callable[[], None],
        record_event: Callable[[str, dict[str, Any]], None] | None = None,
        initial_checkpoint: dict[str, Any] | None = None,
        clock_ns: Clock = time.perf_counter_ns,
    ) -> None:
        self.policy = policy
        self.units = [dict(row) for row in units]
        if [int(row["unit_id"]) for row in self.units] != list(range(len(self.units))):
            raise ValueError("runtime units must be contiguous in chronological order")
        self.deadline_seconds = float(deadline_seconds)
        self.run_start_ns = int(run_start_ns)
        self.scan_upper_seconds = float(scan_upper_seconds)
        self.commit_upper_seconds = float(commit_upper_seconds)
        self.scan_unit = scan_unit
        self.finalize_proxy_scores = finalize_proxy_scores
        self.query_oracle = query_oracle
        self.commit_snapshot = commit_snapshot
        self.admit_verify = admit_verify
        self.final_synchronize = final_synchronize
        self.record_event = record_event or (lambda event_type, fields: None)
        self.initial_checkpoint = (
            None if initial_checkpoint is None else dict(initial_checkpoint)
        )
        self.clock_ns = clock_ns

    def elapsed(self) -> float:
        return (self.clock_ns() - self.run_start_ns) / 1e9

    def run(self) -> ARCPhysicalRuntimeResult:
        checkpoints: list[dict[str, Any]] = []
        actions: list[dict[str, Any]] = []
        scans: list[dict[str, Any]] = []
        proxy_summary: dict[str, Any] | None = None
        stop_reason = "proxy_scan_exhausted"

        if self.initial_checkpoint is None:
            initial = self.commit_snapshot([], "initial_commit", None)
            checkpoints.append({
                "checkpoint_index": 0,
                "action": "initial_commit",
                "elapsed_seconds": self.elapsed(),
                "physical_oracle_calls": 0,
                "confirmed_events": int(initial.get("confirmed_events", 0)),
                **initial,
            })
            self.record_event("INITIAL_SNAPSHOT_DURABLY_COMMITTED", checkpoints[-1])
        else:
            checkpoints.append(dict(self.initial_checkpoint))
        if checkpoints[-1]["elapsed_seconds"] > self.deadline_seconds:
            stop_reason = "initial_commit_after_deadline"
        else:
            for unit in self.units:
                elapsed = self.elapsed()
                required = self.scan_upper_seconds + self.commit_upper_seconds
                if self.deadline_seconds - elapsed <= required:
                    stop_reason = "insufficient_scan_and_commit_reservation"
                    break
                action_start = elapsed
                result = self.scan_unit(unit)
                if int(result["unit_id"]) != int(unit["unit_id"]):
                    raise RuntimeError("proxy scan returned the wrong unit identity")
                scans.append(result)
                committed = self.commit_snapshot(
                    self.policy.comparable_queried_rows(), "scan", None
                )
                action_end = self.elapsed()
                actions.append({
                    "action": "scan",
                    "unit_id": int(unit["unit_id"]),
                    "start_seconds": action_start,
                    "end_seconds": action_end,
                    "future_proxy_accesses": 0,
                })
                checkpoints.append({
                    "checkpoint_index": len(checkpoints),
                    "action": "scan",
                    "elapsed_seconds": action_end,
                    "physical_oracle_calls": 0,
                    "confirmed_events": int(committed.get("confirmed_events", 0)),
                    **committed,
                })
                self.record_event("SCAN_DURABLY_COMMITTED", {
                    "unit_id": int(unit["unit_id"]),
                    "snapshot_path": committed.get("snapshot_path"),
                })
                self.scan_upper_seconds = max(
                    self.scan_upper_seconds, 1.5 * (action_end - action_start) + 0.5
                )
            else:
                scoring_start = self.elapsed()
                scores = list(map(float, self.finalize_proxy_scores(scans)))
                if len(scores) != len(self.units):
                    raise RuntimeError("complete proxy scorer did not return one score per unit")
                for unit_id, score in enumerate(scores):
                    self.policy.observe_proxy_score(unit_id, score)
                proxy_summary = self.policy.finish_proxy_pass()
                scoring_end = self.elapsed()
                actions.append({
                    "action": "proxy_finalize_calibrate_cluster",
                    "start_seconds": scoring_start,
                    "end_seconds": scoring_end,
                    "unit_count": len(scores),
                    "future_proxy_accesses": 0,
                })
                if scoring_end >= self.deadline_seconds:
                    stop_reason = "complete_proxy_pass_finished_after_deadline"
                else:
                    stop_reason = "arc_selector_stopped"
                    while True:
                        controller_start = self.elapsed()
                        selection = self.policy.select_next()
                        controller_end = self.elapsed()
                        if selection is None:
                            break
                        admission = dict(self.admit_verify(controller_end))
                        if not admission.get("admitted", False):
                            stop_reason = "verify_not_admitted:" + str(
                                admission.get("reason", "unspecified")
                            )
                            actions.append({
                                "action": "arc_controller_rejected",
                                "unit_id": selection.unit_id,
                                "start_seconds": controller_start,
                                "end_seconds": controller_end,
                                "admission": admission,
                            })
                            break
                        query_start = self.elapsed()
                        result = self.query_oracle(selection.unit_id)
                        query_end = self.elapsed()
                        observation = self.policy.observe_verify(selection, result)
                        committed = self.commit_snapshot(
                            self.policy.comparable_queried_rows(), "query", result
                        )
                        checkpoint_elapsed = self.elapsed()
                        actions.append({
                            "action": "query",
                            "unit_id": selection.unit_id,
                            "controller_start_seconds": controller_start,
                            "controller_end_seconds": controller_end,
                            "start_seconds": query_start,
                            "end_seconds": query_end,
                            "snapshot_elapsed_seconds": checkpoint_elapsed,
                            "outcome": observation.outcome,
                            "admission": admission,
                            "future_proxy_accesses": 0,
                        })
                        checkpoints.append({
                            "checkpoint_index": len(checkpoints),
                            "action": "query",
                            "elapsed_seconds": checkpoint_elapsed,
                            "physical_oracle_calls": len(
                                self.policy.diagnostics()["physical_observations"]
                            ),
                            "confirmed_events": int(
                                committed.get("confirmed_events", 0)
                            ),
                            **committed,
                        })
                        self.record_event("VERIFY_DURABLY_COMMITTED", {
                            "unit_id": selection.unit_id,
                            "parsed_label": observation.outcome,
                            "snapshot_path": committed.get("snapshot_path"),
                        })

        # Synchronization is deliberately inside total wall accounting.  It
        # cannot mutate the last already-durable EventRelation.
        self.final_synchronize()
        total_elapsed = self.elapsed()
        snapshot_elapsed = float(checkpoints[-1]["elapsed_seconds"])
        diagnostics = self.policy.diagnostics()
        self.record_event("RUN_COMPLETED", {
            "snapshot_elapsed_seconds": snapshot_elapsed,
            "deadline_met": snapshot_elapsed <= self.deadline_seconds,
            "physical_oracle_calls": len(diagnostics["physical_observations"]),
        })
        return ARCPhysicalRuntimeResult(
            stop_reason=stop_reason,
            proxy_pass_complete=self.policy.proxy_pass_complete,
            refinement_started=self.policy.refinement_started,
            scan_actions=len(scans),
            logical_oracle_calls=len(diagnostics["physical_observations"]),
            selected_unit_ids=tuple(diagnostics["selected_unit_ids"]),
            checkpoints=tuple(checkpoints),
            actions=tuple(actions),
            proxy_summary=proxy_summary,
            diagnostics=diagnostics,
            snapshot_elapsed_seconds=snapshot_elapsed,
            total_elapsed_seconds=total_elapsed,
            deadline_seconds=self.deadline_seconds,
            deadline_met=snapshot_elapsed <= self.deadline_seconds,
        )
