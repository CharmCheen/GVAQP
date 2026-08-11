from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .config import INITIAL_SCAN_COST_SEC
from .hidden_evaluator import (
    load_units,
    load_video,
    replay_frozen_visible,
    transition,
)
from .id_redaction import RunScopedIdMapper, new_public_run_id
from .isolated_policy_client import IsolatedPolicyClient
from .public_state_builder import (
    InternalRunState,
    build_choose_action_message,
    build_initialize_message,
)
from .runtime_accounting import action_admitted, remaining_budget_at_validation


class ReplayEnvironment:
    def __init__(
        self,
        *,
        video_id: str,
        policy_id: str,
        seed: int,
        budget_sec: float,
        public_contract_hash: str,
        private_stderr_log: Path,
    ):
        self.video = load_video(video_id)
        self.units = load_units(video_id)
        self.by_id = {str(unit["unit_id"]): unit for unit in self.units}
        self.mapper = RunScopedIdMapper(new_public_run_id())
        self.internal = InternalRunState(
            internal_video_id=video_id,
            duration_sec=float(self.video["duration_sec"]),
            units=self.units,
            budget_sec=float(budget_sec),
        )
        initialize = build_initialize_message(
            self.internal, self.mapper, public_contract_hash
        )
        self.client = IsolatedPolicyClient(
            policy_id=policy_id,
            seed=seed,
            initialize_message=initialize,
            private_stderr_log=private_stderr_log,
        )
        self.policy_id = policy_id
        self.trace: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        current: dict[str, Any] | None = None
        reason = "RUN_COMPLETE"
        try:
            while len(self.internal.scanned_internal_unit_ids) < len(self.units):
                step_id = len(self.trace)
                remaining_before_step = self.internal.remaining_budget_sec
                step_started = time.perf_counter()
                build_started = time.perf_counter()
                message = build_choose_action_message(
                    self.internal, self.mapper, step_id
                )
                public_state_build_sec = time.perf_counter() - build_started
                available_public_units = {
                    self.mapper.unit(str(unit["unit_id"]))
                    for unit in self.units
                    if str(unit["unit_id"])
                    not in self.internal.scanned_internal_unit_ids
                }
                selected_public, policy_timings = self.client.choose(
                    message, available_public_units
                )
                validate_started = time.perf_counter()
                selected_internal = self.mapper.internal_unit(selected_public)
                if selected_internal in self.internal.scanned_internal_unit_ids:
                    reason = "ACTION_ALREADY_SCANNED"
                    break
                selected = self.by_id[selected_internal]
                action_transition = transition(current, selected)
                environment_action_validate_sec = (
                    time.perf_counter() - validate_started
                )
                remaining_at_validation = remaining_budget_at_validation(
                    remaining_before_step,
                    policy_timings
                    | {"environment_action_validate_sec": environment_action_validate_sec},
                )
                if not action_admitted(INITIAL_SCAN_COST_SEC, remaining_at_validation):
                    reason = "NO_COMPLETE_ACTION_FITS"
                    break
                self.internal.scanned_internal_unit_ids.append(selected_internal)
                self.internal.current_internal_unit_id = selected_internal
                replay_started = time.perf_counter()
                candidates, exposed = replay_frozen_visible(
                    self.internal.internal_video_id,
                    set(self.internal.scanned_internal_unit_ids),
                )
                visible_subset_replay_time_sec = (
                    time.perf_counter() - replay_started
                )
                self.internal.visible_internal_candidate_ids = sorted(
                    candidates.candidate_id.astype(str)
                )
                self.internal.hidden_reference_event_ids = exposed
                self.internal.last_result_class = "LOGICAL_REPLAY"
                measured_overhead = time.perf_counter() - step_started
                budgeted_cost = INITIAL_SCAN_COST_SEC + measured_overhead
                self.internal.past_action_costs_sec.append(budgeted_cost)
                self.internal.remaining_budget_sec = max(
                    0.0,
                    self.internal.remaining_budget_sec - budgeted_cost,
                )
                record = {
                    "run_public_id": self.mapper.run_id,
                    "policy_id": self.policy_id,
                    "action_index": step_id,
                    **action_transition,
                    "selected_public_unit_id": selected_public,
                    "selected_internal_unit_id": selected_internal,
                    "public_state_build_sec": public_state_build_sec,
                    **policy_timings,
                    "environment_action_validate_sec": (
                        environment_action_validate_sec
                    ),
                    "remaining_budget_before_step_sec": (
                        remaining_before_step
                    ),
                    "remaining_budget_at_validation_sec": remaining_at_validation,
                    "estimated_post_validation_completion_sec": INITIAL_SCAN_COST_SEC,
                    "seek_time_sec": 0.0,
                    "decode_time_sec": 0.0,
                    "model_time_sec": 0.0,
                    "tracker_time_sec": 0.0,
                    "candidate_time_sec": 0.0,
                    "visible_subset_replay_time_sec": (
                        visible_subset_replay_time_sec
                    ),
                    "total_scan_action_time_sec": INITIAL_SCAN_COST_SEC,
                    "total_scheduler_step_time_sec": budgeted_cost,
                    "actual_replay_wall_clock_sec": measured_overhead,
                    "remaining_budget_sec": self.internal.remaining_budget_sec,
                    "visible_candidate_count": len(candidates),
                    "hidden_exposed_reference_count": len(exposed),
                    "action_started": True,
                    "action_completed": True,
                    "result_class": "LOGICAL_REPLAY_WITH_ESTIMATED_SCAN_COST",
                }
                self.trace.append(record)
                current = selected
        finally:
            self.client.close(reason)
        return {
            "trace": self.trace,
            "summary": {
                "video_id": self.internal.internal_video_id,
                "policy_id": self.policy_id,
                "public_run_id": self.mapper.run_id,
                "budget_sec": self.internal.budget_sec,
                "completed_action_count": len(self.trace),
                "termination_reason": reason,
                "final_remaining_budget_sec": (
                    self.internal.remaining_budget_sec
                ),
                "hidden_final_exposed_reference_count": len(
                    self.internal.hidden_reference_event_ids
                ),
                **self.client.summary(),
            },
        }
